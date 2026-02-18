# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevOps Agentic Framework — An autonomous, AI-powered DevOps platform that runs locally via Podman/Docker containers. No cloud infrastructure required.

## Core Architecture

### Multi-Agent System

The framework consists of 6 specialized AI agents running as local containers:

1. **Planner Agent** (port 8000) — Orchestrates multi-step workflows
2. **CodeGen Agent** (port 8001) — Generates microservices and infrastructure code
3. **Remediation Agent** (port 8002) — Auto-fixes detected issues in code/workflows
4. **Chatbot Agent** (port 8003) — Natural language interface for DevOps operations
5. **Migration Agent** (port 8004) — Converts Jenkins pipelines to GitHub Actions
6. **MCP GitHub Server** (port 8100) — Model Context Protocol server for GitHub operations

All agents inherit from `BaseAgent` (`backend/agents/common/agent_base.py`) which provides:
- Claude AI API client (via `anthropic` library)
- GitHub API client (via `PyGithub`)
- Local storage backends (DynamoDB, S3, EventBridge, Secrets Manager replacements)
- Structured JSON logging

### LOCAL_MODE

When `LOCAL_MODE=true` (always true in this branch), cloud services are replaced:
- **DynamoDB** → JSON file-backed in-memory store (`/data/db/`)
- **S3** → Local filesystem (`/data/artifacts/`)
- **EventBridge** → No-op with logging
- **Secrets Manager** → Environment variables (`ANTHROPIC_API_KEY`, `GITHUB_TOKEN`)

Key file: `backend/agents/common/local_storage.py`

### Model Context Protocol (MCP)

The framework uses MCP to separate concerns between agents and GitHub:

```
Agent -> call_mcp_github() -> MCP GitHub Server -> GitHub API
```

**Key files**:
- `backend/mcp-server/github/server.py` — MCP server implementing GitHub operations
- Service URL: `http://mcp-github:8100` (inter-container)
- Env var: `MCP_GITHUB_URL` (default: `http://mcp-github:8100`)

**MCP Operations** (`POST /mcp/call` with `method` field):
| Method | Description |
|--------|-------------|
| `github.create_repository` | Create a new GitHub repository |
| `github.create_file` | Create a new file in a repository |
| `github.update_file` | Update an existing file (auto-fetches SHA, falls back to create if missing) |
| `github.create_branch` | Create a branch from another branch |
| `github.get_workflow_run` | Get GitHub Actions run details and job logs |
| `github.list_repositories` | List user repositories |
| `github.get_repository` | Get repository details |

**`call_mcp_github()` return format**: `{"success": True, "result": {...}}` on success, `{"success": False, "error": {...}}` on failure. Always check `result.get("success")`, never `result.get("path")`.

### Agent Communication Flow

```
User Browser -> Chatbot (:8003) -> Claude AI -> Other Agents via HTTP
                                                      |
                                            Shared Volume /data/
```

## Build and Deploy

### Prerequisites

- Podman or Docker with compose support
- Python 3.11+
- Anthropic API key
- GitHub personal access token

### Setup and Run

```bash
# 1. Create .env from template
cp .env.local.template .env
# Edit .env: set ANTHROPIC_API_KEY and GITHUB_TOKEN

# 2. Start all services
bash scripts/run-local.sh up

# 3. Access services
# Chatbot UI:        http://localhost:8003
# Planner:           http://localhost:8000/health
# CodeGen:           http://localhost:8001/health
# Remediation:       http://localhost:8002/health
# Migration:         http://localhost:8004/health
# MCP GitHub:        http://localhost:8100/health

# 4. Management
bash scripts/run-local.sh logs     # View logs
bash scripts/run-local.sh status   # Check status
bash scripts/run-local.sh down     # Stop everything
bash scripts/run-local.sh restart  # Restart all
```

### Manual Build (Podman Desktop / Windows WSL2)

`podman-compose` v1.5.0 has a known bug ignoring `dockerfile:` keys in compose build sections. Build images manually instead:

