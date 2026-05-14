###########################################
# ECS GPU Compute: Launch Template + ASG
###########################################

data "aws_ami" "ecs_gpu" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-ecs-gpu-hvm-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

locals {
  ecs_gpu_image_id = var.gpu_ami_id_override != "" ? var.gpu_ami_id_override : data.aws_ami.ecs_gpu.id
}

resource "aws_security_group" "ecs_gpu_sg" {
  name        = "bookgen-ecs-gpu-sg"
  description = "Security group for ECS GPU instances"
  vpc_id      = aws_vpc.bookgen.id

  ingress {
    description = "Allow ECS tasks in the VPC to reach the local Qwen server"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.bookgen.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "bookgen-ecs-gpu-sg"
    Project = "bookgen"
  }
}

resource "aws_launch_template" "ecs_gpu_lt" {
  name_prefix   = "bookgen-ecs-g5-"
  image_id      = local.ecs_gpu_image_id
  instance_type = "g5.xlarge"

  iam_instance_profile {
    name = aws_iam_instance_profile.ecs_instance_profile.name
  }

  vpc_security_group_ids = [aws_security_group.ecs_gpu_sg.id]

  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 200
      volume_type           = "gp3"
      delete_on_termination = true
    }
  }

  user_data = base64encode(<<EOF
    #!/bin/bash
    set -euxo pipefail
    mkdir -p /opt/bookgen/hf-cache
    mkdir -p /etc/bookgen
    chown -R root:root /opt/bookgen
    echo "ECS_CLUSTER=${aws_ecs_cluster.bookgen_cluster.name}" >> /etc/ecs/ecs.config
    echo "ECS_ENABLE_GPU_SUPPORT=true" >> /etc/ecs/ecs.config

    cat >/etc/bookgen/qwen.env <<'ENVEOF'
HF_TOKEN=REPLACE_WITH_HF_TOKEN
HF_HOME=/opt/bookgen/hf-cache
TRANSFORMERS_CACHE=/opt/bookgen/hf-cache
HUGGINGFACE_HUB_CACHE=/opt/bookgen/hf-cache
QWEN_MODEL=Qwen/Qwen2.5-14B-Instruct-AWQ
QWEN_GPU_MEMORY_UTILIZATION=0.60
QWEN_MAX_MODEL_LEN=4096
ENVEOF

    cat >/usr/local/bin/bookgen-qwen-start.sh <<'SCRIPTEOF'
#!/bin/bash
set -euo pipefail
source /etc/bookgen/qwen.env
/usr/bin/docker rm -f bookgen-qwen >/dev/null 2>&1 || true
exec /usr/bin/docker run --rm --name bookgen-qwen \
  --runtime nvidia --gpus all \
  -v /opt/bookgen/hf-cache:/opt/bookgen/hf-cache \
  -e HF_TOKEN="$${HF_TOKEN}" \
  -e HF_HOME="$${HF_HOME}" \
  -e TRANSFORMERS_CACHE="$${TRANSFORMERS_CACHE}" \
  -e HUGGINGFACE_HUB_CACHE="$${HUGGINGFACE_HUB_CACHE}" \
  -p 8000:8000 \
  --ipc=host \
  vllm/vllm-openai:latest \
  --model "$${QWEN_MODEL}" \
  --gpu-memory-utilization "$${QWEN_GPU_MEMORY_UTILIZATION}" \
  --max-model-len "$${QWEN_MAX_MODEL_LEN}"
SCRIPTEOF
    chmod +x /usr/local/bin/bookgen-qwen-start.sh

    cat >/etc/systemd/system/bookgen-qwen.service <<'SERVICEEOF'
[Unit]
Description=Bookgen Qwen vLLM server
After=docker.service network-online.target
Wants=network-online.target
Requires=docker.service

[Service]
Type=simple
ExecStart=/usr/local/bin/bookgen-qwen-start.sh
ExecStop=/usr/bin/docker stop -t 30 bookgen-qwen
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICEEOF

    systemctl daemon-reload
    systemctl enable bookgen-qwen.service
    systemctl start bookgen-qwen.service
  EOF
  )

  tag_specifications {
    resource_type = "instance"

    tags = {
      Name    = "bookgen-ecs-gpu"
      Project = "bookgen"
    }
  }
}

resource "aws_autoscaling_group" "ecs_gpu_asg" {
  name             = "bookgen-ecs-gpu-asg"
  max_size         = 2
  min_size         = 0
  desired_capacity = 0
  vpc_zone_identifier = [
    aws_subnet.public_a.id,
    aws_subnet.public_b.id,
  ]

  launch_template {
    id      = aws_launch_template.ecs_gpu_lt.id
    version = "$Latest"
  }

  tag {
    key                 = "Name"
    value               = "bookgen-ecs-gpu"
    propagate_at_launch = true
  }

  lifecycle {
    ignore_changes = [desired_capacity]
  }
}
