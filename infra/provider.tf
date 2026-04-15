terraform {
  required_version = ">= 1.5.0"

  backend "s3" {
    bucket = "bookgen-tf-state-lectoria01"
    key    = "global/terraform.tfstate"
    region = "eu-west-1"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }

    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }
}

provider "aws" {
  region = "eu-west-1"
}
