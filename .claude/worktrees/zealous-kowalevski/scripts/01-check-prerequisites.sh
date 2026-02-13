#!/bin/bash
# Script to check if all prerequisites are installed

set -e

echo "================================================"
echo "DevOps Agentic Framework - Prerequisites Check"
echo "================================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Function to check if command exists
check_command() {
    if command -v $1 &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 is installed"
        if [ ! -z "$2" ]; then
            VERSION=$($1 $2 2>&1)
            echo "  Version: $VERSION"
        fi
    else
        echo -e "${RED}✗${NC} $1 is NOT installed"
        echo -e "  ${YELLOW}Install from: $3${NC}"
        ERRORS=$((ERRORS+1))
    fi
    echo ""
}

# Function to check AWS credentials
check_aws_credentials() {
    if aws sts get-caller-identity &> /dev/null; then
        ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        AWS_REGION=$(aws configure get region)
        echo -e "${GREEN}✓${NC} AWS credentials are configured"
        echo "  Account ID: $ACCOUNT_ID"
        echo "  Region: $AWS_REGION"
        export AWS_ACCOUNT_ID=$ACCOUNT_ID
    else
        echo -e "${RED}✗${NC} AWS credentials are NOT configured"
        echo -e "  ${YELLOW}Run: aws configure${NC}"
        ERRORS=$((ERRORS+1))
    fi
    echo ""
}

# Function to check environment file
check_env_file() {
    if [ -f ".env" ]; then
        echo -e "${GREEN}✓${NC} .env file exists"

        # Check for required variables
        if grep -q "ANTHROPIC_API_KEY=" .env && ! grep -q "ANTHROPIC_API_KEY=your_" .env; then
            echo -e "  ${GREEN}✓${NC} ANTHROPIC_API_KEY is set"
        else
            echo -e "  ${RED}✗${NC} ANTHROPIC_API_KEY is not set"
            ERRORS=$((ERRORS+1))
        fi

        if grep -q "GITLAB_TOKEN=" .env && ! grep -q "GITLAB_TOKEN=your_" .env; then
            echo -e "  ${GREEN}✓${NC} GITLAB_TOKEN is set"
        else
            echo -e "  ${YELLOW}!${NC} GITLAB_TOKEN is not set (optional)"
        fi
    else
        echo -e "${RED}✗${NC} .env file does NOT exist"
        echo -e "  ${YELLOW}Run: cp .env.example .env${NC}"
        echo -e "  ${YELLOW}Then edit .env with your credentials${NC}"
        ERRORS=$((ERRORS+1))
    fi
    echo ""
}

# Check required tools
echo "Checking required tools..."
echo "-----------------------------------"
check_command "docker" "--version" "https://docs.docker.com/get-docker/"
check_command "docker-compose" "--version" "https://docs.docker.com/compose/install/"
check_command "aws" "--version" "https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
check_command "terraform" "--version" "https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli"
check_command "python" "--version" "https://www.python.org/downloads/"
check_command "git" "--version" "https://git-scm.com/downloads"

# Check AWS credentials
echo "Checking AWS credentials..."
echo "-----------------------------------"
check_aws_credentials

# Check environment file
echo "Checking environment configuration..."
echo "-----------------------------------"
check_env_file

# Check Docker daemon
echo "Checking Docker daemon..."
echo "-----------------------------------"
if docker info &> /dev/null; then
    echo -e "${GREEN}✓${NC} Docker daemon is running"
else
    echo -e "${RED}✗${NC} Docker daemon is NOT running"
    echo -e "  ${YELLOW}Start Docker Desktop or run: sudo systemctl start docker${NC}"
    ERRORS=$((ERRORS+1))
fi
echo ""

# Check available ports
echo "Checking required ports..."
echo "-----------------------------------"
REQUIRED_PORTS=(5432 8000 8001 8002 3000)
for PORT in "${REQUIRED_PORTS[@]}"; do
    if lsof -i:$PORT &> /dev/null || netstat -an 2>/dev/null | grep -q ":$PORT.*LISTEN"; then
        echo -e "${YELLOW}!${NC} Port $PORT is already in use"
        echo "  This may cause conflicts. Consider stopping the service using this port."
    else
        echo -e "${GREEN}✓${NC} Port $PORT is available"
    fi
done
echo ""

# Summary
echo "================================================"
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✓ All prerequisites are met!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Review your .env file and ensure all credentials are correct"
    echo "  2. Run: ./scripts/02-setup-aws-backend.sh"
    echo ""
else
    echo -e "${RED}✗ Found $ERRORS error(s)${NC}"
    echo ""
    echo "Please fix the errors above and run this script again."
    echo ""
    exit 1
fi
echo "================================================"
