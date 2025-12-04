# DevOps Agentic Framework

An autonomous, AI-powered DevOps platform that accelerates software delivery through intelligent multi-agent automation, GitOps workflows, and enhanced developer experience.

## Current Status

**✅ FULLY OPERATIONAL**

The framework is deployed and accessible via public API Gateway with a conversational chatbot interface!

### Live Services

**Public Chatbot Interface**:
- **URL**: https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/
- **Features**: Natural language interface for all DevOps operations
- **Capabilities**: Create workflows, generate code, remediate issues, get help

**API Gateway**: `https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev`
- POST /workflows - Create workflows
- POST /generate - Generate microservices
- POST /remediate - Auto-fix issues
- POST /chat - Chat with AI assistant
- GET /*/health - Health checks

**AI Agents Running** (4 agents on AWS ECS Fargate):
1. **Planner Agent** (port 8000) - Orchestrates multi-step workflows
2. **CodeGen Agent** (port 8001) - Generates code and infrastructure
3. **Remediation Agent** (port 8002) - Auto-fixes detected issues
4. **Chatbot Agent** (port 8003) - Conversational DevOps interface

**Infrastructure** (90+ AWS resources deployed):
- Application Load Balancer routing to ECS services
- VPC with public/private subnets across 2 AZs
- DynamoDB tables for state management
- S3 buckets for artifacts and templates
- EventBridge for event-driven communication
- Secrets Manager for secure credentials

## Quick Start

### Try the Chatbot (Easiest Way)

1. **Open in Browser**: https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/

2. **Ask Questions**:
   - "Create a new Python microservice"
   - "Help me plan a deployment workflow"
   - "Generate a REST API with PostgreSQL"

### Use the API Directly

#### Create a Workflow
```bash
curl -X POST https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "template": "microservice-rest-api",
    "requested_by": "user@example.com",
    "parameters": {
      "service_name": "user-service",
      "language": "python",
      "database": "postgresql",
      "environment": "dev"
    }
  }'
```

#### Generate Microservice Code
```bash
curl -X POST https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/generate \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "payment-service",
    "language": "python",
    "database": "postgresql",
    "api_type": "rest"
  }'
```

#### Check Health
```bash
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/planner/health
```

## Key Capabilities

- **AI Scaffolding**: Generates repos, microservices, IaC, CI/CD pipelines automatically
- **Multi-Agent System**: Specialized agents powered by Claude AI work together
- **Conversational Interface**: Natural language chatbot for DevOps operations
- **Event-Driven**: EventBridge-based asynchronous task orchestration
- **GitOps Ready**: Designed for ArgoCD integration (planned)
- **Policy Automation**: OPA-based governance (planned)
- **Observability**: OpenTelemetry integration (planned)

## Project Structure

```
/backend/agents          # AI agent implementations (Python)
  /planner              # Workflow orchestration
  /codegen              # Code generation
  /remediation          # Auto-remediation
  /chatbot              # Conversational interface
  /common               # Shared utilities
/iac                    # Infrastructure as Code
  /terraform            # AWS infrastructure
    /modules            # Reusable Terraform modules
    /environments       # Environment configs
/scripts                # Deployment automation
/user-stories           # Product requirements
```

## Architecture

### High-Level Flow

```
User → Chatbot/API Gateway → VPC Link → ALB → ECS Agents
                                              ↓
                                    EventBridge + DynamoDB + S3
```

### Components

**Compute**:
- ECS Fargate cluster with 4 agent services
- Auto-scaling based on CPU/memory

**Storage**:
- DynamoDB: Workflow state, sessions
- S3: Generated code, templates, artifacts

**Integration**:
- API Gateway HTTP API (public)
- Application Load Balancer (internal)
- VPC Link (secure connection)
- EventBridge (event-driven messaging)

**Security**:
- Private subnets for all agents
- Secrets Manager for API keys
- IAM roles with minimal permissions

## Deployment

### Prerequisites
- AWS Account with appropriate permissions
- AWS CLI configured
- Terraform >= 1.0
- Podman or Docker
- Anthropic API key

### Deploy Infrastructure

1. **Configure AWS Credentials**
   ```bash
   cp .env.example .env
   # Edit .env with your AWS credentials and API key
   ```

2. **Setup Terraform Backend**
   ```bash
   bash scripts/02-setup-aws-backend.sh
   ```

3. **Deploy Infrastructure**
   ```bash
   bash scripts/03-deploy-infrastructure.sh
   ```

4. **Store API Secrets**
   ```bash
   # Anthropic Claude API key
   aws secretsmanager put-secret-value \
     --secret-id dev-anthropic-api-key \
     --secret-string '{"api_key":"your-anthropic-api-key"}'

   # GitHub Personal Access Token (for repository operations)
   aws secretsmanager put-secret-value \
     --secret-id dev-github-credentials \
     --secret-string '{"token":"your_github_token","owner":"darrylbowler72"}'
   ```

   **Creating a GitHub Personal Access Token:**
   1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
   2. Click "Generate new token (classic)"
   3. Select scopes: `repo` (all), `workflow`, `admin:repo_hook`
   4. Copy the generated token and use it in the command above

5. **Build and Deploy Agents**
   ```bash
   bash scripts/05-deploy-agents-podman.sh
   ```

### Verify Deployment

```bash
# Check ECS services
aws ecs list-services --cluster dev-agentic-cluster --region us-east-1

# Get API Gateway URL
cd iac/terraform && terraform output api_gateway_url

# Test chatbot
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/health
```

## Local Development

Run the chatbot locally for development:

```bash
# Install dependencies
cd backend
pip install fastapi uvicorn pydantic boto3 anthropic httpx

# Set environment variable
export ENVIRONMENT=dev

# Run chatbot server
python -m uvicorn agents.chatbot.main:app --host 0.0.0.0 --port 8003 --reload
```

Access at: http://localhost:8003

## Monitoring

### View Logs
```bash
# All agent logs
aws logs tail /aws/ecs/dev-agentic-cluster --follow

# Specific agent
aws logs tail /aws/ecs/dev-agentic-cluster --follow --filter-pattern planner

# API Gateway logs
aws logs tail /aws/apigateway/dev-agentic-api --follow
```

### Check Service Status
```bash
# ECS services
aws ecs describe-services \
  --cluster dev-agentic-cluster \
  --services dev-planner-agent dev-codegen-agent dev-remediation-agent dev-chatbot-agent \
  --region us-east-1

# ALB target health
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn>
```

### DynamoDB Data
```bash
# List workflows
aws dynamodb scan --table-name dev-workflows --region us-east-1

# List chat sessions
aws dynamodb scan --table-name dev-chatbot-sessions --region us-east-1
```

## Cost Estimate

Monthly cost for current deployment (24/7):

| Service | Cost |
|---------|------|
| ECS Fargate (4 tasks) | ~$45-60 |
| Application Load Balancer | ~$20-25 |
| API Gateway | ~$3-5 |
| VPC (NAT Gateways) | ~$100-120 |
| DynamoDB | ~$5-10 |
| S3 + CloudWatch | ~$5-10 |
| **Total** | **~$180-230/month** |

## Troubleshooting

### Can't reach API Gateway
```bash
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/health
```
Expected: JSON with `"status": "healthy"`

### Agents not responding
```bash
# Check ECS service status
aws ecs describe-services \
  --cluster dev-agentic-cluster \
  --services dev-chatbot-agent \
  --region us-east-1
```

### ALB health checks failing
```bash
# Check target health
aws elbv2 describe-target-health \
  --target-group-arn <arn>
```

### Claude API errors
```bash
# Verify API key
aws secretsmanager get-secret-value \
  --secret-id dev-anthropic-api-key \
  --region us-east-1
```

## What's Next

### Immediate
- Configure custom domain for API Gateway
- Add authentication (AWS IAM or JWT)
- Set up CloudWatch alarms

### Short Term
- GitLab integration for repository creation
- ArgoCD for GitOps deployments
- Policy Agent with OPA rules

### Long Term
- Multi-environment setup (staging, production)
- Backstage developer portal
- Observability Agent with OpenTelemetry
- Advanced AI features and custom agents

## Documentation

- [Architecture Documentation](./architecture.md) - Detailed technical architecture
- [GitHub Integration Guide](./docs/GITHUB_INTEGRATION.md) - Complete guide for GitHub integration
- User Stories: See `/user-stories` directory for requirements

## Support

- **Issues**: https://github.com/darrylbowler72/agenticframework/issues
- **Discussions**: GitHub Discussions for Q&A

## License

MIT License

---

**Current Deployment**: Development environment (us-east-1)
**Infrastructure**: 90+ AWS resources managed by Terraform
**Status**: Operational and ready for use
