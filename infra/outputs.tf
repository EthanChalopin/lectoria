output "vpc_id" {
  description = "ID du VPC principal Bookgen"
  value       = aws_vpc.bookgen.id
}

output "public_subnet_ids" {
  description = "IDs des subnets publics"
  value = [
    aws_subnet.public_a.id,
    aws_subnet.public_b.id
  ]
}

output "public_subnet_azs" {
  description = "Zones de dispo des subnets publics"
  value = [
    aws_subnet.public_a.availability_zone,
    aws_subnet.public_b.availability_zone
  ]
}
output "http_api_url" {
  description = "URL publique de l'API HTTP Bookgen"
  value       = aws_apigatewayv2_api.http_api.api_endpoint
}
