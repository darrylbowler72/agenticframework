#!/bin/bash
# Script to verify AWS deployment

set -e

echo "================================================"
echo "Verifying AWS Deployment"
echo "================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Get AWS region
AWS_REGION=$(aws configure get region)
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

if [ -z "$AWS_REGION" ]; then
    AWS_REGION="us-east-1"
fi

echo -e "${BLUE}AWS Account:${NC} $AWS_ACCOUNT_ID"
echo -e "${BLUE}AWS Region:${NC} $AWS_REGION"
echo ""

ERRORS=0

# Function to check resource
check_resource() {
    RESOURCE_NAME=$1
    CHECK_COMMAND=$2

    echo -n "Checking $RESOURCE_NAME... "

    if eval $CHECK_COMMAND &>/dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        ERRORS=$((ERRORS+1))
    fi
}

# Check S3 buckets
echo "1. S3 Buckets"
echo "-----------------------------------"
check_resource "Artifacts bucket" "aws s3 ls s3://dev-agent-artifacts-${AWS_ACCOUNT_ID}"
check_resource "Templates bucket" "aws s3 ls s3://dev-codegen-templates-${AWS_ACCOUNT_ID}"
check_resource "Policies bucket" "aws s3 ls s3://dev-policy-bundles-${AWS_ACCOUNT_ID}"
check_resource "Terraform state bucket" "aws s3 ls s3://dev-terraform-state-${AWS_ACCOUNT_ID}"
echo ""

# Check DynamoDB tables
echo "2. DynamoDB Tables"
echo "-----------------------------------"
check_resource "Workflows table" "aws dynamodb describe-table --table-name dev-workflows"
check_resource "Playbooks table" "aws dynamodb describe-table --table-name dev-remediation-playbooks"
check_resource "Actions table" "aws dynamodb describe-table --table-name dev-remediation-actions"
check_resource "Sessions table" "aws dynamodb describe-table --table-name dev-chatbot-sessions"
check_resource "State lock table" "aws dynamodb describe-table --table-name terraform-state-lock"
echo ""

# Check EventBridge
echo "3. EventBridge"
echo "-----------------------------------"
check_resource "Event bus" "aws events describe-event-bus --name dev-agentic-framework"
check_resource "Task created rule" "aws events describe-rule --name dev-task-created --event-bus-name dev-agentic-framework"
check_resource "Pipeline failed rule" "aws events describe-rule --name dev-pipeline-failed --event-bus-name dev-agentic-framework"
echo ""

# Check Secrets Manager
echo "4. Secrets Manager"
echo "-----------------------------------"
check_resource "Anthropic API key" "aws secretsmanager describe-secret --secret-id dev-anthropic-api-key"
check_resource "GitLab credentials" "aws secretsmanager describe-secret --secret-id dev-gitlab-credentials"
echo ""

# Check ECR repositories
echo "5. ECR Repositories"
echo "-----------------------------------"
check_resource "Planner agent repo" "aws ecr describe-repositories --repository-names planner-agent"
check_resource "CodeGen agent repo" "aws ecr describe-repositories --repository-names codegen-agent"
check_resource "Remediation agent repo" "aws ecr describe-repositories --repository-names remediation-agent"
check_resource "Chatbot agent repo" "aws ecr describe-repositories --repository-names chatbot-agent"
echo ""

# Check CloudWatch Log Groups
echo "6. CloudWatch Log Groups"
echo "-----------------------------------"
check_resource "Main log group" "aws logs describe-log-groups --log-group-name-prefix /aws/agentic-framework"
echo ""

# Get API Gateway URL from Terraform outputs
echo "7. API Gateway"
echo "-----------------------------------"
if [ -f "terraform-outputs.json" ]; then
    API_URL=$(cat terraform-outputs.json | jq -r '.api_gateway_url.value' 2>/dev/null)

    if [ ! -z "$API_URL" ] && [ "$API_URL" != "null" ]; then
        echo -e "${GREEN}✓${NC} API Gateway URL: $API_URL"

        # Try to access health endpoint
        echo ""
        echo "Testing health endpoint..."
        if curl -s -f "${API_URL}/health" > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} Health endpoint is accessible"
            curl -s "${API_URL}/health" | jq .
        else
            echo -e "${YELLOW}!${NC} Health endpoint not accessible yet"
            echo "  This is normal if Lambda functions aren't deployed yet"
        fi
    else
        echo -e "${YELLOW}!${NC} API Gateway URL not found in outputs"
        echo "  Run: cd iac/terraform && terraform output"
    fi
else
    echo -e "${YELLOW}!${NC} Terraform outputs file not found"
    echo "  Run: cd iac/terraform && terraform output -json > ../../terraform-outputs.json"
fi
echo ""

# Summary
echo "================================================"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All resources verified successfully!${NC}"
    echo ""

    if [ ! -z "$API_URL" ] && [ "$API_URL" != "null" ]; then
        echo "Your API Gateway URL:"
        echo "  $API_URL"
        echo ""
        echo "Test with:"
        echo "  curl $API_URL/health"
        echo ""
        echo "Create a workflow:"
        echo "  curl -X POST $API_URL/workflows \\"
        echo "    -H 'Content-Type: application/json' \\"
        echo "    -d '{"
        echo "      \"template\": \"microservice-rest-api\","
        echo "      \"parameters\": {"
        echo "        \"service_name\": \"test-service\","
        echo "        \"language\": \"python\""
        echo "      },"
        echo "      \"requested_by\": \"admin@example.com\""
        echo "    }'"
        echo ""
    fi

    echo "View your resources:"
    echo "  - S3: https://s3.console.aws.amazon.com/s3/buckets?region=$AWS_REGION"
    echo "  - DynamoDB: https://console.aws.amazon.com/dynamodbv2/home?region=$AWS_REGION"
    echo "  - ECR: https://console.aws.amazon.com/ecr/repositories?region=$AWS_REGION"
    echo "  - Secrets: https://console.aws.amazon.com/secretsmanager/home?region=$AWS_REGION"
    echo ""
else
    echo -e "${RED}✗ Found $ERRORS error(s) during verification${NC}"
    echo ""
    echo "Some resources may not be created yet or there might be issues."
    echo "Check the AWS Console for more details."
    echo ""
fi
echo "================================================"
