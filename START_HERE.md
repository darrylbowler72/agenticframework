# 🚀 START HERE - DevOps Agentic Framework Setup

**Environment**: Development (dev)
**Time to Deploy**: 45 minutes
**Cost**: ~$270/month

---

## 📋 What You Need

Before starting, you'll need to obtain these credentials:

| Service | Required | Get It From | Time |
|---------|----------|-------------|------|
| **AWS** | ✅ Yes | https://console.aws.amazon.com/iam/ | 5 min |
| **Anthropic** | ✅ Yes | https://console.anthropic.com/ | 3 min |
| **GitLab** | ⚠️ Recommended | https://gitlab.com/-/profile/personal_access_tokens | 3 min |
| **Slack** | ⚠️ Optional | https://api.slack.com/apps | 5 min |

**Don't have these yet?** See detailed instructions in: **[SETUP_CREDENTIALS.md](SETUP_CREDENTIALS.md)**

---

## 🎯 Quick Setup (3 Options)

### ⚡ Option 1: Interactive Setup (Easiest)

**Best for**: First-time setup, guided experience

```bash
# Run interactive setup script
bash scripts/interactive-setup.sh
```

This will:
- ✅ Guide you through entering each credential
- ✅ Create and configure your .env file
- ✅ Set up AWS CLI automatically
- ✅ Verify your credentials work

**Then deploy:**
```bash
bash scripts/deploy-all.sh
```

---

### 🚀 Option 2: Manual Setup (You Have Credentials)

**Best for**: If you already have all credentials ready

**Step 1**: Create .env file
```bash
cp .env.example .env
```

**Step 2**: Edit .env with your credentials
```bash
# Windows
notepad .env

# Mac/Linux or VS Code
code .env
```

Fill in your actual values:
```env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...your_actual_key
AWS_SECRET_ACCESS_KEY=...your_actual_secret
ANTHROPIC_API_KEY=sk-ant-api03-...your_actual_key
GITLAB_TOKEN=glpat-...your_token
SLACK_BOT_TOKEN=xoxb-...your_token
SLACK_SIGNING_SECRET=...your_secret
```

**Step 3**: Configure AWS CLI
```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Default region: us-east-1
# Default output: json
```

**Step 4**: Deploy
```bash
bash scripts/deploy-all.sh
```

---

### 🧪 Option 3: Local Testing Only (No AWS Yet)

**Best for**: Testing locally before AWS deployment

**Step 1**: Create minimal .env
```bash
cp .env.example .env
```

**Step 2**: Edit .env - only need Anthropic key
```env
ANTHROPIC_API_KEY=sk-ant-api03-...your_key
```

**Step 3**: Start local services
```bash
docker-compose up -d
```

**Step 4**: Test
```bash
curl http://localhost:8000/health
```

---

## 📖 Detailed Credential Setup

### Need help getting credentials?

See **[SETUP_CREDENTIALS.md](SETUP_CREDENTIALS.md)** for detailed step-by-step instructions with screenshots for:

1. **AWS Credentials** - Creating access keys in IAM console
2. **Anthropic API Key** - Signing up and creating API key
3. **GitLab Token** - Creating personal access token
4. **Slack Bot** - Creating app and getting bot token

---

## ✅ Verify Setup

After configuring credentials, verify everything:

```bash
# Check prerequisites
bash scripts/01-check-prerequisites.sh
```

This checks:
- ✅ Required tools installed (Docker, AWS CLI, Terraform)
- ✅ AWS credentials configured
- ✅ .env file exists and has required keys
- ✅ Docker daemon running
- ✅ Required ports available

---

## 🚀 Deployment Steps

Once credentials are set up:

### Automated Deployment (Recommended)

```bash
bash scripts/deploy-all.sh
```

This runs all steps automatically:
1. ✅ Checks prerequisites
2. ✅ Creates Terraform backend (S3 + DynamoDB)
3. ✅ Deploys AWS infrastructure (~20 min)
4. ✅ Stores secrets in AWS Secrets Manager
5. ✅ Builds and pushes Docker images
6. ✅ Verifies deployment

### Manual Step-by-Step

If you prefer to run each step:

```bash
# Step 1: Check prerequisites
bash scripts/01-check-prerequisites.sh

# Step 2: Set up Terraform backend
bash scripts/02-setup-aws-backend.sh

# Step 3: Deploy infrastructure
bash scripts/03-deploy-infrastructure.sh

# Step 4: Store secrets
bash scripts/04-store-secrets.sh

# Step 5: Build and deploy agents
bash scripts/05-deploy-agents.sh

# Step 6: Verify deployment
bash scripts/06-verify-deployment.sh
```

---

## 🎉 After Deployment

### Test Your Deployment

You'll get an API Gateway URL like:
```
https://abc123.execute-api.us-east-1.amazonaws.com
```

**Test it:**
```bash
# Health check
curl https://YOUR-API-URL/health

# Create first workflow
curl -X POST https://YOUR-API-URL/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "template": "microservice-rest-api",
    "parameters": {
      "service_name": "hello-world",
      "language": "python",
      "database": "postgresql"
    },
    "requested_by": "admin@example.com"
  }'
```

### What You Can Do

✅ **Generate microservices** in <5 minutes
✅ **Auto-fix broken pipelines** with AI
✅ **Chat with DevOps bot** via Slack
✅ **Event-driven workflows** across agents

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| **START_HERE.md** | 👉 This file - Quick start |
| **SETUP_CREDENTIALS.md** | Detailed credential setup guide |
| **QUICK_DEPLOY.md** | 30-minute deployment guide |
| **GETTING_STARTED.md** | Complete tutorial |
| **DEPLOYMENT.md** | Full AWS deployment reference |
| **BUILD_STATUS.md** | What's built and ready |

---

## 🆘 Troubleshooting

### Issue: "Unable to locate credentials"

**Solution**: Run the interactive setup:
```bash
bash scripts/interactive-setup.sh
```

Or manually configure:
```bash
aws configure
```

### Issue: "Docker daemon not running"

**Solution**: Start Docker Desktop and wait for it to be fully running.

### Issue: "Terraform command not found"

**Solution**: You have it installed (v1.13.3), try restarting your terminal.

### Issue: "ANTHROPIC_API_KEY not set"

**Solution**:
1. Get API key from https://console.anthropic.com/
2. Add to .env file:
```env
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

### Issue: Scripts won't run on Windows

**Solution**: Use Git Bash:
```bash
bash scripts/deploy-all.sh
```

Or install Git for Windows: https://git-scm.com/download/win

---

## 💰 Cost Breakdown

### AWS Resources (~$270/month)

| Service | Monthly Cost |
|---------|--------------|
| DynamoDB (4 tables) | $100 |
| S3 Storage | $25 |
| API Gateway | $35 |
| CloudWatch Logs | $50 |
| Lambda/ECS | $50 |
| Other (EventBridge, ECR) | $10 |

### Anthropic API (~$5-20/month)
- Free $5 credit for new users
- Pay as you go: ~$0.01-0.03 per request

### Total: ~$275-290/month for dev

**Can be reduced:**
- Use AWS free tier (first 12 months)
- Lambda ARM64 (20% cheaper)
- Shorter log retention periods
- Turn off resources when not in use

---

## 🎯 Success Checklist

After setup, you should have:

- [ ] .env file with all credentials
- [ ] AWS CLI configured: `aws sts get-caller-identity` works
- [ ] Docker running: `docker ps` works
- [ ] Prerequisites passing: `bash scripts/01-check-prerequisites.sh` ✓
- [ ] Infrastructure deployed: Terraform outputs show API URL
- [ ] Health check passes: `curl API_URL/health` returns 200
- [ ] Can create workflows: POST request succeeds

---

## 🚀 Ready to Start?

### If you have credentials:
```bash
bash scripts/interactive-setup.sh
bash scripts/deploy-all.sh
```

### If you need credentials first:
1. Read: **[SETUP_CREDENTIALS.md](SETUP_CREDENTIALS.md)**
2. Get AWS, Anthropic, GitLab, Slack credentials
3. Come back and run setup scripts

### Want to test locally first:
```bash
# Minimal .env with just Anthropic key
docker-compose up -d
curl http://localhost:8000/health
```

---

## 📞 Need Help?

- **Credential Setup**: See SETUP_CREDENTIALS.md
- **Deployment Issues**: See DEPLOYMENT.md
- **General Questions**: See GETTING_STARTED.md
- **GitHub Issues**: https://github.com/darrylbowler72/agenticframework/issues

---

**Let's build something amazing!** 🚀
