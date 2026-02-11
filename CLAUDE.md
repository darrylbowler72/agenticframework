# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevOps Agentic Framework - An autonomous, AI-powered DevOps platform that accelerates software delivery through intelligent multi-agent automation, GitOps workflows, and enhanced developer experience.

**Live API**: https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/

## Core Architecture

### Multi-Agent System

The framework consists of 6 specialized AI agents running on AWS ECS Fargate:

1. **Planner Agent** (port 8000) - Orchestrates multi-step workflows
2. **CodeGen Agent** (port 8001) - Generates microservices and infrastructure code
3. **Remediation Agent** (port 8002) - Auto-fixes detected issues in code/workflows
4. **Chatbot Agent** (port 8003) - Natural language interface for DevOps operations
5. **Migration Agent** (port 8004) - Converts Jenkins pipelines to GitHub Actions
6. **MCP GitHub Server** (port 8100) - Model Context Protocol server for GitHub operations

All agents inherit from `BaseAgent` (`backend/agents/common/agent_base.py`) which provides:
- AWS SDK integrations (S3, DynamoDB, EventBridge, Secrets Manager)
- Claude AI API client (via `anthropic` library)
- GitHub API client (via `PyGithub`)
- Structured JSON logging
- Event-driven task processing

### LangGraph Orchestration

All agents use **LangGraph** for internal workflow orchestration. Each agent builds a compiled `StateGraph` at initialization time.

**Key files**:
- `backend/agents/common/graphs.py` - Graph builder functions for all agents
- `backend/agents/common/graph_states.py` - TypedDict state definitions

**Graph per agent**:
- **Planner**: `build_planner_graph()` - plan → fallback → store → dispatch (conditional AI/fallback)
- **Migration**: `build_migration_graph()` - parse → generate → cleanup → report (dual LLM/regex fallback)
- **Chatbot**: `build_chatbot_graph()` - analyze_intent → execute_action → compose_response (conditional dispatch)
- **Remediation**: `build_remediation_graph()` - fetch → analyze → fix → notify (retry cycle up to 3x)
- **CodeGen**: `build_codegen_graph()` - init → generate → enhance → store → push → readme (sequential)

**Pattern**: Each agent's `__init__` calls the builder, storing the compiled graph. Request handlers call `graph.ainvoke(initial_state)` and read results from the final state dict.

### Model Context Protocol (MCP)

The framework uses MCP to separate concerns between agents and external integrations:

```
Agent → GitHubMCPClient → MCP GitHub Server → GitHub API
```

**Key files**:
- `backend/agents/common/mcp_client.py` - Client library used by agents
- `backend/mcp-server/github/server.py` - MCP server implementing GitHub operations

**Benefits**: Centralized credential management, standardized interface, easier to add new Git providers (GitLab, Bitbucket).

### Agent Communication Flow

```
User/API → API Gateway → VPC Link → ALB → ECS Agent → LangGraph StateGraph → EventBridge → Other Agents
                                              ↓                    ↓
                                    Claude AI (anthropic)   DynamoDB (state) + S3 (artifacts)
```

## Build and Deploy

### Prerequisites

- AWS CLI configured with credentials
- Terraform >= 1.0
- Podman or Docker
- Python 3.11+
- Anthropic API key

### Initial Setup

```bash
# 1. Setup AWS backend (S3 + DynamoDB for Terraform state)
bash scripts/02-setup-aws-backend.sh

# 2. Deploy infrastructure (VPC, ECS, ALB, API Gateway, DynamoDB, S3, etc.)
bash scripts/03-deploy-infrastructure.sh

# 3. Store secrets in AWS Secrets Manager
aws secretsmanager put-secret-value \
  --secret-id dev-anthropic-api-key \
  --secret-string '{"api_key":"your-anthropic-api-key"}'

aws secretsmanager put-secret-value \
  --secret-id dev-github-credentials \
  --secret-string '{"token":"your_github_token","owner":"darrylbowler72"}'

# 4. Build and push agent Docker images to ECR
bash scripts/05-deploy-agents-podman.sh
```