```bash
podman.exe machine start   # Ensure Podman machine is running

# Build each image (run from project root)
podman.exe build --build-arg VERSION=1.1.0 -f backend/Dockerfile.mcp-github   -t mcp-github-agent   .
podman.exe build --build-arg VERSION=1.1.0 -f backend/Dockerfile.planner      -t planner-agent      .
podman.exe build --build-arg VERSION=1.1.0 -f backend/Dockerfile.codegen      -t codegen-agent      .
podman.exe build --build-arg VERSION=1.1.0 -f backend/Dockerfile.remediation  -t remediation-agent  .
podman.exe build --build-arg VERSION=1.1.0 -f backend/Dockerfile.migration    -t migration-agent    .
podman.exe build --build-arg VERSION=1.1.0 -f backend/Dockerfile.chatbot      -t chatbot-agent      .

# Create network and volume (first time only)
podman.exe network create agentic-local
podman.exe volume create local-data

# Start containers
ENV_ARGS="--env-file .env -e LOCAL_MODE=true -e ENVIRONMENT=local \
  -e MCP_GITHUB_URL=http://mcp-github:8100 \
  -e PLANNER_URL=http://planner-agent:8000 \
  -e CODEGEN_URL=http://codegen-agent:8001 \
  -e REMEDIATION_URL=http://remediation-agent:8002 \
  -e MIGRATION_URL=http://migration-agent:8004"
NET="--network agentic-local"
VOL="-v local-data:/data"

podman.exe run -d --name mcp-github        $NET          -p 8100:8100 $ENV_ARGS mcp-github-agent
podman.exe run -d --name planner-agent     $NET $VOL     -p 8000:8000 $ENV_ARGS planner-agent
podman.exe run -d --name codegen-agent     $NET $VOL     -p 8001:8001 $ENV_ARGS codegen-agent
podman.exe run -d --name remediation-agent $NET $VOL     -p 8002:8002 $ENV_ARGS remediation-agent
podman.exe run -d --name migration-agent   $NET $VOL     -p 8004:8004 $ENV_ARGS migration-agent
podman.exe run -d --name chatbot-agent     $NET $VOL     -p 8003:8003 $ENV_ARGS chatbot-agent
```

## Development

### Local Agent Development

```bash
# Install dependencies
cd backend
pip install -r agents/common/requirements.txt

# Set environment
export LOCAL_MODE=true
export ENVIRONMENT=local
export ANTHROPIC_API_KEY=your-key
export GITHUB_TOKEN=your-token

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
- MCP Servers: `mcp-<service>-agent` (e.g., `mcp-github-agent`)
- Dockerfiles: `backend/Dockerfile.<name>` (e.g., `Dockerfile.planner`, `Dockerfile.mcp-github`)
- Build context: Project root (`.`)
- All Dockerfiles accept `--build-arg VERSION=x.y.z` and embed OCI image labels

## Key Technical Details

### Agent Implementation Pattern

Each agent (`backend/agents/<agent-name>/main.py`):
1. Extends `BaseAgent`
2. Implements FastAPI application
3. Defines Pydantic models for request/response
4. Builds a LangGraph compiled graph in `__init__()` via `build_<agent>_graph(self)`
5. Invokes the graph per request via `await self.graph.ainvoke(state_dict)`
6. Implements `process_task()` method for async task processing
7. Uses Claude AI via `self.anthropic_client`
8. Exposes `/health` endpoint returning `{"status", "agent", "version", "timestamp"}`

### LangGraph Orchestration

Agent workflows are defined as LangGraph StateGraph instances:
- **State classes**: `backend/agents/common/graph_states.py` — TypedDict classes defining the data flowing through each graph
- **Graph builders**: `backend/agents/common/graphs.py` — Factory functions that wire agent methods as graph nodes
- **Entry point**: `await self.graph.ainvoke({...})` replaces imperative method chains

**Graph summary:**

| Graph | Nodes | Key behaviour |
|-------|-------|---------------|
| `build_planner_graph` | plan_tasks → store_workflow → dispatch_tasks | Falls back from LLM plan → regex plan |
| `build_migration_graph` | parse_llm → generate_llm → cleanup_platform → build_report | Falls back to template if LLM fails |
| `build_chatbot_graph` | analyze_intent → [execute_action] → compose_response | Skips execute_action if `action_needed=false` |
| `build_remediation_graph` | fetch_logs → analyze_failure → find_playbook → execute_playbook → verify → notify | Retries execute_playbook up to 3 times |
| `build_codegen_graph` | generate_service → generate_common_files → store_artifacts | Linear pipeline |

### Service Discovery

Agents find each other via container DNS names on the `agentic-local` network:
- `http://planner-agent:8000`
- `http://codegen-agent:8001`
- `http://remediation-agent:8002`
- `http://migration-agent:8004`
- `http://mcp-github:8100`

