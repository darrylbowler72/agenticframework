# Getting Started with DevOps Agentic Framework

This guide will help you get the DevOps Agentic Framework up and running in 15 minutes.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Your First Workflow](#your-first-workflow)
4. [AWS Deployment](#aws-deployment)
5. [Next Steps](#next-steps)

---

## Prerequisites

### Required Accounts
- ✅ AWS Account ([Create one](https://aws.amazon.com/))
- ✅ Anthropic API Key ([Get one](https://www.anthropic.com/))
- ✅ GitLab Account ([Sign up](https://gitlab.com/))

### Required Software
```bash
# Check if you have these installed:
docker --version          # Should be 20.x or higher
docker-compose --version  # Should be 2.x or higher
python --version          # Should be 3.11 or higher
aws --version            # Should be 2.x or higher
```

If any are missing, install them:
- **Docker**: https://docs.docker.com/get-docker/
- **Python**: https://www.python.org/downloads/
- **AWS CLI**: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html

---

## Local Development Setup

### Step 1: Clone and Configure

```bash
# Clone the repository
git clone https://github.com/darrylbowler72/agenticframework.git
cd agenticframework

# Create environment file
cp .env.example .env
```

### Step 2: Add Your Credentials

Edit the `.env` file:

```bash
# Use your favorite editor
nano .env
# or
code .env
```

Fill in these values:

```env
# AWS (get from https://console.aws.amazon.com/iam/)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...your_key...
AWS_SECRET_ACCESS_KEY=abc123...your_secret...

# Anthropic Claude (get from https://console.anthropic.com/)
ANTHROPIC_API_KEY=sk-ant-api03-...your_key...

# GitLab (get from https://gitlab.com/-/profile/personal_access_tokens)
GITLAB_TOKEN=glpat-...your_token...

# Optional: Slack (if using chatbot)
SLACK_BOT_TOKEN=xoxb-...your_token...
SLACK_SIGNING_SECRET=...your_secret...
```

### Step 3: Start the Services

```bash
# Start all services in the background
docker-compose up -d

# Watch the logs (Ctrl+C to stop watching)
docker-compose logs -f
```

Wait 30-60 seconds for all services to start.

### Step 4: Verify Everything is Running

```bash
# Check service status
docker-compose ps

# Test each agent
curl http://localhost:8000/health  # Planner Agent
curl http://localhost:8001/health  # CodeGen Agent
curl http://localhost:8002/health  # Remediation Agent
curl http://localhost:3000/health  # Chatbot Agent
```

You should see `{"status": "healthy"}` for each.

---

## Your First Workflow

### Create a Python Microservice

```bash
curl -X POST http://localhost:8000/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "template": "microservice-rest-api",
    "parameters": {
      "service_name": "hello-service",
      "language": "python",
      "database": "postgresql",
      "api_type": "rest",
      "environment": "dev"
    },
    "requested_by": "me@example.com"
  }'
```

**Response:**
```json
{
  "workflow_id": "wf-abc123def456",
  "status": "in_progress",
  "tasks": [
    {
      "task_id": "t-001",
      "agent": "codegen",
      "status": "pending",
      "description": "Generate hello-service microservice code"
    }
  ],
  "created_at": "2025-12-03T10:30:00Z"
}
```

### Check Workflow Progress

```bash
# Use the workflow_id from the response
curl http://localhost:8000/workflows/wf-abc123def456
```

### What Just Happened?

The framework:
1. **Planner Agent** decomposed your request into tasks
2. **CodeGen Agent** generated:
   - FastAPI application code
   - PostgreSQL database models
   - Dockerfile and docker-compose.yml
   - GitLab CI/CD pipeline
   - Kubernetes manifests
   - Terraform infrastructure code
   - README documentation
3. **Policy Agent** validated security compliance
4. **Deployment Agent** prepared for deployment

### Where's My Code?

- **S3 Bucket**: Artifacts stored in `dev-agent-artifacts-{your-account-id}`
- **GitLab**: Repository created (if credentials configured)
- **Local Logs**: Check `docker-compose logs codegen-agent`

---

## AWS Deployment

Once you've tested locally, deploy to AWS:

### Step 1: Configure AWS CLI

```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Default region: us-east-1
# Default output format: json
```

### Step 2: Create Terraform Backend

```bash
# Get your AWS account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Your AWS Account ID: $AWS_ACCOUNT_ID"

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

### Step 3: Deploy Infrastructure

```bash
cd iac/terraform

# Update backend config with your account ID
sed -i "s/ACCOUNT_ID/${AWS_ACCOUNT_ID}/g" environments/dev/backend.tfvars

# Initialize Terraform
terraform init -backend-config=environments/dev/backend.tfvars

# Review what will be created
terraform plan -var-file=environments/dev/terraform.tfvars

# Deploy (takes 5-10 minutes)
terraform apply -var-file=environments/dev/terraform.tfvars
```

Enter `yes` when prompted.

### Step 4: Store Secrets

```bash
# Store Anthropic API Key
aws secretsmanager create-secret \
  --name dev-anthropic-api-key \
  --secret-string "{\"api_key\":\"$ANTHROPIC_API_KEY\"}"

# Store GitLab Token
aws secretsmanager create-secret \
  --name dev-gitlab-credentials \
  --secret-string "{\"url\":\"https://gitlab.com\",\"token\":\"$GITLAB_TOKEN\"}"

# (Optional) Store Slack Credentials
aws secretsmanager create-secret \
  --name dev-slack-credentials \
  --secret-string "{\"bot_token\":\"$SLACK_BOT_TOKEN\",\"signing_secret\":\"$SLACK_SIGNING_SECRET\"}"
```

### Step 5: Get Your API Gateway URL

```bash
terraform output api_gateway_url
```

Copy this URL - you'll use it to access your agents.

### Step 6: Test AWS Deployment

```bash
# Replace with your API Gateway URL
export API_URL="https://abc123.execute-api.us-east-1.amazonaws.com"

# Test health endpoint
curl $API_URL/health

# Create a workflow
curl -X POST $API_URL/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "template": "microservice-rest-api",
    "parameters": {
      "service_name": "aws-service",
      "language": "python",
      "database": "postgresql"
    },
    "requested_by": "admin@company.com"
  }'
```

---

## Next Steps

### 1. Set Up Slack Bot (Optional)

1. Create a Slack app at https://api.slack.com/apps
2. Add scopes: `chat:write`, `commands`, `im:history`, `app_mentions:read`
3. Install to your workspace
4. Copy bot token to `.env` or Secrets Manager
5. Set request URL to: `{API_URL}/slack/events`

Test it:
```
@AgenticBot create a new service called test-api
```

### 2. Configure GitLab Webhooks

1. Go to your GitLab project → Settings → Webhooks
2. Add webhook URL: `{API_URL}/webhooks/gitlab/pipeline`
3. Check "Pipeline events"
4. Save

Now pipeline failures will auto-trigger remediation!

### 3. Integrate with Backstage (Optional)

See [backstage-plugins/README.md](backstage-plugins/README.md) for instructions.

### 4. Add Custom Templates

Create your own service templates:

```bash
cd templates/my-custom-template
# Add your template files
# See templates/python-fastapi/ for example structure
```

### 5. Customize Remediation Playbooks

Add new auto-fix strategies:

```bash
# See backend/agents/remediation/playbooks/
```

### 6. Monitor with CloudWatch

```bash
# View logs
aws logs tail /aws/agentic-framework/dev --follow

# View metrics
aws cloudwatch get-metric-statistics \
  --namespace "AgenticFramework" \
  --metric-name WorkflowsCreated \
  --start-time 2025-12-01T00:00:00Z \
  --end-time 2025-12-03T23:59:59Z \
  --period 3600 \
  --statistics Sum
```

---

## Troubleshooting

### Docker Issues

**Services won't start:**
```bash
# Check logs
docker-compose logs

# Restart services
docker-compose restart

# Nuclear option: clean restart
docker-compose down -v
docker-compose up -d
```

**Port already in use:**
```bash
# Find what's using the port
lsof -i :8000  # On Mac/Linux
netstat -ano | findstr :8000  # On Windows

# Kill the process or change port in docker-compose.yml
```

### AWS Issues

**Terraform errors:**
```bash
# Check AWS credentials
aws sts get-caller-identity

# Validate Terraform config
terraform validate

# See detailed errors
terraform apply -var-file=environments/dev/terraform.tfvars -no-color 2>&1 | tee terraform.log
```

**Lambda timeout errors:**
Increase timeout in `iac/terraform/modules/lambda/main.tf`:
```hcl
timeout = 600  # 10 minutes
```

### Agent Issues

**Agents not responding:**
```bash
# Check agent logs
docker-compose logs planner-agent
docker-compose logs codegen-agent

# Restart specific agent
docker-compose restart planner-agent

# Check if dependencies are available
curl http://localhost:5432  # PostgreSQL
```

**Claude API errors:**
- Verify API key is correct in `.env`
- Check API quota at https://console.anthropic.com/
- Ensure you have billing set up

---

## Common Questions

**Q: How much does this cost to run on AWS?**
A: Approximately $200-300/month for dev environment. See [DEPLOYMENT.md](DEPLOYMENT.md#cost-optimization) for details.

**Q: Can I use other AI models besides Claude?**
A: Yes, but you'll need to modify the agent code. Claude is recommended for best results.

**Q: Does this work with GitHub instead of GitLab?**
A: Not yet, but GitHub support is on the roadmap.

**Q: Can I run this without AWS?**
A: Yes! Use docker-compose for local development. You'll need to mock some AWS services.

**Q: How do I add support for more languages?**
A: Create a new template in `templates/` and add generation logic in `backend/agents/codegen/main.py`.

---

## Getting Help

- **Documentation**: See `/docs` folder
- **GitHub Issues**: https://github.com/darrylbowler72/agenticframework/issues
- **Discussions**: https://github.com/darrylbowler72/agenticframework/discussions
- **Architecture**: [architecture.md](architecture.md)
- **Deployment**: [DEPLOYMENT.md](DEPLOYMENT.md)

---

## Success! 🎉

You now have a fully functional AI-powered DevOps automation platform!

**What you can do:**
- ✅ Generate complete microservices in minutes
- ✅ Auto-fix broken CI/CD pipelines
- ✅ Deploy with GitOps
- ✅ Chat with your DevOps platform via Slack
- ✅ Enforce security policies automatically

**Next:** Check out the [User Stories](user-stories/) to see all capabilities!

---

*Happy DevOps Automating! 🚀*
