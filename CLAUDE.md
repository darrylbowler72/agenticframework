# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevOps Agentic Framework — An autonomous, AI-powered DevOps platform that runs locally via Podman/Docker containers. No cloud infrastructure required.

## Core Architecture

### Multi-Agent System

The framework consists of 7 specialized AI agents running as local containers:

1. **Planner Agent** (port 8000) — Orchestrates multi-step workflows
2. **CodeGen Agent** (port 8001) — Generates microservices and infrastructure code
3. **Remediation Agent** (port 8002) — Auto-fixes detected issues in code/workflows
4. **Chatbot Agent** (port 8003) — Natural language interface for DevOps operations
5. **Migration Agent** (port 8004) — Converts Jenkins pipelines to GitHub Actions
6. **Policy Agent** (port 8005) — Enforces governance policies and compliance gates
7. **MCP GitHub Server** (port 8100) — Model Context Protocol server for GitHub operations

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
# Policy:            http://localhost:8005/health
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
podman.exe build --build-arg VERSION=1.1.0 -f backend/Dockerfile.policy       -t policy-agent       .
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
podman.exe run -d --name policy-agent      $NET $VOL     -p 8005:8005 $ENV_ARGS policy-agent
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
| `build_policy_graph` | load_policies → scan_content → evaluate_violations → [suggest_fixes] → build_report | Suggests fixes for auto-fixable violations only |

### Service Discovery

Agents find each other via container DNS names on the `agentic-local` network:
- `http://planner-agent:8000`
- `http://codegen-agent:8001`
- `http://remediation-agent:8002`
- `http://migration-agent:8004`
- `http://policy-agent:8005`
- `http://mcp-github:8100`

Configurable via env vars: `PLANNER_URL`, `CODEGEN_URL`, `REMEDIATION_URL`, `MIGRATION_URL`, `POLICY_URL`, `MCP_GITHUB_URL`

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

#### Policy Agent (:8005)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/evaluate` | Evaluate content (code, workflow, repo, deployment) against all applicable policies |
| `POST` | `/evaluate/code` | Validate generated code for security and quality violations |
| `POST` | `/evaluate/workflow` | Validate a GitHub Actions workflow YAML against policy |
| `POST` | `/evaluate/repository` | Validate repository structure and required compliance files |
| `POST` | `/evaluate/deployment` | Gate a deployment request; returns approve/block decision |
| `GET`  | `/policies` | List all stored policy rules |
| `POST` | `/policies` | Create or update a policy rule |
| `GET`  | `/policies/{policy_id}` | Get a specific policy rule by ID |
| `DELETE` | `/policies/{policy_id}` | Remove a policy rule |
| `GET`  | `/health` | Health check |

#### MCP GitHub Server (:8100)
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/mcp/call` | Execute an MCP operation (see MCP Operations table) |
| `GET` | `/mcp/info` | List available tools and their parameters |
| `GET` | `/health` | Health check |

## Policy Agent — Design, Use Cases, and Implementation Guide

### Purpose

The Policy Agent (port 8005) is a governance and compliance layer that evaluates content at every stage of the DevOps pipeline. It acts as a configurable gate that other agents can call before pushing code, creating repositories, generating workflows, or dispatching deployments.

> **Status**: Documented design — ready to implement. See [Agent Implementation Pattern](#agent-implementation-pattern) for code patterns.

### Architecture

```
Chatbot / CodeGen / Migration / Planner / Remediation
                    |
          POST /evaluate/<content-type>
                    |
             Policy Agent (:8005)
                    |
          LangGraph Policy Graph
                    |
    +-----------+------------------+
    |           |                  |
  APPROVE     WARN            BLOCK
    |           |                  |
    v           v                  v
 caller       caller+log       caller + reason
continues    continues         returns 422
```

### LangGraph Policy Graph

**File**: `backend/agents/common/graphs.py` → `build_policy_graph(agent)`
**State**: `backend/agents/common/graph_states.py` → `PolicyState`

```
load_policies
     |
scan_content (Claude analyses content against loaded policy rules)
     |
evaluate_violations (classify: critical/high/medium/low, auto-fixable?)
     |
     +-- (violations & auto_fixable=True) --> suggest_fixes --> build_report --> END
     |
     +-- (violations & auto_fixable=False) -----------------> build_report --> END
     |
     +-- (no violations) ------------------------------------> build_report --> END
