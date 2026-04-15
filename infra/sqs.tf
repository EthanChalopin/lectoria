####################################
# SQS Queues for Bookgen pipeline
####################################

# Main queue: all ML jobs (Zero123XL, LoRA, SD)
resource "aws_sqs_queue" "inference" {
  name                       = "bookgen-inference-queue"
  visibility_timeout_seconds = 1800  # 30 min for GPU worker
  message_retention_seconds  = 86400 # 24h
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.inference_dlq.arn
    maxReceiveCount     = 5
  })
}

# Secondary queue: result messages
resource "aws_sqs_queue" "callbacks" {
  name                       = "bookgen-callbacks-queue"
  visibility_timeout_seconds = 60
  message_retention_seconds  = 86400
}

####################################
# DLQ
####################################

resource "aws_sqs_queue" "inference_dlq" {
  name                       = "bookgen-inference-dlq"
  visibility_timeout_seconds = 1800
  message_retention_seconds  = 1209600 # 14 days
}

####################################
# CloudWatch Alarm
####################################

resource "aws_cloudwatch_metric_alarm" "inference_dlq_visible" {
  alarm_name          = "bookgen-inference-dlq-visible"
  alarm_description   = "DLQ has visible messages (should be zero)."
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = aws_sqs_queue.inference_dlq.name
  }
}

####################################
# Outputs
####################################

output "sqs_inference_queue_url" {
  value = aws_sqs_queue.inference.id
}

output "sqs_callbacks_queue_url" {
  value = aws_sqs_queue.callbacks.id
}

output "sqs_inference_dlq_url" {
  value = aws_sqs_queue.inference_dlq.id
}