Configurable via env vars: `PLANNER_URL`, `CODEGEN_URL`, `REMEDIATION_URL`, `MIGRATION_URL`, `MCP_GITHUB_URL`

### Secrets via Environment Variables

All secrets are passed via `.env` file (gitignored):
- `ANTHROPIC_API_KEY` — Claude AI API key
- `GITHUB_TOKEN` — GitHub personal access token
- `GITHUB_OWNER` — GitHub username (default: darrylbowler72)

### Persistence

Data stored in shared `local-data` volume at `/data`:
- `/data/db/` — JSON files (DynamoDB table replacement)
- `/data/artifacts/` — File storage (S3 replacement)

## Chatbot Agent — Detailed Features

### Intent Detection (`analyze_intent`)

Classifies user messages into intents: `workflow | codegen | remediation | github | jenkins | migration | help | general`

Claude returns structured JSON at temperature 0.1. The parser uses a **4-attempt repair chain** to handle malformed responses:
1. Direct `json.loads` after stripping markdown fences
2. Extract first complete `{...}` block and retry
3. Repair literal newlines/tabs inside JSON string values (common when Claude has long conversation context), then retry
4. Regex extraction of `intent`, `action_needed`, `parameters` as last resort

**Context trimming**: assistant messages in session history are capped at 200 chars to prevent prior completed tasks from confusing intent detection in subsequent requests.

### GitHub Operations (`execute_action` → `intent == "github"`)

| Operation | `template_framework` values | Description |
|-----------|----------------------------|-------------|
| `create_repo` | — | Create a new repository |
| `delete_repo` | — | Delete a repository |
| `list_repos` | — | List user repositories |
| `create_branch` | — | Create a single branch |
| `create_gitflow` | — | Create gitflow branches (develop, release/1.0.0, hotfix/initial) |
| `setup_project` | `python\|fastapi\|flask\|django\|nodejs\|express\|react\|angular\|vue\|nextjs\|none` | Full project bootstrap |

### `setup_project` Operation

The most complex chatbot action — creates a complete project from scratch:

1. **Create repo** via `github.create_repository` (with `auto_init=True`)
2. **Wait 3 s** for GitHub to initialise the default branch
3. **Create gitflow branches**: `develop`, `release/1.0.0`
4. **Generate template** via `_generate_project_template(framework, repo_name)`:
   - **LLM Call 1 — Code files**: Returns JSON `{path: content}`. Includes `main.py`/`requirements.txt` (Python) or `src/index.js`/`package.json` (Node.js)
   - **LLM Call 2 — CI/CD workflow**: Returns raw YAML directly (avoids YAML-in-JSON escaping issues)
   - Falls back to hardcoded templates if either LLM call fails
5. **Push files** to `develop` branch via `github.update_file` MCP (3 retries per file, 0.5 s between files)

