#!/bin/bash
# Script to set up Terraform backend (S3 bucket and DynamoDB table)

set -e

echo "================================================"
echo "Setting Up Terraform Backend"
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

if [ -z "$AWS_REGION" ]; then
    echo -e "${YELLOW}Warning: No default region set, using us-east-1${NC}"
    AWS_REGION="us-east-1"
fi

echo -e "${BLUE}AWS Account ID:${NC} $AWS_ACCOUNT_ID"
echo -e "${BLUE}AWS Region:${NC} $AWS_REGION"
echo ""

# Set variables
BUCKET_NAME="dev-terraform-state-${AWS_ACCOUNT_ID}"
DYNAMODB_TABLE="terraform-state-lock"

# Create S3 bucket for Terraform state
echo "Creating S3 bucket: $BUCKET_NAME"
echo "-----------------------------------"

if aws s3 ls "s3://$BUCKET_NAME" 2>&1 | grep -q 'NoSuchBucket'; then
    if [ "$AWS_REGION" == "us-east-1" ]; then
        aws s3 mb "s3://$BUCKET_NAME" --region $AWS_REGION
    else
        aws s3 mb "s3://$BUCKET_NAME" --region $AWS_REGION --create-bucket-configuration LocationConstraint=$AWS_REGION
    fi
    echo -e "${GREEN}✓ Bucket created successfully${NC}"
else
    echo -e "${YELLOW}! Bucket already exists${NC}"
fi
echo ""

# Enable versioning on the bucket
echo "Enabling versioning..."
aws s3api put-bucket-versioning \
    --bucket $BUCKET_NAME \
    --versioning-configuration Status=Enabled
echo -e "${GREEN}✓ Versioning enabled${NC}"
echo ""

# Enable encryption
echo "Enabling encryption..."
aws s3api put-bucket-encryption \
    --bucket $BUCKET_NAME \
    --server-side-encryption-configuration '{
        "Rules": [{
            "ApplyServerSideEncryptionByDefault": {
                "SSEAlgorithm": "AES256"
            }
        }]
    }'
echo -e "${GREEN}✓ Encryption enabled${NC}"
echo ""

# Block public access
echo "Blocking public access..."
aws s3api put-public-access-block \
    --bucket $BUCKET_NAME \
    --public-access-block-configuration \
        "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
echo -e "${GREEN}✓ Public access blocked${NC}"
echo ""

# Create DynamoDB table for state locking
echo "Creating DynamoDB table: $DYNAMODB_TABLE"
echo "-----------------------------------"

if aws dynamodb describe-table --table-name $DYNAMODB_TABLE --region $AWS_REGION &>/dev/null; then
    echo -e "${YELLOW}! Table already exists${NC}"
else
    aws dynamodb create-table \
        --table-name $DYNAMODB_TABLE \
        --attribute-definitions AttributeName=LockID,AttributeType=S \
        --key-schema AttributeName=LockID,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region $AWS_REGION

    echo "Waiting for table to be active..."
    aws dynamodb wait table-exists --table-name $DYNAMODB_TABLE --region $AWS_REGION
    echo -e "${GREEN}✓ Table created successfully${NC}"
fi
echo ""

# Update backend.tfvars with account ID
echo "Updating Terraform backend configuration..."
BACKEND_FILE="iac/terraform/environments/dev/backend.tfvars"

if [ -f "$BACKEND_FILE" ]; then
    # Create backup
    cp $BACKEND_FILE ${BACKEND_FILE}.backup

    # Update the file
    sed -i.bak "s/ACCOUNT_ID/${AWS_ACCOUNT_ID}/g" $BACKEND_FILE
    sed -i.bak "s/us-east-1/${AWS_REGION}/g" $BACKEND_FILE
    rm ${BACKEND_FILE}.bak

    echo -e "${GREEN}✓ Backend configuration updated${NC}"
    echo ""
    echo "Updated file: $BACKEND_FILE"
    echo "-----------------------------------"
    cat $BACKEND_FILE
else
    echo -e "${RED}Error: Backend configuration file not found${NC}"
    exit 1
fi
echo ""

# Summary
echo "================================================"
echo -e "${GREEN}✓ Terraform backend setup complete!${NC}"
echo ""
echo "Resources created:"
echo "  - S3 Bucket: $BUCKET_NAME"
echo "  - DynamoDB Table: $DYNAMODB_TABLE"
echo ""
echo "Next steps:"
echo "  1. Run: ./scripts/03-deploy-infrastructure.sh"
echo ""
echo "================================================"
