####################################
# ECR Repositories for ML workers
####################################

# Worker Zero123XL (génère les 8 vues)
resource "aws_ecr_repository" "zero123xl" {
  name = "bookgen-zero123xl"
  image_scanning_configuration {
    scan_on_push = true
  }
}

# Worker LoRA training
resource "aws_ecr_repository" "lora_train" {
  name = "bookgen-lora-train"
  image_scanning_configuration {
    scan_on_push = true
  }
}

# Worker SDXL inference (10 images finales)
resource "aws_ecr_repository" "sd_infer" {
  name = "bookgen-sd-infer"
  image_scanning_configuration {
    scan_on_push = true
  }
}

# Utils (préparation dataset, PDF, nettoyage images…)
resource "aws_ecr_repository" "utils" {
  name = "bookgen-utils"
  image_scanning_configuration {
    scan_on_push = true
  }
}

####################################
# Outputs
####################################

output "ecr_urls" {
  value = {
    zero123xl  = aws_ecr_repository.zero123xl.repository_url
    lora_train = aws_ecr_repository.lora_train.repository_url
    sd_infer   = aws_ecr_repository.sd_infer.repository_url
    utils      = aws_ecr_repository.utils.repository_url
  }
}
