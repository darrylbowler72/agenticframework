# Quick Deploy Guide - DevOps Agentic Framework

**Time Required**: 30 minutes
**Estimated Cost**: ~$270/month

---

## Prerequisites Check

Before starting, ensure you have:

- [ ] AWS Account with admin access
- [ ] AWS CLI installed and configured
- [ ] Docker and Docker Compose installed
- [ ] Anthropic API key ([Get one](https://console.anthropic.com/))
- [ ] GitLab token (optional but recommended)

---

## Step 1: Configure AWS Credentials (5 minutes)

### Option A: Using AWS CLI

```bash
aws configure
```

Enter when prompted:
- **AWS Access Key ID**: Your access key
- **AWS Secret Access Key**: Your secret key
- **Default region**: `us-east-1` (recommended)
- **Default output format**: `json`

### Option B: Using Environment Variables

Add to your `.env` file:
```env
AWS_ACCESS_KEY_ID=AKIA...your_key
AWS_SECRET_ACCESS_KEY=abc123...your_secret
AWS_REGION=us-east-1
```

### Verify AWS Access

```bash
# Check your credentials work
aws sts get-caller-identity

# You should see your account ID and ARN
```

---

## Step 2: Set Up Environment File (2 minutes)

```bash
# Copy example environment file
cp .env.example .env

# Edit with your favorite editor
code .env    # VS Code
# or
nano .env    # Terminal editor
```

**Required values:**
```env
# AWS (from Step 1)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...

# Anthropic Claude API (REQUIRED)
ANTHROPIC_API_KEY=sk-ant-api03-...

# GitLab (OPTIONAL but recommended)
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=glpat-...

# Slack (OPTIONAL - for chatbot)
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
```

---

## Step 3: Run Automated Deployment (20 minutes)

### On Linux/Mac:

```bash
# Run the master deployment script
./scripts/deploy-all.sh
```

### On Windows:

```bash
# Option 1: Using Git Bash (recommended)
bash scripts/deploy-all.sh

# Option 2: Using WSL
wsl bash scripts/deploy-all.sh

# Option 3: Using batch script
scripts\deploy-all.bat
```

### What the Script Does:

1. ✅ Checks prerequisites
2. ✅ Creates S3 bucket for Terraform state
3. ✅ Creates DynamoDB table for state locking
4. ✅ Deploys AWS infrastructure with Terraform
5. ✅ Stores secrets in AWS Secrets Manager
6. ✅ Builds Docker images
7. ✅ Pushes images to Amazon ECR
8. ✅ Verifies deployment

---

## Step 4: Verify Deployment (3 minutes)

After deployment completes, you'll see your API Gateway URL. Test it:

```bash
# Set your API URL (from deployment output)
export API_URL="https://abc123.execute-api.us-east-1.amazonaws.com"

# Test health endpoint
curl $API_URL/health

# Expected response:
# {"status": "healthy", "agent": "planner", "version": "1.0.0"}
```

---

## Step 5: Create Your First Workflow (2 minutes)

```bash
curl -X POST $API_URL/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "template": "microservice-rest-api",
    "parameters": {
      "service_name": "hello-world",
      "language": "python",
      "database": "postgresql",
      "environment": "dev"
    },
    "requested_by": "admin@example.com"
  }'
```

**Response:**
```json
{
  "workflow_id": "wf-abc123",
  "status": "in_progress",
  "tasks": [
    {"task_id": "t-001", "agent": "codegen", "status": "pending"},
    {"task_id": "t-002", "agent": "policy", "status": "pending"}
  ]
}
```

### Check Workflow Status

```bash
# Use the workflow_id from above
curl $API_URL/workflows/wf-abc123
```

---

## Troubleshooting

### Issue: "AWS credentials not configured"

**Solution:**
```bash
aws configure
# Or check your .env file has AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
```

### Issue: "Permission denied" on scripts

**Solution:**
```bash
chmod +x scripts/*.sh
```

### Issue: Docker daemon not running

**Solution:**
- **Windows**: Start Docker Desktop
- **Linux**: `sudo systemctl start docker`
- **Mac**: Start Docker Desktop

### Issue: Terraform backend already exists

**Solution:**
```bash
# This is OK - the script will use the existing backend
# Just proceed with the deployment
```

### Issue: API Gateway returns 404

**Solution:**
```bash
# Lambda functions may not be deployed yet
# They will be deployed in future CI/CD runs
# Or deploy manually:
cd backend/agents/planner
pip install -r ../../requirements.txt -t .
zip -r deployment.zip .
aws lambda update-function-code \
  --function-name dev-planner-agent \
  --zip-file fileb://deployment.zip
```

---

## Alternative: Manual Step-by-Step

If the automated script fails, run each step manually:

```bash
# 1. Check prerequisites
./scripts/01-check-prerequisites.sh

# 2. Set up Terraform backend
./scripts/02-setup-aws-backend.sh

# 3. Deploy infrastructure
./scripts/03-deploy-infrastructure.sh

# 4. Store secrets
./scripts/04-store-secrets.sh

# 5. Build and push images
./scripts/05-deploy-agents.sh

# 6. Verify
./scripts/06-verify-deployment.sh
```

---

## What Gets Deployed

### AWS Resources Created:

| Resource | Purpose | Monthly Cost |
|----------|---------|--------------|
| **VPC** | Network isolation | Free |
| **DynamoDB** (4 tables) | State storage | ~$100 |
| **S3** (4 buckets) | Artifact storage | ~$25 |
| **EventBridge** | Event routing | ~$10 |
| **API Gateway** | HTTP API | ~$35 |
| **ECR** (4 repos) | Docker images | ~$5 |
| **Secrets Manager** (3 secrets) | Credential storage | ~$3 |
| **CloudWatch** | Logging | ~$50 |
| **Lambda** (optional) | Agent compute | ~$50 |
| **Total** | | **~$278/month** |

---

## Next Steps After Deployment

### 1. Set Up Monitoring

```bash
# View logs
aws logs tail /aws/agentic-framework/dev --follow

# Check DynamoDB
aws dynamodb scan --table-name dev-workflows --max-items 10
```

### 2. Configure GitLab Webhooks

1. Go to your GitLab project
2. Settings → Webhooks
3. Add: `{API_URL}/webhooks/gitlab/pipeline`
4. Check "Pipeline events"

### 3. Set Up Slack Bot (Optional)

1. Create app at https://api.slack.com/apps
2. Add bot scopes: `chat:write`, `commands`, `im:history`
3. Install to workspace
4. Update secrets:
```bash
aws secretsmanager update-secret \
  --secret-id dev-slack-credentials \
  --secret-string '{"bot_token":"xoxb-...","signing_secret":"..."}'
```

### 4. Create CloudWatch Dashboard

```bash
# Create a dashboard for monitoring
aws cloudwatch put-dashboard \
  --dashboard-name agentic-framework-dev \
  --dashboard-body file://monitoring/dashboard.json
```

### 5. Set Up Cost Alerts

```bash
# Create budget alert
aws budgets create-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget file://config/budget.json
```

---

## Viewing Your Resources

### AWS Console Links

- **S3 Buckets**: https://s3.console.aws.amazon.com/s3/buckets?region=us-east-1
- **DynamoDB**: https://console.aws.amazon.com/dynamodbv2/home?region=us-east-1
- **ECR**: https://console.aws.amazon.com/ecr/repositories?region=us-east-1
- **Secrets**: https://console.aws.amazon.com/secretsmanager/home?region=us-east-1
- **CloudWatch**: https://console.aws.amazon.com/cloudwatch/home?region=us-east-1
- **API Gateway**: https://console.aws.amazon.com/apigateway/home?region=us-east-1

### CLI Commands

```bash
# List all S3 buckets
aws s3 ls | grep dev-

# List DynamoDB tables
aws dynamodb list-tables --query "TableNames[?contains(@, 'dev-')]"

# List ECR repositories
aws ecr describe-repositories --query "repositories[*].repositoryName"

# View API Gateway
aws apigateway get-rest-apis
```

---

## Cleaning Up (When Needed)

To remove all AWS resources and avoid charges:

```bash
# WARNING: This deletes everything!

# 1. Empty S3 buckets first
aws s3 rm s3://dev-agent-artifacts-${AWS_ACCOUNT_ID} --recursive
aws s3 rm s3://dev-codegen-templates-${AWS_ACCOUNT_ID} --recursive
aws s3 rm s3://dev-policy-bundles-${AWS_ACCOUNT_ID} --recursive

# 2. Destroy infrastructure
cd iac/terraform
terraform destroy -var-file=environments/dev/terraform.tfvars

# 3. Delete Terraform state bucket (optional)
aws s3 rb s3://dev-terraform-state-${AWS_ACCOUNT_ID} --force

# 4. Delete DynamoDB state lock table
aws dynamodb delete-table --table-name terraform-state-lock
```

---

## Support

If you encounter issues:

1. **Check logs**: `docker-compose logs` or CloudWatch
2. **Review documentation**: `DEPLOYMENT.md`, `GETTING_STARTED.md`
3. **GitHub Issues**: https://github.com/darrylbowler72/agenticframework/issues
4. **AWS Support**: https://console.aws.amazon.com/support/

---

## Success Checklist

After deployment, verify:

- [ ] AWS credentials work: `aws sts get-caller-identity`
- [ ] Terraform backend exists: `aws s3 ls s3://dev-terraform-state-*`
- [ ] Infrastructure deployed: `cd iac/terraform && terraform output`
- [ ] Secrets stored: `aws secretsmanager list-secrets`
- [ ] Docker images in ECR: `aws ecr describe-repositories`
- [ ] API Gateway responding: `curl $API_URL/health`
- [ ] Can create workflows: `curl -X POST $API_URL/workflows ...`

---

**🎉 Congratulations! Your DevOps Agentic Framework is deployed!**

Start creating workflows and automating your DevOps processes!
