# Bookgen DLQ Runbook (replay)

## Purpose
When `bookgen-inference-dlq` has messages, it means some jobs failed processing too many times.
This runbook explains how to inspect and safely replay them.

## 1) Inspect the DLQ
Use the AWS Console or AWS CLI to view messages in the DLQ.

CLI example (receive a sample message):
```bash
aws sqs receive-message \
  --queue-url <DLQ_URL> \
  --max-number-of-messages 1
```

## 2) Decide whether to replay
Common reasons to replay:
- A transient outage (S3/SQS/DynamoDB) is resolved.
- A bug in the worker was fixed.

If the failure is deterministic (bad payload, unsupported job_type), do not replay until fixed.

## 3) Replay to the main queue
Option A: use the SQS redrive UI in the AWS Console (recommended for one-off).

Option B: manually send the message body back to the main queue:
```bash
aws sqs send-message \
  --queue-url <INFERENCE_QUEUE_URL> \
  --message-body '<MESSAGE_BODY_JSON>'
```

## 4) Clean up
If you manually replayed a message, delete it from the DLQ:
```bash
aws sqs delete-message \
  --queue-url <DLQ_URL> \
  --receipt-handle <RECEIPT_HANDLE>
```

## Notes
- Avoid replay loops: fix the root cause before redriving.
- Keep the DLQ empty in steady state.