### Deploy Individual Agent

```bash
# Build and deploy a single agent
bash scripts/deploy-<agent-name>.sh

# Example: Deploy migration agent
bash scripts/deploy-migration.sh
```

### Infrastructure Management

```bash
# Navigate to Terraform directory
cd iac/terraform

# Initialize with dev backend
terraform init -backend-config=environments/dev/backend.tfvars

# Plan changes
terraform plan -var-file=environments/dev/terraform.tfvars

# Apply changes
terraform apply -var-file=environments/dev/terraform.tfvars

# Destroy infrastructure (use with caution)
bash scripts/06-destroy-infrastructure.sh
```

## Development

### Local Agent Development

```bash
# Install dependencies
cd backend
pip install -r agents/common/requirements.txt

# Set environment
export ENVIRONMENT=dev
export AWS_REGION=us-east-1

# Run agent locally (example: chatbot)
python -m uvicorn agents.chatbot.main:app --host 0.0.0.0 --port 8003 --reload
```

### Testing

```bash
# Run agent tests with pytest
cd backend/agents/chatbot
pytest -v

# Pytest is configured with asyncio_mode = auto for async tests
```

### Docker Image Naming Convention

- Agents: `<agent-name>-agent` (e.g., `planner-agent`, `migration-agent`)
- MCP Servers: `mcp-<service>` (e.g., `mcp-github`)
- Dockerfiles: `backend/Dockerfile.<name>` (e.g., `Dockerfile.planner`, `Dockerfile.mcp-github`)

## Key Technical Details

### Agent Implementation Pattern

Each agent (`backend/agents/<agent-name>/main.py`):
1. Extends `BaseAgent`
2. Implements FastAPI application
3. Defines Pydantic models for request/response
4. Builds a LangGraph `StateGraph` via `build_<agent>_graph(self)` in `__init__`
5. Implements `process_task()` method which delegates to `graph.ainvoke()`
6. Uses Claude AI via `self.call_claude()` (called from graph nodes)
7. Uses MCP for GitHub operations via `GitHubMCPClient()`

### LangGraph Development

When modifying agent workflow logic:
- Graph builders are in `backend/agents/common/graphs.py`
- State types are in `backend/agents/common/graph_states.py`
- Each graph node is an async function taking state and returning a partial state dict
- Use `add_conditional_edges()` for branching logic (fallbacks, intent routing)
- Use cycles (node pointing back to itself or earlier) for retry loops
- The agent instance (`self`) is captured in the closure, giving nodes access to `call_claude()`, `publish_event()`, etc.

### Infrastructure Modules

Terraform modules in `iac/terraform/modules/`:
- `vpc/` - Network infrastructure (subnets, NAT, security groups)
- `ecs/` - ECS cluster, services, task definitions
- `api_gateway/` - HTTP API, VPC Link integration
- `dynamodb/` - Tables for workflows, sessions, policy violations
- `s3/` - Buckets for artifacts, templates, state
- `eventbridge/` - Event bus for agent communication

### Environment Configuration

Environments defined in `iac/terraform/environments/<env>/`:
- `terraform.tfvars` - Variable values
- `backend.tfvars` - S3 backend configuration
- No `main.tf` files - root module is in `iac/terraform/`

### Secrets Management

All secrets stored in AWS Secrets Manager:
- `dev-anthropic-api-key` - Claude AI API key
- `dev-github-credentials` - GitHub token and owner
- `dev-slack-credentials` - Slack webhooks (if configured)

Agents retrieve secrets via `BaseAgent._get_anthropic_client()` and `BaseAgent._get_github_client()`.

## Migration Agent Specifics

The Migration Agent converts Jenkins pipelines to GitHub Actions workflows:

