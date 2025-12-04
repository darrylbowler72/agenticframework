# Deployment Guide - DevOps Agentic Framework

## Prerequisites

### Required Tools
- **AWS CLI** (v2.x): [Install Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html)
- **Terraform** (v1.0+): [Install Guide](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli)
- **Docker** (v20.x+): [Install Guide](https://docs.docker.com/get-docker/)
- **Python** (3.11+): [Install Guide](https://www.python.org/downloads/)
- **Node.js** (18+): [Install Guide](https://nodejs.org/)
- **Git**: [Install Guide](https://git-scm.com/downloads)

### Required Accounts & API Keys
- AWS Account with administrative access
- Anthropic API key ([Get one here](https://www.anthropic.com/))
- GitLab account and API token
- Slack workspace (optional, for chatbot)

---

## Quick Start (Local Development)

### 1. Clone the Repository

```bash
git clone https://github.com/darrylbowler72/agenticframework.git
cd agenticframework
```

### 2. Set Up Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key_here
AWS_SECRET_ACCESS_KEY=your_secret_here
ANTHROPIC_API_KEY=sk-ant-your-key-here
GITLAB_TOKEN=glpat-your-token
SLACK_BOT_TOKEN=xoxb-your-token (optional)
SLACK_SIGNING_SECRET=your-secret (optional)
```

### 3. Start Services with Docker Compose

```bash
docker-compose up -d
```

This starts:
- PostgreSQL database
- Planner Agent (port 8000)
- CodeGen Agent (port 8001)
- Remediation Agent (port 8002)
- Chatbot Agent (port 3000)

### 4. Verify Services

```bash
# Check all services are running
docker-compose ps

# Test Planner Agent
curl http://localhost:8000/health

# Test CodeGen Agent
curl http://localhost:8001/health

# Test Remediation Agent
curl http://localhost:8002/health
```

### 5. Create Your First Workflow

```bash
curl -X POST http://localhost:8000/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "template": "microservice-rest-api",
    "parameters": {
      "service_name": "test-service",
      "language": "python",
      "database": "postgresql",
      "environment": "dev"
    },
    "requested_by": "developer@example.com"
  }'
```

---

## AWS Deployment

### Step 1: Configure AWS CLI

```bash
aws configure
```

Enter your AWS credentials when prompted.

### Step 2: Create Terraform Backend

First, create the S3 bucket and DynamoDB table for Terraform state:

```bash
# Replace ACCOUNT_ID with your AWS account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create S3 bucket for Terraform state
aws s3 mb s3://dev-terraform-state-${AWS_ACCOUNT_ID} --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket dev-terraform-state-${AWS_ACCOUNT_ID} \
  --versioning-configuration Status=Enabled

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

### Step 3: Initialize Terraform

```bash
cd iac/terraform

# Update backend.tfvars with your account ID
sed -i "s/ACCOUNT_ID/${AWS_ACCOUNT_ID}/g" environments/dev/backend.tfvars

# Initialize Terraform with backend configuration
terraform init -backend-config=environments/dev/backend.tfvars
```

### Step 4: Review and Deploy Infrastructure

```bash
# Plan the deployment
terraform plan -var-file=environments/dev/terraform.tfvars

# Apply (deploy) infrastructure
terraform apply -var-file=environments/dev/terraform.tfvars
```

This creates:
- VPC with public and private subnets
- DynamoDB tables (workflows, playbooks, actions, sessions)
- S3 buckets (artifacts, templates, policies)
- EventBridge event bus
- API Gateway
- IAM roles and policies
- CloudWatch log groups

### Step 5: Store Secrets in AWS Secrets Manager

```bash
# Anthropic API Key
aws secretsmanager create-secret \
  --name dev-anthropic-api-key \
  --secret-string '{"api_key":"your-anthropic-key"}'

# GitLab Credentials
aws secretsmanager create-secret \
  --name dev-gitlab-credentials \
  --secret-string '{"url":"https://gitlab.com","token":"your-gitlab-token"}'

# Slack Credentials (optional)
aws secretsmanager create-secret \
  --name dev-slack-credentials \
  --secret-string '{"bot_token":"xoxb-your-token","signing_secret":"your-secret"}'
```

### Step 6: Deploy Lambda Functions

Package and deploy the Planner Agent:

```bash
cd ../../backend/agents/planner

# Install dependencies
pip install -r ../../requirements.txt -t .

# Create deployment package
zip -r planner-agent.zip .

# Deploy to Lambda
aws lambda create-function \
  --function-name dev-planner-agent \
  --runtime python3.11 \
  --handler main.lambda_handler \
  --role arn:aws:iam::${AWS_ACCOUNT_ID}:role/dev-lambda-execution-role \
  --zip-file fileb://planner-agent.zip \
  --timeout 300 \
  --memory-size 2048
```

Repeat for other agents (CodeGen, Remediation).

### Step 7: Configure EventBridge Rules

```bash
# Add Lambda as target for task.created events
aws events put-targets \
  --rule dev-task-created \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:${AWS_ACCOUNT_ID}:function:dev-planner-agent"
```

### Step 8: Deploy ECS Services (Optional)

For long-running agents (Remediation, Chatbot):

```bash
cd ../../ecs

# Build and push Docker images to ECR
aws ecr create-repository --repository-name remediation-agent

# Get ECR login
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -f ../backend/Dockerfile.remediation -t ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/remediation-agent:latest ..
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/remediation-agent:latest

# Deploy ECS service (use Terraform or AWS Console)
```

---

## Post-Deployment Configuration

### 1. Verify Deployment

```bash
# Get API Gateway URL from Terraform outputs
terraform output api_gateway_url

# Test health endpoint
curl https://your-api-id.execute-api.us-east-1.amazonaws.com/health
```

### 2. Create Test Workflow

```bash
curl -X POST https://your-api-id.execute-api.us-east-1.amazonaws.com/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "template": "microservice-rest-api",
    "parameters": {
      "service_name": "my-service",
      "language": "python",
      "database": "postgresql"
    },
    "requested_by": "admin@example.com"
  }'
```

### 3. Monitor Logs

```bash
# View Lambda logs
aws logs tail /aws/lambda/dev-planner-agent --follow

# View ECS logs
aws logs tail /aws/agentic-framework/dev --follow
```

### 4. Set Up Slack Bot (Optional)

1. Create Slack app at https://api.slack.com/apps
2. Add Bot Token Scopes: `chat:write`, `commands`, `im:history`
3. Install app to workspace
4. Update Secrets Manager with bot token
5. Set request URL to: `https://your-api-id.execute-api.us-east-1.amazonaws.com/slack/events`

---

## Monitoring & Operations

### CloudWatch Dashboards

View agent performance:

```bash
aws cloudwatch get-dashboard --dashboard-name agentic-framework-dev
```

### DynamoDB Queries

Check workflow status:

```bash
aws dynamodb query \
  --table-name dev-workflows \
  --key-condition-expression "workflow_id = :wf_id" \
  --expression-attribute-values '{":wf_id":{"S":"wf-12345"}}'
```

### S3 Artifacts

View generated artifacts:

```bash
aws s3 ls s3://dev-agent-artifacts-${AWS_ACCOUNT_ID}/ --recursive
```

---

## Troubleshooting

### Lambda Timeout Errors

Increase timeout in Terraform:

```hcl
timeout = 600  # 10 minutes
```

### DynamoDB Throttling

Switch to provisioned capacity or increase limits.

### EventBridge Events Not Routing

Check event patterns and targets:

```bash
aws events describe-rule --name dev-task-created
aws events list-targets-by-rule --rule dev-task-created
```

### Lambda Can't Access DynamoDB

Verify IAM role has necessary permissions:

```bash
aws iam get-role-policy --role-name dev-lambda-execution-role --policy-name DynamoDBAccess
```

---

## Updating the Deployment

### Update Lambda Code

```bash
cd backend/agents/planner
zip -r planner-agent.zip .
aws lambda update-function-code \
  --function-name dev-planner-agent \
  --zip-file fileb://planner-agent.zip
```

### Update Infrastructure

```bash
cd iac/terraform
terraform plan -var-file=environments/dev/terraform.tfvars
terraform apply -var-file=environments/dev/terraform.tfvars
```

---

## Destroying Resources

### Local Development

```bash
docker-compose down -v
```

### AWS Resources

```bash
cd iac/terraform
terraform destroy -var-file=environments/dev/terraform.tfvars
```

**Warning**: This will delete all data including DynamoDB tables and S3 buckets.

---

## Security Best Practices

1. **Use AWS IAM roles** instead of access keys where possible
2. **Enable CloudTrail** for audit logging
3. **Rotate secrets** regularly in Secrets Manager
4. **Use VPC endpoints** to avoid public internet traffic
5. **Enable encryption** for all data at rest and in transit
6. **Set up AWS Budgets** to monitor costs
7. **Use least-privilege IAM policies**
8. **Enable MFA** for AWS console access

---

## Cost Optimization

### Estimated Monthly Costs

| Service | Usage | Cost |
|---------|-------|------|
| Lambda | 1M invocations, 512MB | $5 |
| DynamoDB | On-demand, 10GB | $100 |
| S3 | 100GB storage | $25 |
| API Gateway | 1M requests | $35 |
| EventBridge | 1M events | $10 |
| CloudWatch | 50GB logs | $50 |
| **Total** | | **~$225/month** |

### Cost Reduction Tips

1. Use Lambda ARM architecture (20% cheaper)
2. Enable S3 lifecycle policies for old artifacts
3. Use DynamoDB on-demand for variable workloads
4. Set CloudWatch log retention to 30 days
5. Use Savings Plans for consistent usage

---

## Support & Resources

- **Documentation**: See `/docs` folder
- **GitHub Issues**: https://github.com/darrylbowler72/agenticframework/issues
- **Architecture**: See `architecture.md`
- **User Stories**: See `user-stories/` folder

---

## Next Steps

1. **Deploy Backstage**: Set up developer portal integration
2. **Configure ArgoCD**: Enable GitOps deployments
3. **Add more templates**: Expand the template library
4. **Set up monitoring**: Create CloudWatch dashboards
5. **Enable alerting**: Configure SNS/PagerDuty notifications
6. **Add more playbooks**: Expand remediation capabilities

---

*Last Updated*: 2025-12-03
*Version*: 1.0.0
