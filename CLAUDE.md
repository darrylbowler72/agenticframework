# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevOps Agentic Framework - An autonomous, AI-powered DevOps platform that runs locally via Podman/Docker containers. No cloud infrastructure required.

## Core Architecture

### Multi-Agent System

The framework consists of 6 specialized AI agents running as local containers:

1. **Planner Agent** (port 8000) - Orchestrates multi-step workflows
2. **CodeGen Agent** (port 8001) - Generates microservices and infrastructure code
3. **Remediation Agent** (port 8002) - Auto-fixes detected issues in code/workflows
4. **Chatbot Agent** (port 8003) - Natural language interface for DevOps operations
5. **Migration Agent** (port 8004) - Converts Jenkins pipelines to GitHub Actions
6. **MCP GitHub Server** (port 8100) - Model Context Protocol server for GitHub operations

All agents inherit from `BaseAgent` (`backend/agents/common/agent_base.py`) which provides:
- Claude AI API client (via `anthropic` library)
- GitHub API client (via `PyGithub`)
- Local storage backends (DynamoDB, S3, EventBridge, Secrets Manager replacements)
- Structured JSON logging

### LOCAL_MODE

When `LOCAL_MODE=true` (always true in this branch), cloud services are replaced:
- **DynamoDB** -> JSON file-backed in-memory store (`/data/db/`)
- **S3** -> Local filesystem (`/data/artifacts/`)
- **EventBridge** -> No-op with logging
- **Secrets Manager** -> Environment variables (`ANTHROPIC_API_KEY`, `GITHUB_TOKEN`)

Key file: `backend/agents/common/local_storage.py`

### Model Context Protocol (MCP)

The framework uses MCP to separate concerns between agents and GitHub:

```
Agent -> GitHubMCPClient -> MCP GitHub Server -> GitHub API
```

**Key files**:
- `backend/mcp-server/github/server.py` - MCP server implementing GitHub operations
- Service URL: `http://mcp-github:8100` (inter-container)

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
- MCP Servers: `mcp-<service>` (e.g., `mcp-github`)
- Dockerfiles: `backend/Dockerfile.<name>` (e.g., `Dockerfile.planner`, `Dockerfile.mcp-github`)
- Build context: Project root (`.`)

## Key Technical Details

### Agent Implementation Pattern

Each agent (`backend/agents/<agent-name>/main.py`):
1. Extends `BaseAgent`
2. Implements FastAPI application
3. Defines Pydantic models for request/response
4. Implements `process_task()` method for async task processing
5. Uses Claude AI via `self.anthropic_client`
6. Exposes `/health` endpoint

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
- `ANTHROPIC_API_KEY` - Claude AI API key
- `GITHUB_TOKEN` - GitHub personal access token
- `GITHUB_OWNER` - GitHub username (default: darrylbowler72)

### Persistence

Data stored in shared `local-data` volume at `/data`:
- `/data/db/` - JSON files (DynamoDB table replacement)
- `/data/artifacts/` - File storage (S3 replacement)

## Migration Agent Specifics

The Migration Agent converts Jenkins pipelines to GitHub Actions workflows:

- **LLM-based parsing**: Uses Claude to intelligently parse Jenkinsfile instead of regex
- **Step mappings**: Maps Jenkins steps to GitHub Actions (`self.step_mappings`)
- **Plugin mappings**: Maps Jenkins plugins to Actions (`self.plugin_mappings`)
- **Integration**: Can fetch pipelines from live Jenkins instances and push workflows to GitHub

**Key classes**:
- `MigrationAgent` - Main agent logic
- `JenkinsClient` - Jenkins API integration
- `GitHubClient` - GitHub API integration

## Important Conventions

### Agent Development
- All agents use async/await patterns (FastAPI + asyncio)
- Use `BaseAgent` logger (`self.logger.info()`) for structured JSON logs
- Use MCP for GitHub operations (don't call GitHub API directly from agents)
- All containers must expose `/health` endpoint

### Container Deployment
- Use Podman (recommended) or Docker
- All services defined in `docker-compose.local.yml`
- `scripts/run-local.sh` is the primary launcher
- `LOCAL_MODE=true` and `ENVIRONMENT=local` set on all containers

### Version Management
- Agent version in `backend/agents/common/version.py`
- Update version in agent `main.py` FastAPI app if individual versioning needed

## API Reference

### Endpoints (localhost)

- `POST http://localhost:8000/workflows` - Create workflow via Planner Agent
- `POST http://localhost:8001/generate` - Generate microservice via CodeGen Agent
- `POST http://localhost:8002/remediate` - Auto-fix issue via Remediation Agent
- `POST http://localhost:8003/chat` - Chat interface via Chatbot Agent
- `POST http://localhost:8004/migration/migrate` - Convert Jenkins pipeline
- `POST http://localhost:8004/migration/analyze` - Analyze Jenkinsfile
- `GET http://localhost:8004/migration/jenkins/jobs` - List Jenkins jobs
- `GET http://localhost:*/health` - Health check (all agents)

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
