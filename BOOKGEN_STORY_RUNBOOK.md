# Bookgen Story Pipeline Runbook

This guide describes the recommended low-redownload setup for Bookgen:

- chapter generation with Qwen
- image generation with SDXL
- both models preloaded in a custom AMI
- ECS GPU instances that can safely scale down to `0`

## 1. Recommended strategy

For your use case, the best compromise is:

1. keep the Auto Scaling Group at `0` when idle
2. bake Qwen and SDXL caches into a custom GPU AMI
3. boot a fresh instance from that AMI when needed
4. run Qwen on the EC2 host
5. run the Bookgen worker as an ECS task on the same EC2 host

Why this is the best fit:

- no repeated large downloads from Hugging Face on every restart
- no need for a persistent single-AZ EBS volume attached to ephemeral ASG instances
- simpler than manually rebuilding the cache every time
- the instance can still disappear without losing the model cache, because the cache is part of the AMI

## 2. How the runtime is wired

Runtime layout:

- EC2 host:
  - stores the Hugging Face cache at `/opt/bookgen/hf-cache`
  - runs Qwen via vLLM on port `8000`

- ECS worker task:
  - mounts `/opt/bookgen/hf-cache`
  - uses the same cache for SDXL
  - calls Qwen through `QWEN_API_BASE_URL=http://__EC2_HOST_PRIVATE_IP__:8000/v1`

The worker resolves `__EC2_HOST_PRIVATE_IP__` through EC2 metadata at runtime.

## 3. What changed in the code

The repository is now back on Qwen for chapter generation:

- Qwen pipeline: `ml/pipelines/qwen_chapters.py`
- worker orchestration: `ml/worker/handlers.py`
- ECS worker env: `infra/ecs_task.tf`
- custom AMI override: `infra/variables.tf`, `infra/ecs_compute.tf`

The ECS launch template now supports:

- default Amazon ECS GPU AMI
- or your own custom AMI through `gpu_ami_id_override`

## 4. Important note about the current image tag

The ECS task definition now points to:

```text
433101552109.dkr.ecr.eu-west-1.amazonaws.com/bookgen-utils:ml-worker-v6
```

That means you must build and push `ml-worker-v6` before the worker can use the latest code.

## 5. Step-by-step setup

### 5.1 Prepare the worker image

From your local machine:

```powershell
cd C:\Users\ethan\Documents\moi\bookgen
docker build -f ml/worker/Dockerfile -t bookgen-utils:ml-worker-v6 .
docker tag bookgen-utils:ml-worker-v6 433101552109.dkr.ecr.eu-west-1.amazonaws.com/bookgen-utils:ml-worker-v6
cmd /c "aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin 433101552109.dkr.ecr.eu-west-1.amazonaws.com"
docker push 433101552109.dkr.ecr.eu-west-1.amazonaws.com/bookgen-utils:ml-worker-v6
```

### 5.2 Set your Hugging Face token in Terraform

In `infra/ecs_task.tf`, replace:

```text
REPLACE_WITH_HF_TOKEN
```

with your real Hugging Face token.

This token is used for SDXL and can also help when preparing the Qwen cache.

### 5.3 Apply Terraform

```powershell
cd C:\Users\ethan\Documents\moi\bookgen\infra
terraform plan
terraform apply
```

At this stage, if you do nothing else, the ASG still uses the default Amazon ECS GPU AMI.

## 6. Build the custom AMI

This is the key step that avoids repeated downloads.

### 6.1 Temporarily boot one GPU instance from the default AMI

1. set the ASG desired capacity to `1`
2. wait for the instance to become healthy
3. connect to the instance with Session Manager

### 6.2 Create the cache directory

On the instance:

```bash
sudo mkdir -p /opt/bookgen/hf-cache
sudo chown -R ssm-user:ssm-user /opt/bookgen/hf-cache
```

### 6.3 Download Qwen into the cache

Export your token:

```bash
export HF_TOKEN=hf_xxx
export HF_HOME=/opt/bookgen/hf-cache
export TRANSFORMERS_CACHE=/opt/bookgen/hf-cache
export HUGGINGFACE_HUB_CACHE=/opt/bookgen/hf-cache
```

Launch Qwen once:

