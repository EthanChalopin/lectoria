###########################################
# ECS Cluster for GPU workloads
###########################################

resource "aws_ecs_cluster" "bookgen_cluster" {
  name = "bookgen-ecs-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Project = "bookgen"
  }
}