**Framework-aware CI/CD** (`_build_gitflow_workflow`):
- Python/FastAPI/Flask/Django: `pip install -r requirements.txt` + `python -m pytest`
- Node.js/Express/React/Angular/Vue/Next.js: `npm install` + `npm test`
- Gitflow trigger branches: `develop`, `release/**`, `hotfix/**`
- Jobs: test → build → deploy-dev (develop only) → deploy-staging (release/** only)

**Important**: Generated workflows use `npm install`, **not** `npm ci` — `npm ci` requires a committed `package-lock.json` which bootstrapped projects don't have.

## Migration Agent Specifics

The Migration Agent converts Jenkins pipelines to GitHub Actions workflows:

- **LLM-based parsing**: Uses Claude to intelligently parse Jenkinsfile instead of regex
- **Step mappings**: Maps Jenkins steps to GitHub Actions (`self.step_mappings`)
- **Plugin mappings**: Maps Jenkins plugins to Actions (`self.plugin_mappings`)
- **Integration**: Can fetch pipelines from live Jenkins instances and push workflows to GitHub

**Key classes**:
- `MigrationAgent` — Main agent logic
- `JenkinsClient` — Jenkins API integration
- `GitHubClient` — GitHub API integration

## Version Management

- **Single source of truth**: `VERSION` file at project root (current: `1.1.0`)
- **Runtime reading**: `backend/agents/common/version.py` reads `VERSION` via `get_version()`:
  1. `AGENT_VERSION` environment variable (for per-agent overrides)
  2. `/VERSION` file in container (copied from project root by each Dockerfile)
  3. Default fallback `"1.0.0"`
- **Usage**: All agents import `from common.version import __version__` and pass it to both the FastAPI constructor and `/health` endpoint response
- **MCP server**: Uses its own `_get_version()` function (reads `/VERSION`, no `common` dependency)
- **Docker labels**: All Dockerfiles accept `--build-arg VERSION=x.y.z` and set `org.opencontainers.image.version`
- **To bump version**: Update `VERSION` file only — all agents pick it up automatically on next build

## API Reference

### Endpoints (localhost)

#### Planner Agent (:8000)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/workflows` | Create and dispatch a new workflow |
| `GET` | `/workflows/{workflow_id}` | Get workflow status |
| `GET` | `/health` | Health check |

#### CodeGen Agent (:8001)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/generate` | Generate microservice code |
| `GET` | `/ready` | Readiness check |
| `GET` | `/health` | Health check |

#### Remediation Agent (:8002)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/remediate` | Analyse and auto-fix a CI/CD failure |
| `POST` | `/webhooks/github/workflow` | GitHub Actions webhook receiver |
| `GET` | `/health` | Health check |

#### Chatbot Agent (:8003)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | Send a message (main interface) |
| `GET` | `/session/{session_id}` | Retrieve session history |
| `GET` | `/api/agents/health` | Health + version of all 6 services |
| `GET` | `/` | Chatbot UI (HTML) |
| `GET` | `/health` | Health check |

#### Migration Agent (:8004)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/migrate` | Convert Jenkinsfile content to GitHub Actions |
| `POST` | `/analyze` | Analyse a Jenkinsfile |
| `GET` | `/migration/jenkins/jobs` | List all Jenkins jobs |
| `GET` | `/migration/jenkins/jobs/{job_name}` | Get specific Jenkins job details |
| `POST` | `/migration/jenkins/migrate-job` | Migrate a Jenkins job to GitHub Actions |
| `POST` | `/migration/jenkins/create-job` | Create a job in Jenkins |
| `GET` | `/migration/jenkins/test` | Test Jenkins connection |
| `GET` | `/migration/github/test` | Test GitHub connection |
| `GET` | `/migration/integration/test` | Test Jenkins→GitHub integration end-to-end |
| `GET` | `/health` | Health check |

#### MCP GitHub Server (:8100)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/mcp/call` | Execute an MCP operation (see MCP Operations table) |
| `GET` | `/mcp/info` | List available tools and their parameters |
| `GET` | `/health` | Health check |

## Common Troubleshooting

### Agent Not Starting
1. Check logs: `bash scripts/run-local.sh logs`
2. Verify `.env` file has valid `ANTHROPIC_API_KEY` and `GITHUB_TOKEN`
3. Check if ports are already in use on host

### MCP Connection Errors
- MCP server runs at `http://mcp-github:8100` (container-to-container)
- Ensure mcp-github container is healthy: `curl http://localhost:8100/health`
- Check `MCP_GITHUB_URL` environment variable

### Container Build Failures
- Ensure Podman/Docker is running
- Check build context is project root (not `backend/`)
- Try: `bash scripts/run-local.sh down` then `bash scripts/run-local.sh up`

### Chatbot Returns "Please let me know if you need anything else!" Without Acting
- Claude returned JSON with literal newlines in the `response` field — the 4-attempt JSON repair handles this
- Check chatbot logs for `"LLM code generation failed"` or `"All repair attempts failed"`
- If persistent: long session history can confuse intent detection — start a fresh session

### GitHub Actions Workflow Failures
- Use `npm install` not `npm ci` — `npm ci` requires a committed `package-lock.json`
- Default `package.json` test script exits 1 — `setup_project` patches this to `echo 'No tests yet' && exit 0`
- If a repo was bootstrapped before this fix, update `package.json` test script manually
