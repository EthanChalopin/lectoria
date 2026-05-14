# Bookgen Current Pipeline Runbook

This document explains how to get back to the current working state of Bookgen:

- prompt entered in the local frontend
- job created through API Gateway + Lambda
- job processed by the ECS GPU worker
- image generated with SDXL
- PNG uploaded to S3
- image displayed in the frontend

It is written as an operational guide so the project can be resumed quickly after a pause.

## 1. Current Architecture

The current working pipeline is:

1. Local frontend served with Vite (`frontend/`)
2. `POST /jobs/sdxl` on API Gateway
3. Lambda writes the job to DynamoDB and pushes the message to SQS
4. ECS GPU worker reads SQS
5. Worker generates a real image with SDXL on GPU
6. Worker uploads a `.png` to `bookgen-outputs`
7. Worker updates DynamoDB status
8. Frontend polls `GET /jobs/{job_id}`
9. Lambda returns a signed S3 URL
10. Frontend displays the image

## 2. Important AWS Resources

Region:

- `eu-west-1`

Main resources:

- HTTP API:
  - `https://im8j4mz3uh.execute-api.eu-west-1.amazonaws.com`
- ECS cluster:
  - `bookgen-ecs-cluster`
- ECS task definition:
  - `bookgen-ml-worker`
- Auto Scaling Group:
  - `bookgen-ecs-gpu-asg`
- Inference queue:
  - `bookgen-inference-queue`
- Callback queue:
  - `bookgen-callbacks-queue`
- DynamoDB table:
  - `BookgenStories`
- Output bucket:
  - `bookgen-outputs`
- ECR image:
  - `433101552109.dkr.ecr.eu-west-1.amazonaws.com/bookgen-utils:ml-worker-v3`

Private subnets for ECS tasks:

- `bookgen-private-a` = `subnet-04859fbed4c7f8dfd`
- `bookgen-private-b` = `subnet-01f57781460dbeeb0`

Public subnets exist, but the ECS worker task should be run in the private subnets above.

## 3. Code Pieces That Matter

Frontend:

- `frontend/`
- main app: `frontend/src/App.tsx`

Lambda API:

- `api/lambda_api.py`

Worker:

- entrypoint: `ml/worker/worker.py`
- service orchestration: `ml/worker/service.py`
- status persistence: `ml/worker/status_store.py`
- SDXL handler: `ml/worker/handlers.py`
- SDXL pipeline: `ml/pipelines/sdxl.py`
- worker Docker image: `ml/worker/Dockerfile`

Terraform:

- `infra/api_lambda.tf`
- `infra/ecs_task.tf`

## 4. What Is Working Right Now

The current pipeline already works end to end:

- the frontend can create a generation job
- the Lambda accepts the request and stores it
- the ECS worker can consume the job
- the worker generates a real image
- the worker uploads a PNG to S3
- the frontend can retrieve and display it through a signed URL

## 5. What To Shut Down When Stopping Work

To avoid GPU cost:

1. Stop the ECS worker task
2. Set the Auto Scaling Group desired capacity to `0`

Recommended shutdown procedure:

1. `ECS > Clusters > bookgen-ecs-cluster > Tasks`
2. Stop the worker task
3. `EC2 > Auto Scaling Groups > bookgen-ecs-gpu-asg`
4. Set:
   - `Desired capacity = 0`
5. Check in `EC2 > Instances` that the `g5.xlarge` disappears or terminates

## 6. How To Restart Quickly

### 6.1 Start the frontend locally

From the repo root:

