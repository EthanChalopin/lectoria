variable "gpu_ami_id_override" {
  description = "Optional custom AMI ID for ECS GPU instances. Leave empty to use the latest Amazon ECS GPU AMI."
  type        = string
  default     = ""
}
