#!/bin/bash

###############################################################################
# Destroy Infrastructure Script
#
# Tears down all AWS infrastructure to reduce costs when not in use.
#
# WARNING: This will destroy:
# - ECS Cluster and all running services (Planner, CodeGen, Remediation, Chatbot)
# - Application Load Balancer and target groups
# - VPC, subnets, and networking resources
# - API Gateway and VPC Link
# - EventBridge event bus
# - DynamoDB tables (workflow state, sessions)
# - S3 buckets (artifacts, templates) - ONLY if empty
# - ECR repositories - ONLY if you confirm force delete
# - Secrets Manager secrets
# - CloudWatch log groups
# - IAM roles and policies
#
# NOTE: The following are NOT destroyed and will still incur minimal costs:
# - S3 buckets with content (must be manually emptied first)
# - ECR repositories with images (can be force deleted with flag)
# - Terraform state bucket (intentionally preserved)
#
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ENVIRONMENT=${ENVIRONMENT:-dev}
TERRAFORM_DIR="iac/terraform"

echo "========================================================================"
echo "  AWS Infrastructure Destroy Script"
echo "========================================================================"
echo ""
echo -e "${YELLOW}WARNING: This will destroy ALL infrastructure in the ${ENVIRONMENT} environment!${NC}"
echo ""
echo "Resources that will be destroyed:"
echo "  - ECS Cluster with all running agent services"
echo "  - Application Load Balancer and target groups"
echo "  - API Gateway HTTP API"
echo "  - VPC and all networking resources"
echo "  - DynamoDB tables (workflow-executions, chatbot-sessions)"
echo "  - EventBridge custom event bus"
echo "  - IAM roles and policies"
echo "  - CloudWatch log groups"
echo "  - Secrets Manager secrets"
echo ""
echo "Resources that will be PRESERVED (manual deletion required):"
echo "  - S3 buckets with content (must be emptied first)"
echo "  - ECR repositories with images"
echo "  - Terraform state bucket"
echo ""

# Prompt for confirmation
read -p "Are you sure you want to destroy the infrastructure? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Destroy cancelled."
    exit 0
fi

echo ""
read -p "Type the environment name '${ENVIRONMENT}' to confirm: " ENV_CONFIRM
if [ "$ENV_CONFIRM" != "$ENVIRONMENT" ]; then
    echo -e "${RED}Environment name does not match. Destroy cancelled.${NC}"
    exit 1
fi

echo ""
echo "========================================================================"
echo "Step 1: Checking Terraform state"
echo "========================================================================"

cd "$TERRAFORM_DIR"

if [ ! -f "terraform.tfstate" ] && [ ! -f ".terraform/terraform.tfstate" ]; then
    echo -e "${YELLOW}Warning: No Terraform state found. Nothing to destroy.${NC}"
    exit 0
fi

echo ""
echo "========================================================================"
echo "Step 2: Optional - Empty S3 buckets"
echo "========================================================================"
echo ""
echo "S3 buckets with content cannot be destroyed by Terraform."
echo "Would you like to empty S3 buckets now? (This will delete all objects)"
echo ""
read -p "Empty S3 buckets? (yes/no): " EMPTY_S3

if [ "$EMPTY_S3" == "yes" ]; then
    echo ""
    echo "Emptying S3 buckets..."

    # Get bucket names from Terraform output or AWS CLI
    BUCKETS=$(aws s3 ls | grep "${ENVIRONMENT}-agentic" | awk '{print $3}')

    for BUCKET in $BUCKETS; do
        if [[ "$BUCKET" == *"terraform-state"* ]]; then
            echo -e "${YELLOW}Skipping Terraform state bucket: $BUCKET${NC}"
            continue
        fi

        echo "Emptying bucket: $BUCKET"
        aws s3 rm s3://$BUCKET --recursive || true
    done

    echo -e "${GREEN}S3 buckets emptied${NC}"
fi

echo ""
echo "========================================================================"
echo "Step 3: Optional - Delete ECR images"
echo "========================================================================"
echo ""
echo "ECR repositories with images cannot be destroyed by Terraform."
echo "Would you like to delete all ECR images? (Repositories will still be preserved)"
echo ""
read -p "Delete ECR images? (yes/no): " DELETE_ECR

