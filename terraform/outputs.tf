output "s3_bucket_id" {
  description = "The ID (name) of the S3 data lake bucket."
  value       = aws_s3_bucket.data_lake.id
}

output "lambda_function_name" {
  description = "The name of the Lambda function."
  value       = aws_lambda_function.etl_function.function_name
}

output "lambda_iam_role_arn" {
  description = "The ARN of the IAM role for the Lambda function."
  value       = aws_iam_role.lambda_exec_role.arn
}
