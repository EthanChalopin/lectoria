########################################
# IAM pour la Lambda API
########################################

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_api_role" {
  name               = "bookgen-lambda-api-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# Permissions de la lambda :
# - écrire dans DynamoDB BookgenStories
# - envoyer des messages dans la file SQS inference
# - écrire des logs CloudWatch
data "aws_iam_policy_document" "lambda_api_policy" {
  statement {
    actions = [
      "dynamodb:PutItem",
      "dynamodb:UpdateItem",
      "dynamodb:GetItem",
    ]
    resources = [aws_dynamodb_table.stories.arn]
  }

  statement {
    actions = [
      "sqs:SendMessage",
    ]
    resources = [aws_sqs_queue.inference.arn]
  }

  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "lambda_api_inline" {
  name   = "bookgen-lambda-api-inline"
  role   = aws_iam_role.lambda_api_role.id
  policy = data.aws_iam_policy_document.lambda_api_policy.json
}

########################################
# Lambda function : bookgen-api
########################################

data "archive_file" "lambda_api_zip" {
  type        = "zip"
  source_file = "${path.module}/../api/lambda_api.py"
  output_path = "${path.module}/lambda_api.zip"
}

resource "aws_lambda_function" "bookgen_api" {
  function_name = "bookgen-api"
  role          = aws_iam_role.lambda_api_role.arn

  runtime = "python3.12"
  handler = "lambda_api.lambda_handler"

  filename         = data.archive_file.lambda_api_zip.output_path
  source_code_hash = data.archive_file.lambda_api_zip.output_base64sha256

  timeout = 29

  environment {
    variables = {
      INFERENCE_QUEUE_URL = aws_sqs_queue.inference.url
      DDB_STORIES_TABLE   = aws_dynamodb_table.stories.name

      BUCKET_CHAPTERS = aws_s3_bucket.chapters.bucket
      BUCKET_DATASETS = aws_s3_bucket.datasets.bucket
      BUCKET_LORA     = aws_s3_bucket.lora.bucket
      BUCKET_OUTPUTS  = aws_s3_bucket.outputs.bucket
      BUCKET_UPLOADS  = aws_s3_bucket.uploads.bucket
    }
  }
}

########################################
# API Gateway HTTP (v2) devant la Lambda
########################################

resource "aws_apigatewayv2_api" "http_api" {
  name          = "bookgen-http-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.bookgen_api.arn
  payload_format_version = "2.0"
}

# Route : POST /jobs/sdxl -> Lambda
resource "aws_apigatewayv2_route" "sdxl_jobs" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /jobs/sdxl"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# Stage par défaut, auto-deploy
resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true
}

# Autoriser API Gateway à invoquer la Lambda
resource "aws_lambda_permission" "apigw_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.bookgen_api.arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}
