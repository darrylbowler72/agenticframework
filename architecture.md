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
10. [Technology Glossary](#technology-glossary)

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
     ┌─────────────────┼──────────────────────────────────────────┐
     │  :8000     :8001 │  :8002     :8003      :8004    :8005    │
     ▼            ▼     ▼      ▼           ▼          ▼       ▼  │
┌────────┐ ┌────────┐ ┌────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐ │
│Planner │ │CodeGen │ │Remediat│ │ Chatbot  │ │Migration│ │ Policy   │ │
│Agent   │ │Agent   │ │Agent   │ │ Agent    │ │Agent    │ │ Agent    │ │
│:8000   │ │:8001   │ │:8002   │ │ :8003    │ │:8004    │ │ :8005    │ │
└────┬───┘ └────┬───┘ └────┬───┘ └─────┬────┘ └────┬────┘ └────┬─────┘ │
     │          │          │           │            │           │      │
     └──────────┼──────────┼───────────┼────────────┼───────────┘      │
                │          │           │            │                  │
                ▼          ▼           ▼            ▼                  │
        ┌──────────────┐ ┌──────────────────────┐                      │
        │ MCP GitHub   │ │ Shared Volume        │                      │
        │ Server :8100 │ │ /data/               │                      │
        └──────────────┘ │   db/      (DynamoDB) │                      │
                         │   artifacts/    (S3)  │                      │
                         └──────────────────────┘                      │
                                                                       │
                    agentic-local network (bridge)                     │
───────────────────────────────────────────────────────────────────────┘
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
| Policy Agent | `policy-agent` | 8005 | Governance and compliance enforcement gate |

### Service Startup Order

```
mcp-github (health-checked)
    │
    ├──> planner-agent
    ├──> codegen-agent
    ├──> remediation-agent
    ├──> migration-agent
    ├──> policy-agent
    │
    └──> chatbot-agent (starts last, depends on all others)
```

### Service Discovery

Agents discover each other via **container DNS names** on the `agentic-local` bridge network:

```
Chatbot           → http://planner-agent:8000/workflows
Chatbot           → http://codegen-agent:8001/generate
Chatbot           → http://remediation-agent:8002/remediate
Chatbot           → http://migration-agent:8004/migration
Chatbot/CodeGen/
Migration/Planner → http://policy-agent:8005/evaluate
All               → http://mcp-github:8100/mcp/call
```

Service URLs are configurable via environment variables (`PLANNER_URL`, `CODEGEN_URL`, `POLICY_URL`, etc.) for flexibility across deployment targets.

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

#### 6. Policy Agent (port 8005)
- Governance and compliance enforcement for all DevOps pipeline stages
- Evaluates code, workflows, repositories, and deployment requests against configurable policy rules
- Returns `approved: true/false` with violation details and auto-fix suggestions
- Policies stored in `/data/db/local-policies.json` with per-type applicability
- Called by other agents as a gate before pushing code or dispatching deployments
- Default policies include: no hardcoded secrets, required repo files, workflow security rules, naming conventions

#### 7. MCP GitHub Server (port 8100)
- Model Context Protocol server for GitHub operations
- Centralized GitHub credential management
- Reads GitHub credentials from environment variables

---

## LangGraph Integration

### Overview

All 6 agents use [LangGraph](https://github.com/langchain-ai/langgraph) StateGraph instances to define their workflows as explicit directed graphs. Each agent builds a compiled graph at initialization and invokes it per request via `await self.graph.ainvoke(state)`.

### Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Agent Container                   │
│                                                     │
│  ┌───────────────────────────────────────────────┐  │
│  │              FastAPI Application               │  │
│  └──────────────────┬────────────────────────────┘  │
│                     │                               │
│                     ▼                               │
│  ┌───────────────────────────────────────────────┐  │
│  │       LangGraph Compiled StateGraph           │  │
│  │   ┌────────┐   ┌────────┐   ┌────────┐       │  │
│  │   │ Node A │──>│ Node B │──>│ Node C │──>END  │  │
│  │   └────────┘   └───┬────┘   └────────┘       │  │
│  │                    │ (conditional)             │  │
│  │                    ▼                           │  │
│  │              ┌────────┐                        │  │
│  │              │Fallback│──>...                  │  │
│  │              └────────┘                        │  │
│  └──────────────────┬────────────────────────────┘  │
│                     │                               │
│                     ▼                               │
│  ┌───────────────────────────────────────────────┐  │
│  │     BaseAgent (Claude AI, Storage, GitHub)     │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### State Classes (`graph_states.py`)

| State Class | Agent | Key Fields |
|-------------|-------|------------|
| `WorkflowState` | Planner | template, parameters, tasks, status |
| `CodeGenState` | CodeGen | service_name, language, files, repo_url |
| `RemediationState` | Remediation | pipeline_id, logs, analysis, playbook, retry_count |
| `MigrationState` | Migration | jenkinsfile_content, pipeline_data, workflow_yaml, cleaned_yaml |
| `ChatState` | Chatbot | user_message, intent, action_result, final_response |
| `PolicyState` | Policy | content_type, content, policies, violations, approved, severity_summary |

### Agent Graphs (`graphs.py`)

#### Planner Agent
```
plan_tasks ──(success)──> store_workflow -> dispatch_tasks -> END
    |
(failure)
    v
fallback_plan -> store_workflow -> dispatch_tasks -> END
```

#### CodeGen Agent
```
init_github -> generate_templates -> enhance_with_ai -> store_artifacts -> push_to_repo -> generate_readme -> END
```

#### Remediation Agent (with retry loop)
```
fetch_logs -> analyze_failure -> find_playbook
                                      |
                    (auto-fixable) ---+--- (manual) -> store_and_notify -> END
                         |
                    execute_playbook ──(success)──> store_and_notify -> END
                         |           |
                    (fail,retry<3)   (fail,retry>=3) -> store_and_notify -> END
                         |
                         └──> execute_playbook (retry)
```

#### Migration Agent (dual fallback)
```
parse_with_llm ──(success)──> generate_with_llm ──(success)──> cleanup_platform -> build_report -> END
      |                              |
  (failure)                      (failure)
      v                              v
parse_with_regex              generate_with_template -> cleanup_platform -> build_report -> END
```

#### Chatbot Agent
```
analyze_intent ──(action_needed)──> execute_action -> compose_response -> END
      |
  (no action)
      v
compose_response -> END
```

#### Policy Agent
```
load_policies -> scan_content -> evaluate_violations
                                         |
                   (violations & auto_fixable) -> suggest_fixes -> build_report -> END
                                         |
                   (violations, not fixable) ---------> build_report -> END
                                         |
                   (no violations) ------------------> build_report -> END
```

### How Graphs Compose

Graph nodes are thin wrappers that call existing agent methods. The agent instance is passed to the graph builder factory function:

```python
# In graphs.py
def build_planner_graph(agent):
    async def plan_tasks(state):
        tasks = await agent._plan_tasks(state["template"], state["parameters"])
        return {"tasks": tasks, "status": "planned"}
    ...
    graph = StateGraph(WorkflowState)
    graph.add_node("plan_tasks", plan_tasks)
    ...
    return graph.compile()

# In planner/main.py
class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(agent_name="planner")
        self.graph = build_planner_graph(self)

    async def create_workflow(self, request_data):
        result = await self.graph.ainvoke({...})
```

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
    ├─ If workflow request ──> Planner Agent (:8000) ──> Policy (:8005) [deploy gate]
    ├─ If codegen request  ──> CodeGen Agent (:8001) ──> Policy (:8005) [code check]
    ├─ If fix request      ──> Remediation Agent (:8002) → Policy (:8005) [fix check]
    ├─ If migration        ──> Migration Agent (:8004) ──> Policy (:8005) [workflow check]
    ├─ If setup_project    ──> Policy Agent (:8005) [repo compliance]
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
| `github.update_file` | Update an existing file (auto-fetches SHA, falls back to create) |
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
  "version": "1.1.0",
  "timestamp": "<iso8601>"
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

### Policy Agent

```
POST /evaluate/code
{
  "content": "<source code>",
  "context": { "repo_name": "my-service", "framework": "python" }
}

POST /evaluate/workflow
{ "content": "<github actions yaml>", "context": {} }

POST /evaluate/repository
{ "content": "<list of file paths>", "context": { "repo_name": "my-repo" } }

POST /evaluate/deployment
{ "content": "", "context": { "branch": "release/1.2.0", "environment": "staging" } }

GET  /policies
POST /policies   { "policy_id": "...", "name": "...", "applies_to": [...], ... }
GET  /policies/{policy_id}
DELETE /policies/{policy_id}

Response (all /evaluate/* endpoints):
{
  "approved": true,
  "severity_summary": { "critical": 0, "high": 0, "medium": 1, "low": 0 },
  "violations": [
    { "rule": "required-repo-files", "severity": "medium",
      "detail": "LICENSE file is missing", "auto_fix": false }
  ],
  "suggested_fixes": [],
  "report": { ... }
}
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
  /policy/                # Governance and compliance enforcement (port 8005)
  /common/                # Shared utilities
    agent_base.py          # BaseAgent class (LOCAL_MODE logic)
    local_storage.py       # Local replacements for AWS services
    graph_states.py        # LangGraph TypedDict state classes (WorkflowState, ChatState, etc.)
    graphs.py              # LangGraph graph builder functions (build_*_graph)
    version.py             # Version management (reads /VERSION file)
/backend/mcp-server/
  /github/                # MCP GitHub server
/backend/Dockerfile.*     # One Dockerfile per service (accepts --build-arg VERSION=x.y.z)
/docker-compose.local.yml # Local Podman/Docker compose
/VERSION                  # Single source of truth for version number (current: 1.1.0)
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
3. Define a `TypedDict` state class in `graph_states.py`
4. Add a `build_<name>_graph(agent)` builder in `graphs.py`
5. Build the compiled graph in `__init__()`: `self.graph = build_<name>_graph(self)`
6. Invoke per request: `result = await self.graph.ainvoke({...})`
7. Add FastAPI routes and health check at `/health` returning `{"status", "agent", "version", "timestamp"}`
8. Create `backend/Dockerfile.<name>` — copy the `Dockerfile.remediation` pattern, update port + CMD
9. Add service to `docker-compose.local.yml`
10. Update `CLAUDE.md`, `README.md`, and `architecture.md` service lists and diagrams
11. Import `from common.version import __version__` — pass to FastAPI constructor and `/health`
12. Add env var discovery URL (e.g. `POLICY_URL`) to chatbot and any other callers

See the **Policy Agent** section in `CLAUDE.md` for a complete worked example with use cases and implementation checklist.

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

## Technology Glossary

| Technology | Category | Description |
|------------|----------|-------------|
| **Python 3.11** | Language | Primary programming language used for all agents and the MCP server. |
| **FastAPI** | Web Framework | High-performance async Python web framework used to expose REST endpoints on every agent. |
| **Uvicorn** | ASGI Server | Lightning-fast ASGI server that runs each FastAPI application inside its container. |
| **Pydantic** | Data Validation | Data validation and serialization library used for request/response models in all agents. |
| **Anthropic SDK** | AI Client | Official Python SDK for calling the Claude AI API (`anthropic` library). Powers all LLM-driven agent logic. |
| **Claude AI** | Large Language Model | Anthropic's LLM used by agents for intent analysis, code generation, pipeline parsing, remediation analysis, and workflow planning. |
| **LangGraph** | Orchestration | Library from LangChain for building agent workflows as compiled StateGraph instances with conditional edges and retry loops. |
| **LangChain Core** | AI Framework | Foundation library providing abstractions (messages, prompts, output parsers) that LangGraph builds upon. |
| **LangChain Anthropic** | AI Integration | LangChain integration package for Claude AI, used alongside LangGraph for model invocation. |
| **PyGithub** | GitHub Client | Python library for interacting with the GitHub REST API. Used by `BaseAgent` for repository operations. |
| **HTTPX** | HTTP Client | Async-capable HTTP client used for inter-agent communication and MCP server calls. |
| **Jinja2** | Templating | Template engine used by CodeGen and Migration agents to generate code files and workflow YAML. |
| **python-dotenv** | Configuration | Loads environment variables from `.env` files into the process environment at startup. |
| **Podman** | Container Runtime | Daemonless, rootless OCI container engine used to build and run all service containers. Drop-in replacement for Docker. |
| **Podman Compose** | Container Orchestration | Compose tool for Podman that reads `docker-compose.local.yml` to start the full multi-service stack. |
| **Docker Compose** | Container Orchestration | Alternative to Podman Compose; also supported for starting the service stack from `docker-compose.local.yml`. |
| **OCI Containers** | Container Standard | Open Container Initiative standard that both Podman and Docker implement, ensuring image portability. |
| **Model Context Protocol (MCP)** | Agent Protocol | Anthropic's open protocol for connecting AI agents to external tools. Used here to decouple agents from the GitHub API via a dedicated MCP server. |
| **JSON-RPC 2.0** | RPC Protocol | Lightweight remote procedure call protocol used by the MCP GitHub Server for tool invocations. |
| **GitHub Actions** | CI/CD | GitHub's built-in CI/CD platform. The Migration Agent converts Jenkins pipelines into GitHub Actions workflow YAML. |
| **Jenkins** | CI/CD | Java-based CI/CD server. The Migration Agent reads Jenkinsfile pipelines for conversion to GitHub Actions. |
| **GitHub REST API** | API | GitHub's HTTP API used (via PyGithub and MCP) for repository management, file creation, and workflow operations. |
| **pytest** | Testing | Python testing framework used for agent unit and integration tests. Configured with `asyncio_mode = auto`. |
| **asyncio** | Concurrency | Python's built-in async I/O library. All agents use async/await patterns for non-blocking operations. |

---

*Last Updated: 2026-02-18*
*Version: 1.1.0 (local-podman)*
