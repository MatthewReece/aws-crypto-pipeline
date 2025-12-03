variable "aws_region" {
  description = "The AWS region to deploy resources in."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "The name of the project, used for tagging and naming resources."
  type        = string
  default     = "aws-crypto-pipeline"
}

variable "s3_bucket_name" {
  description = "The name of the S3 bucket for the data lake. Must be globally unique."
  type        = string
}

variable "coingecko_api_key_secret_arn" {
  description = "The ARN of the AWS Secrets Manager secret for the CoinGecko API key."
  type        = string
}

variable "athena_database" {
  description = "Name of the Athena database containing bitcoin_daily"
  type        = string
}

variable "athena_output_s3" {
  description = "S3 bucket/prefix where Athena stores query result CSVs"
  type        = string
}
