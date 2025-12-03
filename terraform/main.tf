terraform {
  required_version = ">= 1.0"

  backend "local" {
    # For a real project, use a remote backend like S3
    # path = "terraform.tfstate"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.2"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

#------------------------------------------------------------------------------
# S3 Data Lake Bucket
#------------------------------------------------------------------------------
resource "aws_s3_bucket" "data_lake" {
  bucket = var.s3_bucket_name

  tags = {
    Name      = "${var.project_name}-data-lake"
    Project   = var.project_name
    ManagedBy = "Terraform"
  }
}

resource "aws_s3_bucket_public_access_block" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

#------------------------------------------------------------------------------
# IAM Role and Policy for Lambda
#------------------------------------------------------------------------------
data "aws_caller_identity" "current" {}

resource "aws_iam_role" "lambda_exec_role" {
  name = "${var.project_name}-lambda-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project = var.project_name
  }
}

resource "aws_iam_policy" "lambda_policy" {
  name        = "${var.project_name}-lambda-policy"
  description = "IAM policy for Lambda to write to S3, CloudWatch Logs, and read from Secrets Manager."

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Sid = "AllowS3Actions",
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ],
        Effect = "Allow",
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*"
        ]
      },
      {
        Sid      = "AllowLogGroupCreation",
        Action   = "logs:CreateLogGroup",
        Effect   = "Allow",
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project_name}-etl:*"
      },
      {
        Sid = "AllowLogStreamActions",
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Effect   = "Allow",
        Resource = "arn:aws:logs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.project_name}-etl:*:*"
      },
      {
        Sid = "AllowSecretsManagerRead",
        Action = [
          "secretsmanager:GetSecretValue"
        ],
        Effect   = "Allow",
        Resource = var.coingecko_api_key_secret_arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_policy_attach" {
  role       = aws_iam_role.lambda_exec_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

#------------------------------------------------------------------------------
# ECR Repository for Lambda Docker Image
#------------------------------------------------------------------------------
resource "aws_ecr_repository" "lambda_repo" {
  name                 = "${var.project_name}-lambda-repo"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Project = var.project_name
  }
}

#------------------------------------------------------------------------------
# Build and push Docker image to ECR
#------------------------------------------------------------------------------
resource "null_resource" "docker_build_and_push" {
  triggers = {
    dockerfile_hash       = filemd5("${path.module}/../lambda/Dockerfile")
    requirements_txt_hash = filemd5("${path.module}/../lambda/src/requirements.txt")
    lambda_src_hash       = filemd5("${path.module}/../lambda/src/lambda_etl.py")
  }

  provisioner "local-exec" {
    command     = <<EOT
      aws ecr get-login-password --region ${var.aws_region} | docker login --username AWS --password-stdin ${aws_ecr_repository.lambda_repo.repository_url}
      docker build --platform linux/amd64 -t ${aws_ecr_repository.lambda_repo.name} ${path.module}/../lambda
      docker tag ${aws_ecr_repository.lambda_repo.name}:latest ${aws_ecr_repository.lambda_repo.repository_url}:latest
      docker push ${aws_ecr_repository.lambda_repo.repository_url}:latest
    EOT
    interpreter = ["bash", "-c"]
  }

  depends_on = [aws_ecr_repository.lambda_repo]
}

#------------------------------------------------------------------------------
# Lambda Function
#------------------------------------------------------------------------------
resource "aws_lambda_function" "etl_function" {
  function_name = "${var.project_name}-etl"
  role          = aws_iam_role.lambda_exec_role.arn
  timeout       = 60
  memory_size   = 512

  package_type = "Image"
  image_uri    = "${aws_ecr_repository.lambda_repo.repository_url}:latest"

  depends_on = [null_resource.docker_build_and_push]

  environment {
    variables = {
      S3_BUCKET                     = aws_s3_bucket.data_lake.id
      S3_PREFIX                     = "raw/coingecko"
      FILE_FORMAT                   = "parquet"
      COINGECKO_API_KEY_SECRET_NAME = var.coingecko_api_key_secret_arn
    }
  }

  tags = {
    Project = var.project_name
  }
}

#------------------------------------------------------------------------------
# EventBridge Rule to schedule Lambda daily
#------------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "daily_trigger" {
  name                = "${var.project_name}-daily-trigger"
  description         = "Triggers the crypto ETL Lambda function once a day."
  schedule_expression = "rate(1 day)"
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.daily_trigger.name
  target_id = "${var.project_name}-lambda-target"
  arn       = aws_lambda_function.etl_function.arn
}

resource "aws_lambda_permission" "allow_cloudwatch" {
  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.etl_function.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_trigger.arn
}


#------------------------------------------------------------------------------
# S3 Bucket Policy – Allow QuickSight to Read From Data Lake
#------------------------------------------------------------------------------
data "aws_iam_policy_document" "data_lake_policy" {
  statement {
    sid = "AllowQuickSightRead"

    principals {
      type        = "Service"
      identifiers = ["quicksight.amazonaws.com"]
    }

    actions = [
      "s3:GetObject",
      "s3:ListBucket"
    ]

    resources = [
      aws_s3_bucket.data_lake.arn,
      "${aws_s3_bucket.data_lake.arn}/*"
    ]
  }
}

resource "aws_s3_bucket_policy" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  policy = data.aws_iam_policy_document.data_lake_policy.json
}
