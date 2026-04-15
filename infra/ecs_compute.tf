###########################################
# ECS GPU Compute: Launch Template + ASG
###########################################

# AMI ECS optimisée GPU (Amazon Linux 2)
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

# Security Group pour les instances GPU
resource "aws_security_group" "ecs_gpu_sg" {
  name        = "bookgen-ecs-gpu-sg"
  description = "Security group for ECS GPU instances"
  vpc_id      = aws_vpc.bookgen.id

  # Optionnel : SSH depuis ton IP si tu veux débug sur la machine
  # Remplace 1.2.3.4/32 par ton IP si tu veux vraiment ouvrir ça
  # ou commente ce bloc si tu t'en fous pour le moment
  /*
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["1.2.3.4/32"]
  }
  */

  # Egress: tout vers l'extérieur (nécessaire pour pip, docker, S3, etc.)
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

# Launch Template pour g5.xlarge
resource "aws_launch_template" "ecs_gpu_lt" {
  name_prefix   = "bookgen-ecs-g5-"
  image_id      = data.aws_ami.ecs_gpu.id
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

  # user_data pour enregistrer l'instance dans le cluster ECS
  user_data = base64encode(<<EOF
    #!/bin/bash
    echo "ECS_CLUSTER=${aws_ecs_cluster.bookgen_cluster.name}" >> /etc/ecs/ecs.config
    echo "ECS_ENABLE_GPU_SUPPORT=true" >> /etc/ecs/ecs.config
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

# AutoScaling Group des instances GPU
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
