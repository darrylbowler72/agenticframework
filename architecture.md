# DevOps Agentic Framework - Architecture Documentation

## Table of Contents
1. [System Overview](#system-overview)
2. [Local Deployment Architecture](#local-deployment-architecture)
3. [Agent Architecture](#agent-architecture)
4. [Data Flow & Orchestration](#data-flow--orchestration)
5. [Model Context Protocol (MCP)](#model-context-protocol-mcp)
6. [Local Storage Layer](#local-storage-layer)
7. [Security & Configuration](#security--configuration)
8. [API Specifications](#api-specifications)
9. [Developer Guide](#developer-guide)

---

## System Overview

### Purpose
The DevOps Agentic Framework is an autonomous, AI-driven platform designed to accelerate software delivery through intelligent automation. It combines multi-agent systems, pipeline migration, conversational interfaces, and code generation into a self-contained, locally deployable system.

### Core Philosophy
- **Cloud-Agnostic**: Runs on any platform supporting OCI containers (Podman, Docker, Kubernetes)
- **Autonomous Operations**: AI agents handle complex workflows with minimal human intervention
- **Zero Cloud Dependencies**: No cloud provider SDKs, accounts, or infrastructure required in local mode
- **Container-Native**: All services are standard OCI containers communicating over a shared network

---

## Local Deployment Architecture

### Architecture Diagram

```
                    localhost (host machine)
                       │
     ┌─────────────────┼────────────────────────────────────┐
     │  :8000     :8001 │  :8002     :8003      :8004       │
     ▼            ▼     ▼      ▼           ▼          ▼     │
┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐ ┌─────────┐  │
│Planner │ │CodeGen │ │Remediat│ │ Chatbot  │ │Migration│  │
│Agent   │ │Agent   │ │Agent   │ │ Agent    │ │Agent    │  │
│:8000   │ │:8001   │ │:8002   │ │ :8003    │ │:8004    │  │
└────┬───┘ └────┬───┘ └────┬───┘ └─────┬────┘ └────┬────┘  │
     │          │          │           │            │       │
     └──────────┼──────────┼───────────┼────────────┘       │
                │          │           │                    │
                ▼          ▼           ▼                    │
        ┌──────────────┐ ┌────────────────────┐             │
        │ MCP GitHub   │ │ Shared Volume      │             │
        │ Server :8100 │ │ /data/             │             │
        └──────────────┘ │   db/     (DynamoDB)│             │
                         │   artifacts/ (S3)   │             │
                         └────────────────────┘             │
                                                            │
                    agentic-local network (bridge)          │
────────────────────────────────────────────────────────────┘
```

### Services

| Service | Container Name | Port | Role |
|---------|---------------|------|------|
| MCP GitHub Server | `mcp-github` | 8100 | GitHub API operations via Model Context Protocol |
| Planner Agent | `planner-agent` | 8000 | Orchestrates multi-step workflows |
| CodeGen Agent | `codegen-agent` | 8001 | Generates microservices and infrastructure code |
| Remediation Agent | `remediation-agent` | 8002 | Auto-fixes detected issues |
| Chatbot Agent | `chatbot-agent` | 8003 | Conversational DevOps interface (web UI) |
| Migration Agent | `migration-agent` | 8004 | Converts Jenkins pipelines to GitHub Actions |

### Service Startup Order

```
mcp-github (health-checked)
    │
    ├──> planner-agent
    ├──> codegen-agent
    ├──> remediation-agent
    ├──> migration-agent
    │
    └──> chatbot-agent (starts last, depends on all others)
```

### Service Discovery

Agents discover each other via **container DNS names** on the `agentic-local` bridge network:

```
Chatbot → http://planner-agent:8000/workflows
Chatbot → http://codegen-agent:8001/generate
Chatbot → http://remediation-agent:8002/remediate
Chatbot → http://migration-agent:8004/migration
All     → http://mcp-github:8100/mcp/call
```

Service URLs are configurable via environment variables (`PLANNER_URL`, `CODEGEN_URL`, etc.) for flexibility across deployment targets.

### Networking

- **Network**: `agentic-local` (bridge driver)
- **Inter-service**: Container-to-container via DNS names
- **Host access**: Each service exposes its port to localhost
- **No load balancer**: Direct port mapping (one container per service)

---

## Agent Architecture

### Base Agent Pattern

All agents inherit from `BaseAgent` (`backend/agents/common/agent_base.py`) which provides:

```
┌──────────────────────────────────────────┐
│              Agent Container             │
│                                          │
│  ┌────────────────────────────────────┐  │
│  │         FastAPI Application        │  │
│  │    - REST endpoints                │  │
│  │    - Health check at /health       │  │
│  └────────┬───────────────────────────┘  │
│           │                              │
│           ▼                              │
│  ┌────────────────────────────────────┐  │
│  │      BaseAgent (common layer)      │  │
│  │   - Claude AI client               │  │
│  │   - GitHub client                  │  │
│  │   - Storage clients (local/cloud)  │  │
│  │   - Structured JSON logging        │  │
│  └────────┬───────────────────────────┘  │
│           │                              │
│           ▼                              │
│  ┌────────────────────────────────────┐  │
│  │    LOCAL_MODE Storage Backends     │  │
│  │   - LocalDynamoDBTable (JSON)      │  │
│  │   - LocalS3Client (filesystem)     │  │
│  │   - LocalEventsClient (no-op/log)  │  │
│  │   - LocalSecretsClient (env vars)  │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

### Storage Initialization

```python
# In agent_base.py - local storage backends, no cloud dependencies
from common.local_storage import (
    LocalDynamoDBResource, LocalS3Client,
    LocalEventsClient, LocalSecretsClient
)
```

### Agent Catalog

#### 1. Planner Agent (port 8000)
- Orchestrates multi-step workflows
- Decomposes high-level requests into tasks
- Assigns tasks to specialized agents
- **No modifications needed for local mode** - inherits from BaseAgent

#### 2. CodeGen Agent (port 8001)
- Generates microservice boilerplate code
- Creates infrastructure templates
- Generates CI/CD pipeline configs
- **No modifications needed for local mode** - inherits from BaseAgent

#### 3. Remediation Agent (port 8002)
- Auto-fixes CI/CD pipeline failures
- Analyzes error logs and suggests fixes
- **No modifications needed for local mode** - inherits from BaseAgent

#### 4. Chatbot Agent (port 8003)
- Natural language interface for all DevOps operations
- Web UI accessible at `http://localhost:8003`
- Routes commands to other agents via HTTP
- **Modified for local mode**: Uses container URLs for agent discovery instead of API Gateway

#### 5. Migration Agent (port 8004)
- Converts Jenkins pipelines to GitHub Actions
- LLM-powered parsing and generation
- Integrates with Jenkins servers and GitHub
- Reads GitHub token from `GITHUB_TOKEN` environment variable

#### 6. MCP GitHub Server (port 8100)
- Model Context Protocol server for GitHub operations
- Centralized GitHub credential management
- Reads GitHub credentials from environment variables

---

## Data Flow & Orchestration

### Request Flow (Local)

```
User Browser
    │
    ▼
Chatbot Agent (:8003)
    │
    ├─ Claude AI (intent analysis)
    │
    ├─ If workflow request ──> Planner Agent (:8000)
    ├─ If codegen request  ──> CodeGen Agent (:8001)
    ├─ If fix request      ──> Remediation Agent (:8002)
    ├─ If migration        ──> Migration Agent (:8004)
    └─ If GitHub operation ──> MCP GitHub Server (:8100)
                                      │
                                      ▼
                               GitHub API (external)
```

### Agent Communication

All inter-agent communication is **synchronous HTTP** in local mode:
- Chatbot calls other agents via their container URLs
- Each agent responds with JSON
- No message queue or event bus needed locally (EventBridge is no-op)

### Event Flow (Local Mode)

EventBridge events are logged but not published:
```
Agent publishes event → LocalEventsClient → Structured log output
```

This preserves the event-driven code paths without requiring infrastructure.

---

## Model Context Protocol (MCP)

### Architecture

```
Agent → GitHubMCPClient → HTTP POST → MCP GitHub Server → GitHub API
```

### Benefits
- **Separation of Concerns**: Agents focus on business logic, MCP handles GitHub
- **Centralized Credentials**: GitHub token managed in one place (MCP server)
- **Standardized Interface**: Consistent JSON-RPC API across all agents

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `github.create_repository` | Create a new GitHub repository |
| `github.create_file` | Create a file in a repository |
| `github.create_branch` | Create a branch in a repository |
| `github.get_workflow_run` | Get GitHub Actions workflow run details |
| `github.list_repositories` | List user's repositories |
| `github.get_repository` | Get repository details |

### MCP Server Endpoint

- **URL**: `http://mcp-github:8100/mcp/call` (inter-container)
- **URL**: `http://localhost:8100/mcp/call` (from host)
- **Protocol**: JSON-RPC 2.0

---

## Local Storage Layer

All storage is implemented in `backend/agents/common/local_storage.py`.

### LocalDynamoDBTable

In-memory dictionary with JSON file persistence at `/data/db/<table-name>.json`.

**Supported operations**: `put_item`, `get_item`, `query`, `update_item`, `scan`, `load`

```
/data/db/
  ├── local-workflows.json
  ├── local-tasks.json
  └── local-chatbot-sessions.json
```

### LocalS3Client

Filesystem-backed object store at `/data/artifacts/`.

**Supported operations**: `put_object`, `get_object`

```
/data/artifacts/
  └── <bucket-name>/
      └── <key-path>/
          └── <object-file>
```

### LocalEventsClient

No-op implementation that logs all published events to stdout in structured JSON format.

### LocalSecretsClient

Reads secrets from environment variables:

| Secret Pattern | Environment Variable |
|---------------|---------------------|
| `*anthropic*` | `ANTHROPIC_API_KEY` |
| `*github*` | `GITHUB_TOKEN` + `GITHUB_OWNER` |
| `*slack*` | `SLACK_BOT_TOKEN` + `SLACK_SIGNING_SECRET` |

---

## Security & Configuration

### Secrets Management (Local)

All secrets are passed via environment variables in the `.env` file:

```bash
ANTHROPIC_API_KEY=sk-ant-...    # Claude AI API key
GITHUB_TOKEN=ghp_...            # GitHub personal access token
GITHUB_OWNER=your-username      # GitHub username/org
```

The `.env` file is gitignored. Use `.env.local.template` as a starting point.

### Network Security

- All services run on an isolated bridge network (`agentic-local`)
- Only exposed ports are accessible from the host
- No TLS between containers (local development only)
- External API calls (Claude AI, GitHub) use HTTPS

### Container Images

All containers use `python:3.11-slim` base image:
- Agents: `backend/Dockerfile.<agent-name>`
- MCP Server: `backend/Dockerfile.mcp-github`
- Build context: Project root (`.`)
- Health checks: `curl` to `/health` endpoint

---

## API Specifications

### Health Check (All Agents)

```
GET /health

Response: 200 OK
{
  "status": "healthy",
  "agent": "<agent-name>",
  "version": "1.0.0"
}
```

### Chatbot

```
POST /chat
{
  "session_id": "uuid",
  "message": "Create a new Python microservice"
}

GET /session/{session_id}
GET /                        # Web UI
GET /api/agents/health       # All agents health status
```

### Planner

```
POST /workflows
{
  "description": "Deploy user-service to staging",
  "environment": "dev",
  "template": "default",
  "requested_by": "user"
}
```

### CodeGen

```
POST /generate
{
  "service_name": "user-service",
  "language": "python",
  "database": "postgresql",
  "api_type": "rest"
}
```

### Migration

```
POST /migrate
{
  "jenkinsfile_content": "pipeline { ... }",
  "project_name": "my-service"
}

POST /analyze
GET  /migration/jenkins/jobs
POST /migration/jenkins/migrate-job
```

### MCP GitHub Server

```
POST /mcp/call
{
  "jsonrpc": "2.0",
  "id": "uuid",
  "method": "github.create_repository",
  "params": { "name": "my-repo", "private": true }
}

GET /mcp/info    # List available tools
GET /health
```

---

## Developer Guide

### Project Structure

```
/backend/agents/          # AI agent implementations (Python)
  /planner/               # Workflow orchestration
  /codegen/               # Code generation
  /remediation/           # Auto-remediation
  /chatbot/               # Conversational interface (+ web UI)
  /migration/             # Jenkins to GitHub Actions migration
  /common/                # Shared utilities
    agent_base.py          # BaseAgent class (LOCAL_MODE logic)
    local_storage.py       # Local replacements for AWS services
    version.py             # Version management
/backend/mcp-server/
  /github/                # MCP GitHub server
/backend/Dockerfile.*     # One Dockerfile per service
/docker-compose.local.yml # Local Podman/Docker compose
/scripts/
  run-local.sh            # Launcher (up/down/logs/restart/status)
/.env.local.template      # Template for API keys
```

### Running Locally

```bash
cp .env.local.template .env
# Edit .env with your ANTHROPIC_API_KEY and GITHUB_TOKEN

bash scripts/run-local.sh up       # Start all services
bash scripts/run-local.sh logs     # Watch logs
bash scripts/run-local.sh status   # Check service status
bash scripts/run-local.sh down     # Stop everything
```

### Developing a Single Agent

```bash
cd backend
pip install -r agents/common/requirements.txt

export LOCAL_MODE=true
export ENVIRONMENT=local
export ANTHROPIC_API_KEY=your-key
export GITHUB_TOKEN=your-token

python -m uvicorn agents.chatbot.main:app --host 0.0.0.0 --port 8003 --reload
```

### Adding a New Agent

1. Create `backend/agents/<name>/main.py` extending `BaseAgent`
2. Implement `process_task()` method
3. Add FastAPI routes and health check at `/health`
4. Create `backend/Dockerfile.<name>`
5. Add service to `docker-compose.local.yml`
6. Update chatbot agent endpoints if the new agent should be accessible via chat

### Container Build Context

All Dockerfiles use the **project root** as build context:

```dockerfile
# Example: backend/Dockerfile.planner
COPY backend/agents/common/ /app/common/
COPY backend/agents/planner/ /app/planner/
```

### Persistence

Data persists in the `local-data` Docker volume mounted at `/data`:
- JSON database files: `/data/db/`
- Artifact storage: `/data/artifacts/`

To reset all data: `bash scripts/run-local.sh down` (removes volumes)

---

*Last Updated: 2026-02-13*
*Version: 2.0.0 (local-podman)*