- **LLM-based parsing**: Uses Claude to intelligently parse Jenkinsfile instead of regex
- **Step mappings**: Maps Jenkins steps to GitHub Actions (`self.step_mappings`)
- **Plugin mappings**: Maps Jenkins plugins to Actions (`self.plugin_mappings`)
- **Integration**: Can fetch pipelines from live Jenkins instances and push workflows to GitHub

**Key classes**:
- `MigrationAgent` - Main agent logic
- `JenkinsClient` - Jenkins API integration
- `GitHubClient` - GitHub API integration (uses MCP internally)

## Monitoring and Debugging

### View ECS Logs

```bash
# All agents
aws logs tail /aws/ecs/dev-agentic-cluster --follow

# Specific agent
aws logs tail /aws/ecs/dev-agentic-cluster --follow --filter-pattern migration

# API Gateway logs
aws logs tail /aws/apigateway/dev-agentic-api --follow
```

### Check Service Health

```bash
# ECS services status
aws ecs describe-services \
  --cluster dev-agentic-cluster \
  --services dev-planner-agent dev-codegen-agent dev-remediation-agent dev-chatbot-agent dev-migration-agent \
  --region us-east-1

# Health check endpoints
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/planner/health
curl https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/migration/health
```

### DynamoDB Tables

```bash
# List workflows
aws dynamodb scan --table-name dev-workflows --region us-east-1

# List chatbot sessions
aws dynamodb scan --table-name dev-chatbot-sessions --region us-east-1
```

## Important Conventions

### Agent Development
- All agents use async/await patterns (FastAPI + asyncio)
- All agents use LangGraph StateGraphs for workflow logic
- Graph nodes are async functions; use `graph.ainvoke()` for execution
- Use `BaseAgent` logger (`self.logger.info()`) for structured JSON logs
- Store state in DynamoDB via `self.workflows_table` or `self.tasks_table`
- Use EventBridge for async agent-to-agent communication
- Use MCP for GitHub operations (don't call GitHub API directly)

### Infrastructure Changes
- Always test Terraform changes in `dev` environment first
- Use `terraform plan` before applying
- Infrastructure state is stored in S3 with DynamoDB locking
- Never destroy infrastructure without backing up DynamoDB data

### Container Deployment
- Use Podman instead of Docker (Windows compatibility)
- Tag images with both `:latest` and timestamp `:YYYYMMDD-HHMMSS`
- ECR repositories are auto-created by deployment scripts
- All containers must expose `/health` endpoint for ALB health checks

### Version Management
- Agent version in `backend/agents/common/version.py`
- Update version in agent `main.py` FastAPI app if individual versioning needed
- All agents at version 2.0.0 (LangGraph integration)

## API Reference

### Public Endpoints

- `POST /workflows` - Create workflow via Planner Agent
- `POST /generate` - Generate microservice via CodeGen Agent
- `POST /remediate` - Auto-fix issue via Remediation Agent
- `POST /chat` - Chat interface via Chatbot Agent
- `POST /migration/migrate` - Convert Jenkins pipeline
- `POST /migration/analyze` - Analyze Jenkinsfile
- `GET /migration/jenkins/list` - List Jenkins jobs
- `GET /<agent>/health` - Health check

All agents expose standard health check at `GET /<agent-name>/health`.

## Common Troubleshooting

### Agent Not Starting
1. Check CloudWatch logs for errors
2. Verify secrets exist in Secrets Manager
3. Check ECS task definition has correct environment variables
4. Verify ECR image exists and is tagged correctly

### MCP Connection Errors
- MCP server runs at `http://dev-mcp-github:8100` (internal ECS service discovery)
- Ensure security groups allow port 8100 communication
- Check `MCP_GITHUB_URL` environment variable

### Terraform State Lock
If deployment fails with state lock error:
```bash
# Force unlock (use with caution)
cd iac/terraform
terraform force-unlock <LOCK_ID>
```

### GitHub Token Issues
- Token needs `repo`, `workflow`, `admin:repo_hook` scopes
- Stored in `dev-github-credentials` secret as `{"token":"...", "owner":"..."}`
- Token retrieved by both agents and MCP server
