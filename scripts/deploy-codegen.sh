#!/bin/bash
set -e

# Deploy CodeGen Agent with versioned container image
# This script builds, pushes, and deploys a specific version to avoid image caching issues

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== CodeGen Agent Deployment Script ===${NC}"

# Check for uncommitted changes in backend/agents/codegen
cd "$PROJECT_ROOT"
if ! git diff --quiet HEAD -- backend/agents/codegen/ backend/agents/common/ || \
   ! git diff --cached --quiet HEAD -- backend/agents/codegen/ backend/agents/common/; then
    echo -e "${RED}ERROR: Uncommitted changes detected in backend/agents/codegen/ or backend/agents/common/${NC}"
    echo -e "${YELLOW}Please commit your changes before deploying to ensure the container includes all fixes.${NC}"
    echo -e "${YELLOW}Run: git status${NC}"
    exit 1
fi

# Read version from VERSION file
VERSION=$(cat "$PROJECT_ROOT/backend/VERSION" | tr -d '\n\r' | xargs)
echo -e "${GREEN}Version:${NC} $VERSION"

# Get AWS account ID and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_REGION:-us-east-1}
ENVIRONMENT=${ENVIRONMENT:-dev}

echo -e "${GREEN}AWS Account:${NC} $AWS_ACCOUNT_ID"
echo -e "${GREEN}Region:${NC} $AWS_REGION"
echo -e "${GREEN}Environment:${NC} $ENVIRONMENT"

# ECR repository details
ECR_REPO="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
IMAGE_NAME="codegen-agent"
FULL_IMAGE="$ECR_REPO/$IMAGE_NAME:$VERSION"

echo -e "\n${GREEN}Step 1: Building container image${NC}"
echo "Building: $FULL_IMAGE"
cd "$PROJECT_ROOT"
MSYS_NO_PATHCONV=1 podman build \
  --no-cache \
  -t "$IMAGE_NAME:$VERSION" \
  -f backend/Dockerfile.codegen .

echo -e "\n${GREEN}Step 2: Logging in to ECR${NC}"
MSYS_NO_PATHCONV=1 aws ecr get-login-password --region $AWS_REGION | \
  podman login --username AWS --password-stdin $ECR_REPO

echo -e "\n${GREEN}Step 3: Tagging image${NC}"
MSYS_NO_PATHCONV=1 podman tag "$IMAGE_NAME:$VERSION" "$FULL_IMAGE"

echo -e "\n${GREEN}Step 4: Pushing to ECR${NC}"
MSYS_NO_PATHCONV=1 podman push "$FULL_IMAGE"

# Verify image is in ECR
echo -e "\n${GREEN}Step 5: Verifying image in ECR${NC}"
IMAGE_DIGEST=$(aws ecr describe-images \
  --repository-name $IMAGE_NAME \
  --image-ids imageTag=$VERSION \
  --region $AWS_REGION \
  --query 'imageDetails[0].imageDigest' \
  --output text)
echo "Image pushed with digest: $IMAGE_DIGEST"

echo -e "\n${GREEN}Step 6: Updating Terraform${NC}"
cd "$PROJECT_ROOT/iac/terraform"

# Update the tfvars file with new version
sed -i "s/agent_image_version = \".*\"/agent_image_version = \"$VERSION\"/" \
  environments/$ENVIRONMENT/terraform.tfvars

# Apply Terraform changes
echo "Applying Terraform changes..."
terraform init -backend-config=environments/$ENVIRONMENT/backend.tfvars > /dev/null
terraform apply -var-file=environments/$ENVIRONMENT/terraform.tfvars -auto-approve

echo -e "\n${GREEN}Step 7: Stopping old tasks to force image refresh${NC}"
# Get running tasks for CodeGen
CLUSTER_NAME="$ENVIRONMENT-agentic-cluster"
SERVICE_NAME="$ENVIRONMENT-codegen-agent"

TASK_ARNS=$(aws ecs list-tasks \
  --cluster $CLUSTER_NAME \
  --service-name $SERVICE_NAME \
  --region $AWS_REGION \
  --query 'taskArns[]' \
  --output text)

if [ -n "$TASK_ARNS" ]; then
  for TASK_ARN in $TASK_ARNS; do
    echo "Stopping task: $TASK_ARN"
    aws ecs stop-task \
      --cluster $CLUSTER_NAME \
      --task $TASK_ARN \
      --region $AWS_REGION \
      --query 'task.taskArn' \
      --output text
  done
fi

echo -e "\n${GREEN}Step 8: Waiting for new tasks to start (60 seconds)${NC}"
sleep 60

echo -e "\n${GREEN}Step 9: Verifying deployment${NC}"
# Check service status
aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $SERVICE_NAME \
  --region $AWS_REGION \
  --query 'services[0].[serviceName,deployments[0].rolloutState,runningCount,desiredCount]' \
  --output table

# Get running task details to verify image
echo -e "\n${GREEN}Checking running task image:${NC}"
NEW_TASK_ARNS=$(aws ecs list-tasks \
  --cluster $CLUSTER_NAME \
  --service-name $SERVICE_NAME \
  --region $AWS_REGION \
  --query 'taskArns[]' \
  --output text)

if [ -n "$NEW_TASK_ARNS" ]; then
  FIRST_TASK=$(echo $NEW_TASK_ARNS | awk '{print $1}')
  TASK_IMAGE=$(aws ecs describe-tasks \
    --cluster $CLUSTER_NAME \
    --tasks $FIRST_TASK \
    --region $AWS_REGION \
    --query 'tasks[0].containers[0].image' \
    --output text)

  echo "Running task image: $TASK_IMAGE"

  if [[ "$TASK_IMAGE" == *"$VERSION"* ]]; then
    echo -e "${GREEN}✓ Deployment successful! Running version $VERSION${NC}"
  else
    echo -e "${RED}✗ Warning: Task is not running version $VERSION${NC}"
    echo -e "${YELLOW}Expected: $FULL_IMAGE${NC}"
    echo -e "${YELLOW}Actual: $TASK_IMAGE${NC}"
  fi
else
  echo -e "${YELLOW}No tasks running yet, check status in a few moments${NC}"
fi

echo -e "\n${GREEN}=== Deployment Complete ===${NC}"
echo -e "Version deployed: ${GREEN}$VERSION${NC}"
echo -e "Image: ${GREEN}$FULL_IMAGE${NC}"
echo -e "Digest: ${GREEN}$IMAGE_DIGEST${NC}"