```

| Node | Method | Description |
|------|--------|-------------|
| `load_policies` | `_load_policies(content_type)` | Read applicable policies from `/data/db/local-policies.json` |
| `scan_content` | `_scan_content(content, policies)` | Use Claude to find violations against each rule |
| `evaluate_violations` | `_evaluate_violations(scan_results)` | Classify severity, set `approved` flag |
| `suggest_fixes` | `_suggest_fixes(violations)` | Claude generates concrete code-level fix suggestions |
| `build_report` | `_build_report(state)` | Produce structured JSON report with decision, violations, fixes |

### PolicyState TypedDict

```python
class PolicyState(TypedDict, total=False):
    # Input
    content_type: str          # "code" | "workflow" | "repository" | "deployment"
    content: str               # The raw content to evaluate
    context: Dict[str, Any]    # repo_name, framework, branch, caller_agent, etc.
    policy_ids: Optional[List[str]]  # Specific policies to apply, or None for all

    # Policy loading
    policies: List[Dict[str, Any]]

    # Scanning
    scan_results: List[Dict[str, Any]]   # Raw findings from Claude

    # Evaluation
    violations: List[Dict[str, Any]]     # Categorised violations with severity
    auto_fixable: bool

    # Fix suggestions
    suggested_fixes: List[Dict[str, Any]]

    # Output
    approved: bool             # True = APPROVE, False = BLOCK
    severity_summary: Dict[str, int]  # {"critical": 0, "high": 1, "medium": 2, "low": 0}
    report: Dict[str, Any]
    error: Optional[str]
```

### Policy Storage Format

Policies are stored in `/data/db/local-policies.json` (via `LocalDynamoDB` table `local-policies`).

```json
{
  "policy_id": "no-hardcoded-secrets",
  "name": "No Hardcoded Secrets",
  "description": "Code and workflows must not contain API keys, passwords, or tokens.",
  "applies_to": ["code", "workflow"],
  "severity": "critical",
  "auto_fix": false,
  "blocking": true,
  "enabled": true,
  "rules": [
    "No string literals matching common API key patterns (e.g. sk-, ghp_, AKIA)",
    "No variable assignments with names containing 'password', 'secret', 'token', 'key' and hardcoded string values",
    "No connection strings with embedded credentials"
  ],
  "remediation_hint": "Use environment variables or GitHub Secrets instead of hardcoded values."
}
```

**Key fields**:
- `applies_to`: Which `content_type` values trigger this policy
- `blocking`: If `true` and severity is `critical`/`high`, the request is rejected (`approved=False`)
- `auto_fix`: Whether the `suggest_fixes` node runs for violations of this policy
- `rules`: Human-readable rules passed verbatim to Claude for analysis

### Default Policies (Seed Data)

The agent ships with these default policies pre-loaded in `/data/db/local-policies.json`:

| Policy ID | Applies To | Severity | Blocking | Description |
|-----------|-----------|----------|----------|-------------|
| `no-hardcoded-secrets` | code, workflow | critical | yes | No API keys, passwords, tokens in content |
| `required-repo-files` | repository | medium | no | README.md, .gitignore, LICENSE must exist |
| `workflow-has-checkout` | workflow | high | yes | GitHub Actions workflow must use `actions/checkout` |
| `workflow-no-sudo` | workflow | medium | no | Workflows should not run arbitrary `sudo` commands |
| `naming-conventions` | repository | low | no | Repo names must be kebab-case, no spaces |
| `branch-protection-required` | repository | medium | no | main/develop branches should have protection rules |
| `dependency-pinning` | workflow | medium | no | Action versions must be pinned (no `@main` or `@latest`) |

### Agent Implementation Checklist

When implementing `backend/agents/policy/main.py`:

1. `class PolicyAgent(BaseAgent)` — extend `BaseAgent("policy")`
2. `FastAPI(title="Policy Agent", version=__version__)` — import `from common.version import __version__`
3. `self.graph = build_policy_graph(self)` in `__init__()`
4. Implement `process_task()` — accept `{"content_type", "content", "context"}`, invoke graph
5. Implement `_load_policies(content_type)` — filter JSON db by `applies_to`
6. Implement `_scan_content(content, policies)` — single `call_claude()` call with rules in system prompt
7. Implement `_evaluate_violations(scan_results)` — classify, count by severity, set `approved`
8. Implement `_suggest_fixes(violations)` — `call_claude()` to produce code-level suggestions
9. Implement `_build_report(state)` — return structured JSON
10. Seed default policies on first startup (check if `/data/db/local-policies.json` exists)
11. Expose all endpoints listed in [API Reference](#policy-agent-8005)
12. `/health` must return `{"status": "healthy", "agent": "policy", "version": __version__, "timestamp": ...}`

**Dockerfile**: `backend/Dockerfile.policy` — follow the same pattern as `Dockerfile.remediation`
**Port**: 8005
**Container name**: `policy-agent`
**Env var**: `POLICY_URL` (default: `http://policy-agent:8005`)

