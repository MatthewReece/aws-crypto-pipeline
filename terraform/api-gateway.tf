resource "aws_apigatewayv2_api" "crypto_api" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_methods = ["GET", "OPTIONS"]
    allow_origins = ["*"]
    allow_headers = ["content-type"]
  }
}

# Lambda integration for GET /crypto
resource "aws_apigatewayv2_integration" "crypto_integration" {
  api_id = aws_apigatewayv2_api.crypto_api.id

  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.athena_query.invoke_arn

  payload_format_version = "2.0"
}

# Route: GET /crypto
resource "aws_apigatewayv2_route" "crypto_route" {
  api_id    = aws_apigatewayv2_api.crypto_api.id
  route_key = "GET /crypto"

  target = "integrations/${aws_apigatewayv2_integration.crypto_integration.id}"
}

# API stage (auto-deploys changes)
resource "aws_apigatewayv2_stage" "crypto_stage" {
  api_id      = aws_apigatewayv2_api.crypto_api.id
  name        = "$default"
  auto_deploy = true
}

# Allow API Gateway to invoke the Lambda
resource "aws_lambda_permission" "api_gateway_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.athena_query.function_name
  principal     = "apigateway.amazonaws.com"

  # Allow *this specific API* to call the Lambda
  source_arn = "${aws_apigatewayv2_api.crypto_api.execution_arn}/*/*"
}
