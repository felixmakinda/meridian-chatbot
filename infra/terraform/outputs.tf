output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.app.repository_url
}

output "alb_dns_name" {
  description = "ALB DNS name"
  value       = aws_lb.app.dns_name
}

output "service_url" {
  description = "Base URL for the service"
  value       = "http://${aws_lb.app.dns_name}"
}