### Calling the Policy Agent from Other Agents

```python
import httpx

async def check_policy(content_type: str, content: str, context: dict) -> dict:
    policy_url = os.getenv("POLICY_URL", "http://policy-agent:8005")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{policy_url}/evaluate/{content_type}",
            json={"content": content, "context": context}
        )
        return resp.json()
    # Returns: {"approved": bool, "severity_summary": {...}, "violations": [...], "suggested_fixes": [...]}
```

### Use Cases

#### UC-1: Prevent Hardcoded Secrets in Generated Code

**Trigger**: CodeGen Agent finishes `_enhance_with_ai()` and before `push_to_repo()`
**Actor**: `codegen-agent` calls `POST /evaluate/code`
**Input**: Generated Python/Node.js service files
**Policy**: `no-hardcoded-secrets` (critical, blocking)
**Flow**:
1. CodeGen calls Policy Agent with the generated file contents
2. Claude scans for API key patterns, password variables, connection strings
3. If any found: Policy Agent returns `approved=False`, violation list, and env-var fix suggestions
4. CodeGen logs the violation, skips pushing to GitHub, returns an error to the caller
5. If none found: `approved=True`, CodeGen proceeds to push files to GitHub

**Example violation**:
```json
{"rule": "no-hardcoded-secrets", "severity": "critical", "file": "src/config.py",
 "line": 12, "match": "API_KEY = 'sk-abc123'",
 "fix": "Replace with: API_KEY = os.getenv('API_KEY')"}
```

---

#### UC-2: Enforce Required Repository Files After Bootstrap

**Trigger**: Chatbot Agent completes `setup_project` (after files are pushed to GitHub)
**Actor**: `chatbot-agent` calls `POST /evaluate/repository`
**Input**: List of file paths pushed to GitHub + repo name
**Policy**: `required-repo-files` (medium, non-blocking — warns but continues)
**Flow**:
1. Chatbot calls Policy Agent with `{"files": [...], "repo_name": "web-frontend"}`
2. Policy Agent checks that `README.md`, `.gitignore`, `LICENSE` are present
3. Missing files are returned as `medium` severity warnings
4. Chatbot appends a compliance notice to its response: "⚠ Missing LICENSE file — consider adding one"
5. Repo is still accessible; user gets actionable guidance

---

#### UC-3: Validate GitHub Actions Workflow Security

**Trigger**: Migration Agent finishes generating a GitHub Actions workflow YAML
**Actor**: `migration-agent` calls `POST /evaluate/workflow`
**Input**: Raw YAML string of the generated workflow
**Policies**: `workflow-has-checkout` (high, blocking), `workflow-no-sudo` (medium, non-blocking), `dependency-pinning` (medium, non-blocking)
**Flow**:
1. Migration Agent calls Policy Agent before returning the workflow to the user
2. Policy Agent scans the YAML: checks for `actions/checkout`, `sudo` usage, pinned action versions
3. If `actions/checkout` missing: `approved=False`, migration result includes the violation
4. For non-blocking warnings (sudo, pinning): workflow is returned with a warning list
5. User sees: "Workflow generated. Warnings: 2 actions use unpinned versions (`@latest`)."

---

#### UC-4: Deployment Gate

**Trigger**: Planner Agent is about to dispatch a `deploy` task
**Actor**: `planner-agent` calls `POST /evaluate/deployment`
**Input**: `{"branch": "release/1.2.0", "repo": "web-frontend", "environment": "staging"}`
**Policies**: All policies with `applies_to: ["deployment"]`
**Flow**:
1. Planner calls Policy Agent before dispatching the deploy task event
2. Policy Agent uses Claude + GitHub API (via MCP) to check:
   - Branch exists and is not `main`/`develop` for staging deployments
   - No open critical security advisories on the repo
   - GitHub Actions CI passed on the branch HEAD
