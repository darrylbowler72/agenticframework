# Terraform Backend Configuration for Dev Environment
# Usage: terraform init -backend-config=environments/dev/backend.tfvars

bucket         = "dev-terraform-state-773550624765"
key            = "agenticframework/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "terraform-state-lock"
encrypt        = true
