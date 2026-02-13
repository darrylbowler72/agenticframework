#!/bin/bash
# Script to deploy AWS infrastructure using Terraform

set -e

echo "================================================"
echo "Deploying AWS Infrastructure with Terraform"
echo "================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get AWS account ID and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
AWS_REGION=$(aws configure get region)

if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo -e "${RED}Error: Could not get AWS account ID${NC}"
    echo "Please run: aws configure"
    exit 1
fi

echo -e "${BLUE}AWS Account ID:${NC} $AWS_ACCOUNT_ID"
echo -e "${BLUE}AWS Region:${NC} $AWS_REGION"
echo ""

# Navigate to Terraform directory
cd iac/terraform

# Initialize Terraform
echo "Initializing Terraform..."
echo "-----------------------------------"
terraform init -backend-config=environments/dev/backend.tfvars
echo -e "${GREEN}✓ Terraform initialized${NC}"
echo ""

# Validate Terraform configuration
echo "Validating Terraform configuration..."
echo "-----------------------------------"
terraform validate
echo -e "${GREEN}✓ Configuration is valid${NC}"
echo ""

# Format Terraform files
echo "Formatting Terraform files..."
terraform fmt -recursive
echo -e "${GREEN}✓ Files formatted${NC}"
echo ""

# Create Terraform plan
echo "Creating Terraform plan..."
echo "-----------------------------------"
terraform plan -var-file=environments/dev/terraform.tfvars -out=tfplan
echo ""

# Ask for confirmation
echo "================================================"
echo -e "${YELLOW}Review the plan above.${NC}"
echo ""
echo "This will create the following AWS resources:"
echo "  - VPC with public and private subnets"
echo "  - 4 DynamoDB tables (workflows, playbooks, actions, sessions)"
echo "  - 4 S3 buckets (artifacts, templates, policies, terraform-state)"
echo "  - EventBridge event bus"
echo "  - API Gateway"
echo "  - IAM roles and policies"
echo "  - CloudWatch log groups"
echo "  - Secrets Manager secrets (empty, you'll populate later)"
echo ""
echo -e "${BLUE}Estimated monthly cost: ~$200-300${NC}"
echo ""

read -p "Do you want to proceed with deployment? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Deployment cancelled${NC}"
    exit 0
fi

# Apply Terraform plan
echo ""
echo "Applying Terraform plan..."
echo "-----------------------------------"
terraform apply tfplan
echo ""

# Get outputs
echo "================================================"
echo -e "${GREEN}✓ Infrastructure deployed successfully!${NC}"
echo ""
echo "Terraform Outputs:"
echo "-----------------------------------"
terraform output
echo ""

# Save outputs to file
terraform output -json > ../../terraform-outputs.json
echo -e "${GREEN}✓ Outputs saved to terraform-outputs.json${NC}"
echo ""

# Return to root directory
cd ../..

# Summary
echo "================================================"
echo -e "${GREEN}Infrastructure Deployment Complete!${NC}"
echo ""
echo "Resources created in AWS account: $AWS_ACCOUNT_ID"
echo "Region: $AWS_REGION"
echo ""
echo "Next steps:"
echo "  1. Run: ./scripts/04-store-secrets.sh"
echo "  2. Then: ./scripts/05-deploy-agents.sh"
echo ""
echo "================================================"
