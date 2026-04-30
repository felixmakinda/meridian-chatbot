# IAM role that lets AppRunner pull images from ECR
resource "aws_iam_role" "apprunner_ecr_access" {
  name_prefix = "${var.name}-apprunner-ecr-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "build.apprunner.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr" {
  role       = aws_iam_role.apprunner_ecr_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

resource "aws_apprunner_service" "api" {
  service_name = "${var.name}-api"

  source_configuration {
    image_repository {
      image_identifier      = "${aws_ecr_repository.app.repository_url}:latest"
      image_repository_type = "ECR"

      image_configuration {
        port = tostring(var.container_port)
        runtime_environment_variables = {
          OPENAI_API_KEY     = var.openai_api_key
          OPENROUTER_API_KEY = var.openrouter_api_key
          PORT               = tostring(var.container_port)
        }
      }
    }

    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_ecr_access.arn
    }

    # AppRunner watches ECR and redeploys on new image push
    auto_deployments_enabled = true
  }

  instance_configuration {
    cpu    = "0.5 vCPU"
    memory = "1 GB"
  }

  health_check_configuration {
    protocol = "HTTP"
    path     = "/health"
    interval = 10
  }
}
