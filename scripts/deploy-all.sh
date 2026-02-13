#!/bin/bash
# Master deployment script - runs all deployment steps

set -e

echo "================================================"
echo "DevOps Agentic Framework - Complete Deployment"
echo "================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}This script will:${NC}"
echo "  1. Check all prerequisites"
echo "  2. Set up Terraform backend (S3 + DynamoDB)"
echo "  3. Deploy AWS infrastructure (VPC, DynamoDB, S3, etc.)"
echo "  4. Store secrets in AWS Secrets Manager"
echo "  5. Build and push Docker images to ECR"
echo "  6. Verify deployment"
echo ""
echo -e "${YELLOW}Estimated time: 20-30 minutes${NC}"
echo -e "${YELLOW}Estimated cost: ~$200-300/month${NC}"
echo ""

read -p "Do you want to proceed? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Deployment cancelled"
    exit 0
fi

echo ""
echo "================================================"

# Step 1: Check prerequisites
echo "Step 1/6: Checking prerequisites..."
echo "================================================"
./scripts/01-check-prerequisites.sh
echo ""

# Step 2: Setup AWS backend
echo "Step 2/6: Setting up Terraform backend..."
echo "================================================"
./scripts/02-setup-aws-backend.sh
echo ""

# Step 3: Deploy infrastructure
echo "Step 3/6: Deploying infrastructure..."
echo "================================================"
./scripts/03-deploy-infrastructure.sh
echo ""

# Step 4: Store secrets
echo "Step 4/6: Storing secrets..."
echo "================================================"
./scripts/04-store-secrets.sh
echo ""

# Step 5: Deploy agents
echo "Step 5/6: Building and deploying agents..."
echo "================================================"
./scripts/05-deploy-agents.sh
echo ""

# Step 6: Verify deployment
echo "Step 6/6: Verifying deployment..."
echo "================================================"
./scripts/06-verify-deployment.sh
echo ""

# Final summary
echo "================================================"
echo -e "${GREEN}🎉 DEPLOYMENT COMPLETE! 🎉${NC}"
echo "================================================"
echo ""

# Get API URL
if [ -f "terraform-outputs.json" ]; then
    API_URL=$(cat terraform-outputs.json | jq -r '.api_gateway_url.value' 2>/dev/null)

    if [ ! -z "$API_URL" ] && [ "$API_URL" != "null" ]; then
        echo -e "${BLUE}Your API Gateway URL:${NC}"
        echo "  $API_URL"
        echo ""
    fi
fi

echo "Next steps:"
echo ""
echo "1. Test the deployment:"
echo "   curl ${API_URL:-https://your-api-url}/health"
echo ""
echo "2. Create your first workflow:"
echo "   curl -X POST ${API_URL:-https://your-api-url}/workflows \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{"
echo "       \"template\": \"microservice-rest-api\","
echo "       \"parameters\": {"
echo "         \"service_name\": \"my-service\","
echo "         \"language\": \"python\""
echo "       },"
echo "       \"requested_by\": \"admin@example.com\""
echo "     }'"
echo ""
echo "3. Monitor your resources:"
echo "   - CloudWatch Logs: aws logs tail /aws/agentic-framework/dev --follow"
echo "   - DynamoDB Tables: aws dynamodb scan --table-name dev-workflows"
echo ""
echo "4. Set up monitoring and alerts (optional):"
echo "   - Create CloudWatch dashboards"
echo "   - Configure SNS notifications"
echo "   - Set up cost alerts"
echo ""
echo "For more information, see:"
echo "  - GETTING_STARTED.md"
echo "  - DEPLOYMENT.md"
echo "  - BUILD_STATUS.md"
echo ""
echo "================================================"
