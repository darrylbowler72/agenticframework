#!/bin/bash
# Script to deploy agents to AWS using Podman (Docker alternative)

set -e

echo "================================================"
echo "Building and Deploying Agents to AWS (Podman)"
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
    exit 1
fi

if [ -z "$AWS_REGION" ]; then
    AWS_REGION="us-east-1"
fi

echo -e "${BLUE}AWS Account ID:${NC} $AWS_ACCOUNT_ID"
echo -e "${BLUE}AWS Region:${NC} $AWS_REGION"
echo ""

# ECR repository prefix
ECR_PREFIX="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Login to ECR using Podman
echo "Logging in to Amazon ECR..."
echo "-----------------------------------"
aws ecr get-login-password --region $AWS_REGION | podman login --username AWS --password-stdin $ECR_PREFIX
echo -e "${GREEN}✓ Logged in to ECR${NC}"
echo ""

# Function to create ECR repository if it doesn't exist
create_ecr_repo() {
    REPO_NAME=$1

    echo "Checking ECR repository: $REPO_NAME"

    if aws ecr describe-repositories --repository-names $REPO_NAME --region $AWS_REGION &>/dev/null; then
        echo -e "  ${YELLOW}Repository exists${NC}"
    else
        echo "  Creating repository..."
        aws ecr create-repository \
            --repository-name $REPO_NAME \
            --image-scanning-configuration scanOnPush=true \
            --region $AWS_REGION > /dev/null
        echo -e "  ${GREEN}✓ Repository created${NC}"
    fi
    echo ""
}

# Function to build and push image using Podman
build_and_push() {
    AGENT_NAME=$1
    DOCKERFILE=$2
    BUILD_CONTEXT=$3

    # Generate timestamp once for consistency
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)

    echo "Building and pushing: $AGENT_NAME"
    echo "-----------------------------------"

    # Create ECR repository
    create_ecr_repo "$AGENT_NAME-agent"

    # Build image with Podman
    echo "Building Podman image..."
    podman build -f $DOCKERFILE -t $AGENT_NAME-agent:latest $BUILD_CONTEXT

    # Tag for ECR
    podman tag $AGENT_NAME-agent:latest $ECR_PREFIX/$AGENT_NAME-agent:latest
    podman tag $AGENT_NAME-agent:latest $ECR_PREFIX/$AGENT_NAME-agent:$TIMESTAMP

    echo -e "${GREEN}✓ Image built${NC}"

    # Push to ECR
    echo "Pushing to ECR..."
    podman push $ECR_PREFIX/$AGENT_NAME-agent:latest
    podman push $ECR_PREFIX/$AGENT_NAME-agent:$TIMESTAMP

    echo -e "${GREEN}✓ Image pushed${NC}"
    echo ""
}

# Build and push all agents
echo "================================================"
echo "Building Agent Images with Podman"
echo "================================================"
echo ""

build_and_push "planner" "backend/Dockerfile.planner" "backend"
build_and_push "codegen" "backend/Dockerfile.codegen" "backend"
build_and_push "remediation" "backend/Dockerfile.remediation" "backend"

echo "================================================"
echo -e "${GREEN}✓ All agents deployed successfully!${NC}"
echo "================================================"
echo ""
echo "Deployed agents:"
echo "  - Planner Agent"
echo "  - CodeGen Agent"
echo "  - Remediation Agent"
echo ""
echo "Images pushed to:"
echo "  $ECR_PREFIX"
echo ""
echo "Next: Deploy ECS tasks to run these containers"
echo ""
