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

  container_definitions = jsonencode([
    {
      name = "bookgen-ml-worker",
      # TODO: plus tard on mettra ici ton image ECR, ex:
      # image = "${aws_ecr_repository.utils.repository_url}:latest"
      image     = "433101552109.dkr.ecr.eu-west-1.amazonaws.com/bookgen-utils:ml-worker-v3",
      essential = true,

      # On déclare ici le GPU pour ce conteneur
      resourceRequirements = [
        {
          type  = "GPU",
          value = "1"
        }
      ],

      # Variables d'environnement pour ton code Python futur
      environment = [
        # S3 buckets
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

        # SQS queues
        {
          name  = "INFERENCE_QUEUE_URL",
          value = aws_sqs_queue.inference.id
        },
        {
          name  = "CALLBACKS_QUEUE_URL",
          value = aws_sqs_queue.callbacks.id
        },

        # DynamoDB
        {
          name  = "DDB_STORIES_TABLE",
          value = aws_dynamodb_table.stories.name
        },

        # Région
        {
          name  = "AWS_REGION",
          value = "eu-west-1"
        },
        {
          name  = "HF_MODEL_ID",
          value = "stabilityai/stable-diffusion-xl-base-1.0"
        },
        {
          name  = "SDXL_DEFAULT_WIDTH",
          value = "768"
        },
        {
          name  = "SDXL_DEFAULT_HEIGHT",
          value = "768"
        },
        {
          name  = "SDXL_DEFAULT_STEPS",
          value = "30"
        },
        {
          name  = "SDXL_DEFAULT_GUIDANCE_SCALE",
          value = "7.0"
        }
      ],

      # Logs dans CloudWatch Logs
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          "awslogs-group"         = "/ecs/bookgen-ml-worker",
          "awslogs-region"        = "eu-west-1",
          "awslogs-stream-prefix" = "ecs"
          "awslogs-create-group"  = "true"
        }
      },

      linuxParameters = {
        initProcessEnabled = true
      }
    }
  ])
}
