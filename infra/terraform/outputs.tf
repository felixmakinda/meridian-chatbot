output "ecr_repository_url" {
  description = "ECR repository URL for the API image"
  value       = aws_ecr_repository.app.repository_url
}

output "apprunner_url" {
  description = "AppRunner service URL (backend API)"
  value       = "https://${aws_apprunner_service.api.service_url}"
}

output "cloudfront_url" {
  description = "CloudFront URL (frontend)"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "s3_bucket" {
  description = "S3 bucket name for frontend static files"
  value       = aws_s3_bucket.frontend.bucket
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (needed for cache invalidation in CI)"
  value       = aws_cloudfront_distribution.frontend.id
}
