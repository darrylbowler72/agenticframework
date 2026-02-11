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

**AI Agents Running** (6 services on AWS ECS Fargate):
1. **Planner Agent** (port 8000) - Orchestrates multi-step workflows
2. **CodeGen Agent** (port 8001) - Generates code and infrastructure
3. **Remediation Agent** (port 8002) - Auto-fixes detected issues
4. **Chatbot Agent** (port 8003) - Conversational DevOps interface
5. **Migration Agent** (port 8004) - Converts Jenkins pipelines to GitHub Actions
6. **MCP GitHub Server** (port 8100) - Model Context Protocol server for GitHub operations

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

#### Migrate Jenkins Pipeline
```bash
curl -X POST https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/migration/migrate \
  -H "Content-Type: application/json" \
  -d '{
    "jenkinsfile_content": "pipeline { agent any stages { stage(Build) { steps { sh maven clean install } } } }",
    "project_name": "my-service",
    "options": {}
  }'
```

#### Check Health
```bash
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/planner/health
```

## Key Capabilities

- **LangGraph Orchestration**: All agents use LangGraph StateGraphs for workflow logic with conditional routing, retry cycles, and automatic fallbacks
- **AI Scaffolding**: Generates repos, microservices, IaC, CI/CD pipelines automatically
- **Multi-Agent System**: Specialized agents powered by Claude AI work together
- **Pipeline Migration**: Converts Jenkins pipelines to GitHub Actions workflows automatically
- **Conversational Interface**: Natural language chatbot for DevOps operations
- **MCP Integration**: Model Context Protocol for standardized tool integration
- **Event-Driven**: EventBridge-based asynchronous task orchestration
- **GitOps Ready**: Designed for ArgoCD integration (planned)
- **Policy Automation**: OPA-based governance (planned)
- **Observability**: OpenTelemetry integration (planned)

## Model Context Protocol (MCP)

The framework uses **Model Context Protocol** for standardized GitHub operations:

### Architecture

```
Agent → MCP Client → MCP GitHub Server → GitHub API
```

### Benefits

- **Separation of Concerns**: Agents focus on business logic, MCP handles GitHub operations
- **Standardized Interface**: Consistent API across all agents
- **Centralized Credentials**: GitHub tokens managed in one place
- **Extensibility**: Easy to add GitLab, Bitbucket, or other Git providers
- **Maintainability**: Update GitHub logic without changing agents

### MCP GitHub Server

**Location**: `backend/mcp-server/github/`
**Port**: 8100
**Endpoint**: `/mcp/call`

**Available Tools**:
- `github.create_repository` - Create GitHub repositories
- `github.create_file` - Create files in repositories
- `github.get_workflow_run` - Get GitHub Actions workflow details
- `github.list_repositories` - List user repositories
- `github.get_repository` - Get repository details

### Usage Example

```python
from common.mcp_client import GitHubMCPClient

# Initialize MCP client
github = GitHubMCPClient()

# Create repository
repo = await github.create_repository(
    name="my-service",
    description="A new microservice",
    private=True
)

# Create file
await github.create_file(
    repo_name="my-service",
    file_path="README.md",
    content="# My Service",
    message="Initial commit"
)
```

### Deployment

The MCP GitHub Server runs as an ECS Fargate service alongside the agents, accessible via private networking at `http://dev-mcp-github:8100`.

## LangGraph Agent Orchestration

All agents use **LangGraph** for internal workflow orchestration. Each agent builds a compiled `StateGraph` at initialization and runs it via `ainvoke()` for every request.

### How It Works

```
HTTP Request → FastAPI endpoint → agent.graph.ainvoke(initial_state) → final_state → Response
```

Each graph is a directed graph of async node functions connected by edges (sequential) and conditional edges (branching/fallback). State flows through every node as a `TypedDict`.

### Agent Graphs

| Agent | Graph Pattern | Key Feature |
|-------|--------------|-------------|
| **Planner** | plan → fallback → store → dispatch | Conditional AI/fallback planning |
| **Migration** | parse → generate → cleanup → report | Dual LLM/regex+template fallback |
| **Chatbot** | analyze → execute → compose | Conditional action dispatch |
| **Remediation** | fetch → analyze → fix → notify | Retry cycle (up to 3 attempts) |
| **CodeGen** | init → generate → enhance → store → push → readme | Sequential pipeline |

### Key Files

- `backend/agents/common/graphs.py` - All graph builder functions
- `backend/agents/common/graph_states.py` - TypedDict state definitions

### Example: Migration Graph

```python
from common.graphs import build_migration_graph

# Graph automatically handles:
# 1. LLM parsing (falls back to regex on failure)
# 2. LLM generation (falls back to templates on failure)
# 3. Platform command cleanup
# 4. Report generation

result = await self.migration_graph.ainvoke({
    "jenkinsfile_content": jenkinsfile,
    "project_name": "my-service",
})
# result["cleaned_yaml"] contains the GitHub Actions workflow
```

See [Architecture Documentation](./architecture.md) for detailed graph diagrams and state schemas.

## Project Structure

```
/backend/agents          # AI agent implementations (Python)
  /planner              # Workflow orchestration (LangGraph: plan → fallback → store → dispatch)
  /codegen              # Code generation (LangGraph: init → generate → enhance → store → push)
  /remediation          # Auto-remediation (LangGraph: fetch → analyze → fix with retry loop)
  /chatbot              # Conversational interface (LangGraph: intent → action → compose)
  /migration            # Jenkins to GitHub Actions (LangGraph: parse → generate → cleanup)
  /common               # Shared utilities
    graphs.py           # LangGraph graph builders for all agents
    graph_states.py     # TypedDict state definitions
    agent_base.py       # BaseAgent with AWS SDK integrations
    mcp_client.py       # MCP GitHub client
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
User → Chatbot/API Gateway → VPC Link → ALB → ECS Agents (6 services)
                                              ↓
                                    LangGraph StateGraph (per agent)
                                              ↓
                                    EventBridge + DynamoDB + S3
```

### Components

**Orchestration**:
- LangGraph StateGraphs for intra-agent workflow logic
- Conditional routing, retry cycles, automatic fallbacks

**Compute**:
- ECS Fargate cluster with 5 agent services + 1 MCP server
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
- Add LangGraph checkpointing with DynamoDB for state persistence

### Short Term
- GitLab integration for repository creation
- ArgoCD for GitOps deployments
- Policy Agent with OPA rules
- LangGraph Studio integration for visual graph debugging

### Long Term
- Multi-environment setup (staging, production)
- Backstage developer portal
- Observability Agent with OpenTelemetry
- LangGraph human-in-the-loop for high-risk remediation approvals
- Cross-agent LangGraph supervisor for multi-agent coordination

## Documentation

- [Architecture Documentation](./architecture.md) - Detailed technical architecture
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
