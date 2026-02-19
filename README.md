# DevOps Agentic Framework

An autonomous, AI-powered DevOps platform that accelerates software delivery through intelligent multi-agent automation. Runs locally on any machine with Podman or Docker.

## Quick Start

```bash
# 1. Clone and setup
cp .env.local.template .env
# Edit .env: add your ANTHROPIC_API_KEY and GITHUB_TOKEN

# 2. Start all 7 services
bash scripts/run-local.sh up

# 3. Open the chatbot UI
open http://localhost:8003
```

That's it. All 7 AI agents are now running locally.

## Services

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| Chatbot Agent | 8003 | http://localhost:8003 | Web UI - natural language DevOps interface |
| Planner Agent | 8000 | http://localhost:8000/health | Orchestrates multi-step workflows |
| CodeGen Agent | 8001 | http://localhost:8001/health | Generates microservices and infrastructure code |
| Remediation Agent | 8002 | http://localhost:8002/health | Auto-fixes detected issues |
| Migration Agent | 8004 | http://localhost:8004/health | Converts Jenkins pipelines to GitHub Actions |
| Policy Agent | 8005 | http://localhost:8005/health | Enforces governance policies and compliance gates |
| MCP GitHub Server | 8100 | http://localhost:8100/health | GitHub operations via Model Context Protocol |

## What You Can Do

### Try the Chatbot

Open http://localhost:8003 and ask:
- "Create a new Python microservice"
- "Help me plan a deployment workflow"
- "Generate a REST API with PostgreSQL"
- "Migrate my Jenkins pipeline to GitHub Actions"
- "List my GitHub repositories"
- "Create a repo called my-service and bootstrap it with a Python web app and gitflow branching"

### Use the APIs Directly

#### Create a Workflow
```bash
curl -X POST http://localhost:8000/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "template": "microservice-rest-api",
    "requested_by": "user@example.com",
    "parameters": {
      "service_name": "user-service",
      "language": "python"
    }
  }'
```

#### Generate Microservice Code
```bash
curl -X POST http://localhost:8001/generate \
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
curl -X POST http://localhost:8004/migrate \
  -H "Content-Type: application/json" \
  -d '{
    "jenkinsfile_content": "pipeline { agent any stages { stage(Build) { steps { sh \"mvn clean install\" } } } }",
    "project_name": "my-service"
  }'
```

#### Evaluate Code Against Policy
```bash
curl -X POST http://localhost:8005/evaluate/code \
  -H "Content-Type: application/json" \
  -d '{
    "content": "API_KEY = \"sk-abc123\"\ndb_password = \"secret\"",
    "context": {"repo_name": "my-service", "framework": "python"}
  }'
```

#### Check Health
```bash
curl http://localhost:8000/health
curl http://localhost:8003/api/agents/health  # All agents at once
```

## Management Commands

```bash
bash scripts/run-local.sh up       # Build and start all services
bash scripts/run-local.sh down     # Stop and remove all services
bash scripts/run-local.sh logs     # Tail logs from all services
bash scripts/run-local.sh restart  # Stop then start all services
bash scripts/run-local.sh status   # Show running service status
```

## Prerequisites

- **Podman** (recommended) or Docker with compose support
- **Anthropic API key** - get one at https://console.anthropic.com
- **GitHub personal access token** - create at GitHub Settings > Developer settings > Personal access tokens (scopes: `repo`, `workflow`)

## How It Works

### Architecture

```
User Browser → Chatbot (:8003) → Claude AI (intent analysis)
                   │
                   ├──> Planner Agent (:8000)
                   ├──> CodeGen Agent (:8001)
                   ├──> Remediation Agent (:8002)
                   ├──> Migration Agent (:8004)
                   ├──> Policy Agent (:8005)  ← governance & compliance gate
                   └──> MCP GitHub Server (:8100) → GitHub API
```

All services run as containers on a shared bridge network (`agentic-local`). Agents discover each other via container DNS names.

The **Policy Agent** acts as a cross-cutting concern: CodeGen, Chatbot, Migration, and Planner agents all call it to validate content before committing it — blocking hardcoded secrets, enforcing required files, validating workflow YAML, and gating deployments.

### LangGraph Orchestration