if [ "$DELETE_ECR" == "yes" ]; then
    echo ""
    echo "Deleting ECR images..."

    REPOS="planner-agent codegen-agent remediation-agent chatbot-agent"

    for REPO in $REPOS; do
        echo "Deleting images in ${ENVIRONMENT}-${REPO}..."

        # Get all image IDs
        IMAGE_IDS=$(aws ecr list-images \
            --repository-name "${ENVIRONMENT}-${REPO}" \
            --query 'imageIds[*]' \
            --output json 2>/dev/null || echo "[]")

        if [ "$IMAGE_IDS" != "[]" ]; then
            aws ecr batch-delete-image \
                --repository-name "${ENVIRONMENT}-${REPO}" \
                --image-ids "$IMAGE_IDS" || true
            echo -e "${GREEN}Deleted images from ${ENVIRONMENT}-${REPO}${NC}"
        else
            echo "No images found in ${ENVIRONMENT}-${REPO}"
        fi
    done
fi

echo ""
echo "========================================================================"
echo "Step 4: Scaling down ECS services (optional for faster destroy)"
echo "========================================================================"
echo ""
read -p "Scale ECS services to 0 before destroy? (Faster cleanup) (yes/no): " SCALE_DOWN

if [ "$SCALE_DOWN" == "yes" ]; then
    echo ""
    echo "Scaling down ECS services..."

    SERVICES="${ENVIRONMENT}-planner-agent ${ENVIRONMENT}-codegen-agent ${ENVIRONMENT}-remediation-agent ${ENVIRONMENT}-chatbot-agent"

    for SERVICE in $SERVICES; do
        echo "Scaling down $SERVICE..."
        aws ecs update-service \
            --cluster "${ENVIRONMENT}-agentic-cluster" \
            --service "$SERVICE" \
            --desired-count 0 \
            --region us-east-1 || true
    done

    echo "Waiting 30 seconds for services to scale down..."
    sleep 30

    echo -e "${GREEN}Services scaled down${NC}"
fi

echo ""
echo "========================================================================"
echo "Step 5: Running Terraform Destroy"
echo "========================================================================"
echo ""
echo -e "${YELLOW}Starting Terraform destroy...${NC}"
echo ""

# Run terraform destroy
terraform destroy \
    -var-file=environments/${ENVIRONMENT}/terraform.tfvars \
    -auto-approve

DESTROY_EXIT_CODE=$?

if [ $DESTROY_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "========================================================================"
    echo -e "${GREEN}Infrastructure successfully destroyed!${NC}"
    echo "========================================================================"
    echo ""
    echo "Resources that may still exist (manual cleanup if needed):"
    echo "  - S3 buckets (if they still contain objects)"
    echo "  - ECR repositories (empty but still exist)"
    echo "  - Terraform state bucket (${ENVIRONMENT}-agentic-terraform-state)"
    echo "  - CloudWatch logs (may be retained based on retention policy)"
    echo ""
    echo "Your AWS costs should now be minimal/zero for this environment."
    echo ""
else
    echo ""
    echo "========================================================================"
    echo -e "${RED}Terraform destroy encountered errors (exit code: $DESTROY_EXIT_CODE)${NC}"
    echo "========================================================================"
    echo ""
    echo "Common issues:"
    echo "  1. S3 buckets not empty - Empty them manually or rerun with empty option"
    echo "  2. ECR repositories not empty - Delete images manually or rerun with delete option"
    echo "  3. Resources in use - Wait a few minutes and try again"
    echo "  4. IAM permission issues - Verify AWS credentials have destroy permissions"
    echo ""
    echo "You can rerun this script after addressing the issues."
    echo ""
    exit $DESTROY_EXIT_CODE
fi

echo "========================================================================"
echo "Optional: Remove local Terraform state"
echo "========================================================================"
echo ""
echo "Would you like to remove local Terraform state files?"
echo "(Only do this if destroy completed successfully)"
echo ""
read -p "Remove local state? (yes/no): " REMOVE_STATE

if [ "$REMOVE_STATE" == "yes" ]; then
    echo "Removing local Terraform state..."
    rm -f terraform.tfstate terraform.tfstate.backup
    echo -e "${GREEN}Local state removed${NC}"
fi

echo ""
echo "========================================================================"
echo "Destroy Complete!"
echo "========================================================================"
echo ""
echo "The infrastructure has been destroyed. Your AWS costs should now be minimal."
echo ""
echo "To recreate the infrastructure later, run:"
echo "  bash scripts/03-deploy-infrastructure.sh"
echo ""
