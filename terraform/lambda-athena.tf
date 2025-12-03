resource "aws_lambda_function" "athena_query" {
  function_name = "${var.project_name}-athena-query"
  role          = aws_iam_role.athena_query_lambda_role.arn
  handler       = "index.handler"
  runtime       = "nodejs20.x"

  # JS zip created from lambda/athena-query folder
  filename         = "${path.module}/../lambda/athena-query.zip"
  source_code_hash = filebase64sha256("${path.module}/../lambda/athena-query.zip")

  # Lambda environment variables
  environment {
    variables = {
      ATHENA_DATABASE  = var.athena_database
      ATHENA_OUTPUT_S3 = var.athena_output_s3
    }
  }
}

# Optional CloudWatch log group
resource "aws_cloudwatch_log_group" "athena_query_lg" {
  name              = "/aws/lambda/${aws_lambda_function.athena_query.function_name}"
  retention_in_days = 14
}
