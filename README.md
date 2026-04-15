# Bookgen

Bookgen is an asynchronous AI book-generation platform. The API receives user
requests, stores job state in DynamoDB, sends inference work to SQS, and lets GPU
workers produce artifacts in S3.

## Repository Layout

- `api/` - Lambda/API Gateway entrypoint that creates generation jobs.
- `infra/` - Terraform configuration for AWS infrastructure.
- `ml/worker/` - ECS GPU worker that consumes SQS jobs.
- `ml/pipelines/` - ML pipeline code and placeholders.
- `PROJECT_OVERVIEW.txt` - higher-level architecture notes.
- `RUNBOOK_DLQ.md` - operational notes for replaying failed SQS messages.

## Current State

The infrastructure and worker skeleton are in place. The current SDXL pipeline
is a fake implementation that writes a JSON placeholder to S3; it is intended to
be replaced by the real generation pipeline.

## Local Checks

Compile the Python files:

```bash
python -m py_compile api/lambda_api.py ml/worker/worker.py ml/pipelines/sdxl.py
```

Format Terraform:

```bash
cd infra
terraform fmt -recursive
```

## Deployment Notes

Terraform generates the Lambda zip from `api/lambda_api.py` via the
`hashicorp/archive` provider. Local zip files, virtual environments, Terraform
state, and ML model artifacts are intentionally ignored.
