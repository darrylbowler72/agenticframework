#!/bin/bash
# Interactive setup script to collect credentials and configure .env file

set -e

echo "================================================"
echo "DevOps Agentic Framework - Interactive Setup"
echo "Environment: Development (dev)"
echo "================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}This script will help you configure all credentials.${NC}"
echo ""
echo "You'll need:"
echo "  1. AWS Access Key ID and Secret Access Key"
echo "  2. Anthropic API Key (required)"
echo "  3. GitLab Token (optional but recommended)"
echo "  4. Slack Bot Token and Signing Secret (optional)"
echo ""
echo "See SETUP_CREDENTIALS.md for detailed instructions on getting these."
echo ""

read -p "Press Enter to continue or Ctrl+C to exit..."
echo ""

# Create .env file from template
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ Created .env file from template${NC}"
else
    echo -e "${YELLOW}! .env file already exists, will update it${NC}"
fi
echo ""

# Function to prompt for credential
prompt_credential() {
    local var_name=$1
    local display_name=$2
    local is_secret=$3
    local is_required=$4
    local example=$5

    echo "-----------------------------------"
    echo -e "${BLUE}$display_name${NC}"
    if [ ! -z "$example" ]; then
        echo "Example: $example"
    fi

    if [ "$is_required" = "true" ]; then
        echo -e "${YELLOW}(Required)${NC}"
    else
        echo -e "(Optional - press Enter to skip)"
    fi

    if [ "$is_secret" = "true" ]; then
        read -s -p "Enter $display_name: " value
        echo ""
    else
        read -p "Enter $display_name: " value
    fi

    if [ -z "$value" ] && [ "$is_required" = "true" ]; then
        echo -e "${RED}Error: This credential is required${NC}"
        prompt_credential "$var_name" "$display_name" "$is_secret" "$is_required" "$example"
        return
    fi

    if [ ! -z "$value" ]; then
        # Update .env file
        if grep -q "^${var_name}=" .env; then
            sed -i.bak "s|^${var_name}=.*|${var_name}=${value}|" .env
        else
            echo "${var_name}=${value}" >> .env
        fi
        echo -e "${GREEN}✓ Saved${NC}"
    else
        echo -e "${YELLOW}⊘ Skipped${NC}"
    fi
    echo ""
}

echo "================================================"
echo "1. AWS Credentials"
echo "================================================"
echo ""
echo "Get these from: https://console.aws.amazon.com/iam/"
echo ""

prompt_credential "AWS_ACCESS_KEY_ID" "AWS Access Key ID" false true "AKIAIOSFODNN7EXAMPLE"
prompt_credential "AWS_SECRET_ACCESS_KEY" "AWS Secret Access Key" true true "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"

# Ask for region
echo "-----------------------------------"
echo -e "${BLUE}AWS Region${NC}"
echo "Recommended: us-east-1 (press Enter for default)"
read -p "Enter AWS Region [us-east-1]: " aws_region
aws_region=${aws_region:-us-east-1}
sed -i.bak "s|^AWS_REGION=.*|AWS_REGION=${aws_region}|" .env
echo -e "${GREEN}✓ Saved: $aws_region${NC}"
echo ""

echo "================================================"
echo "2. Anthropic API Key"
echo "================================================"
echo ""
echo "Get this from: https://console.anthropic.com/"
echo ""

prompt_credential "ANTHROPIC_API_KEY" "Anthropic API Key" true true "sk-ant-api03-..."

echo "================================================"
echo "3. GitLab Token (Optional)"
echo "================================================"
echo ""
echo "Get this from: https://gitlab.com/-/profile/personal_access_tokens"
echo "Required for: Repository creation, CI/CD webhooks"
echo ""

prompt_credential "GITLAB_TOKEN" "GitLab Personal Access Token" true false "glpat-..."

echo "================================================"
echo "4. Slack Bot Credentials (Optional)"
echo "================================================"
echo ""
echo "Get these from: https://api.slack.com/apps"
echo "Required for: Chatbot natural language interface"
echo ""

prompt_credential "SLACK_BOT_TOKEN" "Slack Bot Token" true false "xoxb-..."
prompt_credential "SLACK_SIGNING_SECRET" "Slack Signing Secret" true false "abc123..."

# Clean up backup files
rm -f .env.bak

echo "================================================"
echo -e "${GREEN}✓ Configuration Complete!${NC}"
echo "================================================"
echo ""

echo "Your .env file has been configured with:"
echo "  ✓ AWS credentials"
echo "  ✓ Anthropic API key"
if grep -q "^GITLAB_TOKEN=glpat-" .env; then
    echo "  ✓ GitLab token"
else
    echo "  ⊘ GitLab token (skipped)"
fi
if grep -q "^SLACK_BOT_TOKEN=xoxb-" .env; then
    echo "  ✓ Slack bot credentials"
else
    echo "  ⊘ Slack bot credentials (skipped)"
fi
echo ""

# Configure AWS CLI
echo "Now configuring AWS CLI..."
echo ""
AWS_ACCESS_KEY=$(grep "^AWS_ACCESS_KEY_ID=" .env | cut -d '=' -f2)
AWS_SECRET_KEY=$(grep "^AWS_SECRET_ACCESS_KEY=" .env | cut -d '=' -f2)
AWS_REGION=$(grep "^AWS_REGION=" .env | cut -d '=' -f2)

# Create AWS credentials file
mkdir -p ~/.aws
cat > ~/.aws/credentials <<EOF
[default]
aws_access_key_id = $AWS_ACCESS_KEY
aws_secret_access_key = $AWS_SECRET_KEY
EOF

cat > ~/.aws/config <<EOF
[default]
region = $AWS_REGION
output = json
EOF

echo -e "${GREEN}✓ AWS CLI configured${NC}"
echo ""

# Verify AWS credentials
echo "Verifying AWS credentials..."
if aws sts get-caller-identity &>/dev/null; then
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    echo -e "${GREEN}✓ AWS credentials verified${NC}"
    echo "  Account ID: $ACCOUNT_ID"
    echo "  Region: $AWS_REGION"
else
    echo -e "${RED}✗ Could not verify AWS credentials${NC}"
    echo "  Please check your Access Key and Secret Key"
fi
echo ""

echo "================================================"
echo "Next Steps:"
echo "================================================"
echo ""
echo "1. Test locally (optional):"
echo "   docker-compose up -d"
echo "   curl http://localhost:8000/health"
echo ""
echo "2. Deploy to AWS:"
echo "   bash scripts/deploy-all.sh"
echo ""
echo "3. Or run step by step:"
echo "   bash scripts/01-check-prerequisites.sh"
echo "   bash scripts/02-setup-aws-backend.sh"
echo "   bash scripts/03-deploy-infrastructure.sh"
echo ""
echo "See SETUP_CREDENTIALS.md for more information."
echo ""
echo "================================================"