3. If all pass: `approved=True`, Planner dispatches the task
4. If blocked: `approved=False`, Planner returns `{"status": "blocked", "reason": "...", "violations": [...]}`

---

#### UC-5: Branch Protection Enforcement

**Trigger**: Chatbot Agent calls `create_gitflow` to set up branching on a new repo
**Actor**: `chatbot-agent` calls `POST /evaluate/repository`
**Input**: Repo name + list of created branches
**Policy**: `branch-protection-required` (medium, non-blocking)
**Flow**:
1. After creating gitflow branches, Chatbot calls Policy Agent
2. Policy Agent checks GitHub (via MCP `github.get_repository`) whether `main`/`develop` have branch protection enabled
3. If not configured: returns warning with step-by-step instructions to enable protection via GitHub UI
4. Chatbot appends to response: "⚠ Branch protection is not enabled on `main`. Enable it in Settings → Branches."

---

#### UC-6: Naming Convention Compliance

**Trigger**: Any repo or branch creation via Chatbot
**Actor**: `chatbot-agent` calls `POST /evaluate/repository`
**Input**: Proposed repo name or branch name
**Policy**: `naming-conventions` (low, non-blocking)
**Flow**:
1. Before creating the repo, Chatbot calls Policy Agent with the proposed name
2. Policy Agent checks: kebab-case, no uppercase, no spaces, length 3–50 chars
3. If violation: return `approved=True` (non-blocking) but include a `suggested_name` in the response
4. Chatbot uses the suggestion: "Normalised repo name from `Web Frontend` to `web-frontend`."

---

#### UC-7: Dependency Vulnerability Scanning

**Trigger**: CodeGen or `setup_project` creates a `requirements.txt` or `package.json`
**Actor**: `codegen-agent` or `chatbot-agent` calls `POST /evaluate/code`
**Input**: Contents of `requirements.txt` / `package.json`
**Policy**: `dependency-scanning` (medium, non-blocking)
**Flow**:
1. After template generation, the calling agent passes dependency files to Policy Agent
2. Claude analyses declared package versions for known insecure patterns (e.g. very old Django, Flask<2, node packages with known CVEs in training data)
3. Returns warnings with suggested version upgrades
4. Calling agent includes the warnings in the response to the user

---

### Integration Points Summary

| Caller Agent | When | Endpoint | Policy |
|-------------|------|----------|--------|
| `codegen-agent` | Before `push_to_repo` | `/evaluate/code` | no-hardcoded-secrets, dependency-scanning |
| `chatbot-agent` | After `setup_project` | `/evaluate/repository` | required-repo-files, naming-conventions, branch-protection-required |
| `chatbot-agent` | After workflow generation | `/evaluate/workflow` | workflow-has-checkout, dependency-pinning |
| `migration-agent` | Before returning workflow | `/evaluate/workflow` | workflow-has-checkout, workflow-no-sudo, dependency-pinning |
| `planner-agent` | Before dispatching deploy | `/evaluate/deployment` | All deployment policies |
| `remediation-agent` | After auto-fix | `/evaluate/code` | no-hardcoded-secrets |

---

### Documentation Completeness Assessment

The existing documentation provides **sufficient detail** to implement the Policy Agent from scratch:

| Requirement | Documented? | Location |
|-------------|-------------|----------|
| BaseAgent inheritance pattern | ✅ | Agent Implementation Pattern section |
| FastAPI structure + Pydantic models | ✅ | Agent Implementation Pattern section |
| LangGraph StateGraph pattern | ✅ | graphs.py + graph_states.py |
| Port assignment (8005 available) | ✅ | Multi-Agent System section |
| Dockerfile pattern with OCI labels | ✅ | Docker Image Naming Convention + Manual Build |
| Version management (`__version__`) | ✅ | Version Management section |
| Claude API usage (`call_claude()`) | ✅ | agent_base.py |
| Local storage (`/data/db/`) | ✅ | LOCAL_MODE section |
| Service discovery + env vars | ✅ | Service Discovery section |
| MCP GitHub operations for repo checks | ✅ | MCP Operations table |
| Structured logging (`self.logger`) | ✅ | agent_base.py |
| `process_task()` abstract method | ✅ | agent_base.py |
| docker-compose service entry | ✅ | docker-compose.local.yml (to be added) |

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
