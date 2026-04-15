############################
# S3 Buckets for Bookgen
############################

locals {
  bucket_prefix = "bookgen"
}

# 1. Uploads (photos envoyées par utilisateur)
resource "aws_s3_bucket" "uploads" {
  bucket = "${local.bucket_prefix}-uploads"
}

# 2. Dataset Zero123XL
resource "aws_s3_bucket" "datasets" {
  bucket = "${local.bucket_prefix}-datasets"
}

# 3. LoRA weights
resource "aws_s3_bucket" "lora" {
  bucket = "${local.bucket_prefix}-lora"
}

# 4. Chapters JSON
resource "aws_s3_bucket" "chapters" {
  bucket = "${local.bucket_prefix}-chapters"
}

# 5. Output (chapitre images + PDF final)
resource "aws_s3_bucket" "outputs" {
  bucket = "${local.bucket_prefix}-outputs"
}

############################
# Good security defaults
############################

resource "aws_s3_bucket_public_access_block" "default" {
  for_each = {
    uploads  = aws_s3_bucket.uploads.id
    datasets = aws_s3_bucket.datasets.id
    lora     = aws_s3_bucket.lora.id
    chapters = aws_s3_bucket.chapters.id
    outputs  = aws_s3_bucket.outputs.id
  }

  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_versioning" "datasets" {
  bucket = aws_s3_bucket.datasets.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_versioning" "lora" {
  bucket = aws_s3_bucket.lora.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_versioning" "chapters" {
  bucket = aws_s3_bucket.chapters.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_versioning" "outputs" {
  bucket = aws_s3_bucket.outputs.id
  versioning_configuration { status = "Enabled" }
}