Each agent uses [LangGraph](https://github.com/langchain-ai/langgraph) to define its workflow as an explicit state graph. This replaces imperative control flow with declarative graph-based orchestration featuring conditional routing and automatic fallbacks.

```
Example: Migration Agent Graph

parse_with_llm ──(success)──> generate_with_llm ──(success)──> cleanup_platform -> build_report -> END
      |                              |
  (failure)                      (failure)
      v                              v
parse_with_regex              generate_with_template -> cleanup_platform -> ...
```

Key benefits:
- **Explicit control flow** - Agent workflows are visible as graph definitions
- **Automatic fallbacks** - LLM failures route to deterministic alternatives
- **Retry cycles** - Remediation agent retries playbook execution up to 3 times
- **Typed state** - Each graph uses TypedDict state classes for type safety

Graph definitions live in:
- `backend/agents/common/graph_states.py` - State type definitions
- `backend/agents/common/graphs.py` - Graph builder functions

### LOCAL_MODE

When `LOCAL_MODE=true`, cloud services are replaced with local implementations:

| Cloud Service | Local Replacement |
|---------------|-------------------|
| DynamoDB | JSON files in `/data/db/` |
| S3 | Filesystem at `/data/artifacts/` |
| EventBridge | No-op with structured logging |
| Secrets Manager | Environment variables |
| Load Balancer | Container DNS names |

No cloud SDK is imported. Zero cloud dependencies.

### Model Context Protocol (MCP)

GitHub operations are centralized through an MCP server:

```
Agent → MCP Client → MCP GitHub Server → GitHub API
```

This provides a single point for GitHub credential management and a standardized interface for all agents.

## Key Capabilities

- **AI Scaffolding**: Generates repos, microservices, IaC, CI/CD pipelines automatically
- **Multi-Agent System**: 7 specialized agents powered by Claude AI work together
- **Policy Enforcement**: Governance agent gates code, workflows, repositories, and deployments against configurable compliance rules
- **Pipeline Migration**: Converts Jenkins pipelines to GitHub Actions workflows (LLM-powered)
- **Conversational Interface**: Natural language chatbot for all DevOps operations
- **MCP Integration**: Model Context Protocol for standardized GitHub operations
- **Cloud-Agnostic**: Runs on Podman, Docker, or any OCI-compatible runtime

## Project Structure

```
/backend/agents/          # AI agent implementations (Python)
  /planner/               # Workflow orchestration
  /codegen/               # Code generation
  /remediation/           # Auto-remediation
  /chatbot/               # Conversational interface (+ web UI)
  /migration/             # Jenkins to GitHub Actions migration
  /policy/                # Governance and compliance enforcement
  /common/                # Shared utilities (BaseAgent, local_storage, LangGraph)
/backend/mcp-server/
  /github/                # MCP GitHub server
/backend/Dockerfile.*     # One Dockerfile per service
/docker-compose.local.yml # Podman/Docker compose for all services
/scripts/
  run-local.sh            # Launcher (up/down/logs/restart/status)
/.env.local.template      # Template for API keys
```

## Development

### Run a Single Agent Locally

```bash
cd backend
pip install -r agents/common/requirements.txt

export LOCAL_MODE=true
export ENVIRONMENT=local
export ANTHROPIC_API_KEY=your-key
export GITHUB_TOKEN=your-token

python -m uvicorn agents.chatbot.main:app --host 0.0.0.0 --port 8003 --reload
```

### Testing

```bash
cd backend/agents/chatbot
pytest -v
```

### Adding a New Agent

1. Create `backend/agents/<name>/main.py` extending `BaseAgent`
2. Implement `process_task()` method
3. Add a `TypedDict` state class to `backend/agents/common/graph_states.py`
4. Add a `build_<name>_graph(agent)` factory to `backend/agents/common/graphs.py`
5. Add FastAPI routes and `/health` endpoint
6. Create `backend/Dockerfile.<name>`
7. Add service to `docker-compose.local.yml`

See the **Policy Agent** section in `CLAUDE.md` for a complete worked example and implementation checklist.

## Monitoring

### View Logs
```bash
bash scripts/run-local.sh logs
```

### Check All Agent Health
```bash
curl http://localhost:8003/api/agents/health
```

### Persistence

Data persists in the `local-data` volume at `/data`:
- `/data/db/` - JSON database files (DynamoDB replacement)
- `/data/artifacts/` - Stored artifacts (S3 replacement)

## Documentation

- [Architecture Documentation](./architecture.md) - Detailed technical architecture
- [Policy Agent Guide](./docs/policy-agent.md) - Governance policies, API reference, and integration guide
- User Stories: See `/user-stories` directory for requirements

## Support

- **Issues**: https://github.com/darrylbowler72/agenticframework/issues

## License

MIT License
