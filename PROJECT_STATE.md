# DevOps Agentic Framework - Project State Snapshot

**Date**: 2026-02-17
**Branch**: local-podman
**Deployment**: Local Podman containers (no cloud infrastructure)

## Current Deployment Status

### Infrastructure Status: LOCAL

**Runtime**: Podman containers on local machine
**Network**: `agentic-local` (bridge)
**Volume**: `local-data` at `/data`

### Agent Versions

| Agent | Version | Container Name | Port | Image |
|-------|---------|---------------|------|-------|
| MCP GitHub Server | 1.0.5 | mcp-github | 8100 | mcp-github:latest |
| Planner Agent | 1.0.0 | planner-agent | 8000 | planner-agent:latest |
| CodeGen Agent | 1.0.0 | codegen-agent | 8001 | codegen-agent:latest |
| Remediation Agent | 1.0.0 | remediation-agent | 8002 | remediation-agent:latest |
| Chatbot Agent | 1.0.0 | chatbot-agent | 8003 | chatbot-agent:latest |
| Migration Agent | 1.0.0 | migration-agent | 8004 | migration-agent:latest |

### Local Resources

**Compute**:
- 6 Podman containers running on the `agentic-local` bridge network
- Each container runs a FastAPI application with uvicorn

**Storage** (LOCAL_MODE=true replacements):
- DynamoDB replacement: JSON file-backed in-memory store (`/data/db/`)
- S3 replacement: Local filesystem (`/data/artifacts/`)
- EventBridge replacement: No-op with logging
- Secrets Manager replacement: Environment variables (`ANTHROPIC_API_KEY`, `GITHUB_TOKEN`)

**Networking**:
- Container DNS via `agentic-local` bridge network
- Direct port mapping to localhost (8000-8004, 8100)
- No load balancer or API gateway required

### Key Features Implemented

1. **AI-Powered Migration**
   - Jenkins to GitHub Actions pipeline conversion
   - LLM-powered intelligent parsing and generation
   - Platform command cleanup (Windows to Linux)
   - GitHub integration for workflow creation

2. **Multi-Agent System**
   - Planner: Workflow orchestration
   - CodeGen: Microservice generation
   - Remediation: Auto-fix broken pipelines
   - Chatbot: Natural language interface (AADOP branded)
   - Migration: Pipeline conversion

3. **Model Context Protocol (MCP)**
   - Standardized GitHub operations via MCP server
   - Centralized credential management
   - Extensible tool interface

4. **LangGraph Orchestration**
   - All agents use LangGraph StateGraph for workflow execution
   - Conditional routing with fallbacks (LLM to regex, LLM to template)
   - Retry cycles for remediation (up to 3 attempts)

### Configuration Files

**Compose File**: `docker-compose.local.yml`
**Environment**: `.env` file (local, not in git)
**Launcher Script**: `scripts/run-local.sh`

**Dockerfiles**:
- `backend/Dockerfile.planner`
- `backend/Dockerfile.codegen`
- `backend/Dockerfile.remediation`
- `backend/Dockerfile.chatbot`
- `backend/Dockerfile.migration`
- `backend/Dockerfile.mcp-github`

## Quick Start

```bash
# 1. Create .env from template
cp .env.local.template .env
# Edit .env: set ANTHROPIC_API_KEY and GITHUB_TOKEN

# 2. Build images (first time only)
bash scripts/run-local.sh build

# 3. Start services (reuses cached images)
bash scripts/run-local.sh up

# 4. Check health
curl http://localhost:8000/health  # Planner
curl http://localhost:8001/health  # CodeGen
curl http://localhost:8002/health  # Remediation
curl http://localhost:8003/health  # Chatbot
curl http://localhost:8004/health  # Migration
curl http://localhost:8100/health  # MCP GitHub

# 5. Management
bash scripts/run-local.sh status   # Check status
bash scripts/run-local.sh logs     # View logs
bash scripts/run-local.sh down     # Stop everything
bash scripts/run-local.sh rebuild  # Force rebuild and start
```

## Secrets Required

All secrets are passed via `.env` file (gitignored):

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude AI API key |
| `GITHUB_TOKEN` | GitHub personal access token |
| `GITHUB_OWNER` | GitHub username (default: darrylbowler72) |

## Contact & Support

- **Repository**: https://github.com/darrylbowler72/agenticframework
- **Issues**: https://github.com/darrylbowler72/agenticframework/issues
- **Owner**: darrylbowler72

---

**State Saved**: 2026-02-17
**Deployment Mode**: Local (Podman)