```powershell
cd C:\Users\ethan\Documents\moi\bookgen\frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

Open:

```text
http://127.0.0.1:5173
```

### 6.2 Start the GPU instance

In AWS Console:

1. `EC2 > Auto Scaling Groups`
2. Open `bookgen-ecs-gpu-asg`
3. Set:

```text
Desired capacity = 1
```

Wait for the `g5.xlarge` instance to become:

- `Running`
- `2/2 status checks passed`

### 6.3 Launch the worker task

In AWS Console:

1. `ECS > Clusters > bookgen-ecs-cluster`
2. `Tasks`
3. `Run new task`

Use:

- task definition family: `bookgen-ml-worker`
- latest revision
- launch type: `EC2`
- subnets:
  - `subnet-04859fbed4c7f8dfd`
  - `subnet-01f57781460dbeeb0`

The task should become `Running`.

### 6.4 Use the frontend

In the frontend app:

- API URL:

```text
https://im8j4mz3uh.execute-api.eu-west-1.amazonaws.com
```

- write a prompt
- click `Generate Image`

## 7. How To Deploy New Code

### 7.1 Push Git changes

```powershell
git push origin main
```

### 7.2 Frontend changes

If only the frontend changed:

- restart `npm run dev`

No AWS deployment is needed for local frontend-only changes.

### 7.3 Lambda / API changes

If `api/lambda_api.py` or API Terraform changed:

```powershell
cd C:\Users\ethan\Documents\moi\bookgen\infra
terraform plan
terraform apply
```

### 7.4 Worker changes

If `ml/worker/` or `ml/pipelines/` changed:

Build and push the worker image:

```powershell
cd C:\Users\ethan\Documents\moi\bookgen
$env:DOCKER_CONFIG = "$env:TEMP\docker-bookgen-config"
docker build -f ml/worker/Dockerfile -t bookgen-utils:ml-worker-v3 .
docker tag bookgen-utils:ml-worker-v3 433101552109.dkr.ecr.eu-west-1.amazonaws.com/bookgen-utils:ml-worker-v3
docker push 433101552109.dkr.ecr.eu-west-1.amazonaws.com/bookgen-utils:ml-worker-v3
```

Then launch a new ECS task so it pulls the new image.

## 8. Required Runtime Configuration

### Hugging Face token

The worker needs `HF_TOKEN` in ECS task environment variables to download the model.

The model used right now:

```text
stabilityai/stable-diffusion-xl-base-1.0
```

Before using it:

1. accept the model license on Hugging Face
2. create a token with `Read` access
3. set:

```text
HF_TOKEN = hf_xxx...
```

in the ECS task definition revision

### SDXL defaults

Current defaults:

- width: `768`
- height: `768`
- steps: `30`
- guidance: `7.0`

These values are intentionally moderate to reduce the risk of GPU memory issues.

## 9. How To Check If The Pipeline Is Working

After clicking `Generate Image`, the normal lifecycle is:

```text
queued -> in_progress -> completed
```

### 9.1 ECS task

Check:

- `ECS > Clusters > bookgen-ecs-cluster > Tasks`

You want:

- one worker task
- status `Running`

### 9.2 Worker logs

Check:

- `CloudWatch > Logs > Log groups > /ecs/bookgen-ml-worker`

You want to see:

- `worker_start`
- `job_received`
- `job_completed`

### 9.3 DynamoDB

Check:

- `DynamoDB > Tables > BookgenStories`

You want the job item to contain:

- `status = completed`
- `output_s3_key = sdxl/<job_id>.png`

### 9.4 S3

Check:

- `S3 > bookgen-outputs > sdxl/`

You want to see:

- `<job_id>.png`

## 10. Common Problems and Fixes

### Problem: job stays `queued`

Likely causes:

- no ECS worker task is running
- ECS worker task crashed
- worker cannot reach SQS

Checks:

1. verify ECS task is `Running`
2. verify CloudWatch logs
3. verify the message is still visible in `bookgen-inference-queue`

### Problem: `sqs_receive_error` timeout

Meaning:

- the worker cannot reach SQS

Fix:

- run the ECS task in the private subnets with NAT
- do not run the task in the public subnets

### Problem: `Float types are not supported. Use Decimal types instead.`

Meaning:

- DynamoDB rejected Python floats

Fix:

- already fixed in `ml/worker/status_store.py`
- rebuild and repush the worker image if this reappears after code rollback

### Problem: `Failed to fetch` in the browser

Likely causes:

- frontend served incorrectly
- API not reachable
- browser calling the API from a bad origin

Fix:

1. run the frontend with:

```powershell
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

2. open:

```text
http://127.0.0.1:5173
```

3. verify the API URL is correct

### Problem: Hugging Face 401/403

Meaning:

- invalid or missing `HF_TOKEN`
- model license not accepted

Fix:

1. accept the model license
2. create a `Read` token
3. update `HF_TOKEN` in ECS task definition

### Problem: CUDA out of memory

Fix:

Try lighter settings in the frontend:

- width: `768`
- height: `768`
- steps: `20`
- guidance: `6.5`

If needed, go lower temporarily:

- width: `512`
- height: `512`

## 11. Fast Resume Checklist

When coming back later, do this:

1. start frontend:

```powershell
cd C:\Users\ethan\Documents\moi\bookgen\frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

2. set ASG `desired capacity = 1`
3. wait for `g5.xlarge`
4. run ECS task `bookgen-ml-worker` latest revision in private subnets
5. open `http://127.0.0.1:5173`
6. paste:

```text
https://im8j4mz3uh.execute-api.eu-west-1.amazonaws.com
```

7. generate image

## 12. Fast Stop Checklist

When stopping work:

1. stop ECS worker task
2. set ASG `desired capacity = 0`
3. verify GPU instance is gone

This is the minimum safe shutdown that keeps the whole project ready to resume quickly.
