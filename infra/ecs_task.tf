###########################################
# ECS Task Definition - ML Worker (GPU)
###########################################

resource "aws_ecs_task_definition" "ml_worker" {
  family                   = "bookgen-ml-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["EC2"]
  cpu                      = "4096"
  memory                   = "14336"

  task_role_arn      = aws_iam_role.ecs_task_role.arn
  execution_role_arn = aws_iam_role.ecs_execution_role.arn

  volume {
    name      = "hf-cache"
    host_path = "/opt/bookgen/hf-cache"
  }

  container_definitions = jsonencode([
    {
      name      = "bookgen-ml-worker",
      image     = "433101552109.dkr.ecr.eu-west-1.amazonaws.com/bookgen-utils:ml-worker-v6",
      essential = true,

      resourceRequirements = [
        {
          type  = "GPU",
          value = "1"
        }
      ],

      environment = [
        {
          name  = "BUCKET_UPLOADS",
          value = aws_s3_bucket.uploads.bucket
        },
        {
          name  = "BUCKET_DATASETS",
          value = aws_s3_bucket.datasets.bucket
        },
        {
          name  = "BUCKET_LORA",
          value = aws_s3_bucket.lora.bucket
        },
        {
          name  = "BUCKET_CHAPTERS",
          value = aws_s3_bucket.chapters.bucket
        },
        {
          name  = "BUCKET_OUTPUTS",
          value = aws_s3_bucket.outputs.bucket
        },
        {
          name  = "INFERENCE_QUEUE_URL",
          value = aws_sqs_queue.inference.id
        },
        {
          name  = "CALLBACKS_QUEUE_URL",
          value = aws_sqs_queue.callbacks.id
        },
        {
          name  = "DDB_STORIES_TABLE",
          value = aws_dynamodb_table.stories.name
        },
        {
          name  = "AWS_REGION",
          value = "eu-west-1"
        },
        {
          name  = "HF_MODEL_ID",
          value = "stabilityai/stable-diffusion-xl-base-1.0"
        },
        {
          name  = "HF_TOKEN",
          value = "REPLACE_WITH_HF_TOKEN"
        },
        {
          name  = "HF_HOME",
          value = "/opt/bookgen/hf-cache"
        },
        {
          name  = "TRANSFORMERS_CACHE",
          value = "/opt/bookgen/hf-cache"
        },
        {
          name  = "HUGGINGFACE_HUB_CACHE",
          value = "/opt/bookgen/hf-cache"
        },
        {
          name  = "QWEN_API_BASE_URL",
          value = "http://__EC2_HOST_PRIVATE_IP__:8000/v1"
        },
        {
          name  = "QWEN_MODEL",
          value = "Qwen/Qwen2.5-14B-Instruct-AWQ"
        },
        {
          name  = "QWEN_ALLOW_STUB_FALLBACK",
          value = "0"
        },
        {
          name  = "QWEN_TIMEOUT_SECONDS",
          value = "300"
        },
        {
          name  = "QWEN_CONTROL_ENABLED",
          value = "1"
        },
        {
          name  = "QWEN_CONTROL_INSTANCE_NAME",
          value = "bookgen-ecs-gpu"
        },
        {
          name  = "QWEN_CONTROL_SERVICE_NAME",
          value = "bookgen-qwen"
        },
        {
          name  = "SDXL_DEFAULT_WIDTH",
          value = "512"
        },
        {
          name  = "SDXL_DEFAULT_HEIGHT",
          value = "512"
        },
        {
          name  = "SDXL_DEFAULT_STEPS",
          value = "20"
        },
        {
          name  = "SDXL_DEFAULT_GUIDANCE_SCALE",
          value = "6.5"
        }
      ],

      mountPoints = [
        {
          sourceVolume  = "hf-cache",
          containerPath = "/opt/bookgen/hf-cache",
          readOnly      = false
        }
      ],

      logConfiguration = {
        logDriver = "awslogs",
        options = {
          "awslogs-group"         = "/ecs/bookgen-ml-worker",
          "awslogs-region"        = "eu-west-1",
          "awslogs-stream-prefix" = "worker",
          "awslogs-create-group"  = "true"
        }
      },

      linuxParameters = {
        initProcessEnabled = true
      }
    }
  ])
}