```bash
sudo docker run --rm --runtime nvidia --gpus all \
  -v /opt/bookgen/hf-cache:/opt/bookgen/hf-cache \
  -e HF_TOKEN=$HF_TOKEN \
  -e HF_HOME=/opt/bookgen/hf-cache \
  -e TRANSFORMERS_CACHE=/opt/bookgen/hf-cache \
  -e HUGGINGFACE_HUB_CACHE=/opt/bookgen/hf-cache \
  -p 8000:8000 \
  --ipc=host \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-14B-Instruct-AWQ
```

Wait until the model is fully loaded once. Then stop it with `Ctrl+C`.

### 6.4 Download SDXL into the same cache

Run:

```bash
python3 - <<'PY'
from diffusers import StableDiffusionXLPipeline
import os

cache = "/opt/bookgen/hf-cache"
token = os.environ["HF_TOKEN"]

StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    token=token,
    cache_dir=cache,
)
print("SDXL cached successfully")
PY
```

If `diffusers` is not installed on the host, you can do the same through a temporary Docker container instead. The goal is simply to populate `/opt/bookgen/hf-cache`.

### 6.5 Install a startup script for Qwen

Create `/opt/bookgen/start-qwen.sh`:

```bash
cat > /opt/bookgen/start-qwen.sh <<'EOF'
#!/bin/bash
export HF_HOME=/opt/bookgen/hf-cache
export TRANSFORMERS_CACHE=/opt/bookgen/hf-cache
export HUGGINGFACE_HUB_CACHE=/opt/bookgen/hf-cache

exec /usr/bin/docker run --rm --runtime nvidia --gpus all \
  -v /opt/bookgen/hf-cache:/opt/bookgen/hf-cache \
  -e HF_HOME=/opt/bookgen/hf-cache \
  -e TRANSFORMERS_CACHE=/opt/bookgen/hf-cache \
  -e HUGGINGFACE_HUB_CACHE=/opt/bookgen/hf-cache \
  -p 8000:8000 \
  --ipc=host \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-14B-Instruct-AWQ
EOF
chmod +x /opt/bookgen/start-qwen.sh
```

### 6.6 Install a systemd service for Qwen

Create `/etc/systemd/system/bookgen-qwen.service`:

```bash
sudo bash -c 'cat > /etc/systemd/system/bookgen-qwen.service <<EOF
[Unit]
Description=Bookgen Qwen vLLM server
After=docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
ExecStart=/opt/bookgen/start-qwen.sh

[Install]
WantedBy=multi-user.target
EOF'
```

Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable bookgen-qwen.service
```

You can test it immediately:

```bash
sudo systemctl start bookgen-qwen.service
sudo systemctl status bookgen-qwen.service
curl http://127.0.0.1:8000/v1/models
```

### 6.7 Create the AMI

When Qwen service and both caches are ready:

1. go to `EC2 > Instances`
2. select the prepared GPU instance
3. choose `Actions > Image and templates > Create image`
4. give it a name like `bookgen-gpu-qwen-sdxl-v1`
5. wait until the AMI becomes `Available`

## 7. Tell Terraform to use the custom AMI

Once the AMI exists, note its AMI ID, for example:

```text
ami-0123456789abcdef0
```

Create `infra/terraform.tfvars` with:

```hcl
gpu_ami_id_override = "ami-0123456789abcdef0"
```

Then apply:

```powershell
cd C:\Users\ethan\Documents\moi\bookgen\infra
terraform apply
```

Now new ASG instances will boot from your custom AMI instead of downloading the model stack again.

## 8. Normal operating cycle

### When you want to work

1. set ASG desired capacity to `1`
2. wait for the instance to become healthy
3. the EC2 host starts Qwen automatically through systemd
4. run one ECS worker task with the latest revision
5. start the frontend locally
6. test `POST /jobs/story`

### When you want to stop costs

1. stop the ECS worker task
2. set ASG desired capacity to `0`

Because the cache is baked into the AMI, the next instance will start from the preloaded image again.

## 9. First app test

Use:

- `chapter_count = 2`
- simple prompt
- one child profile

You should then see:

- DynamoDB: `queued -> in_progress -> completed`
- S3:
  - `stories/<story_id>/brief.json`
  - `stories/<story_id>/plan.json`
  - `stories/<story_id>/manifest.json`
  - `stories/<story_id>/chapters/01.json`
  - `stories/<story_id>/chapters/01.png`
- frontend story cards with chapter text and images

## 10. What this solves and what it does not

This solves:

- repeated Qwen downloads
- repeated SDXL downloads
- dependence on a permanently running GPU instance

This does not fully solve:

- image fine-tuning workflow itself
- future LoRA artifact management
- model version upgrades, which will require creating a new AMI version
