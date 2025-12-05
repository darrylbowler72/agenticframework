# Model Context Protocol (MCP) Architecture

## Overview

The DevOps Agentic Framework implements **Model Context Protocol (MCP)** by Anthropic for standardized tool integration. MCP provides a clean separation between AI agents and external services like GitHub, enabling better maintainability, security, and extensibility.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         API Gateway                              │
│            https://d9bf4clz2f.execute-api...amazonaws.com         │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Application Load Balancer                      │
│                    (internal-dev-agents-alb)                     │
└─────────────────────────────────────────────────────────────────┘
                                 │
                 ┌───────────────┼───────────────┐
                 │               │               │
                 ▼               ▼               ▼
       ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
       │   Planner    │  │   CodeGen    │  │ Remediation  │
       │    Agent     │  │    Agent     │  │    Agent     │
       │  (port 8000) │  │  (port 8001) │  │  (port 8002) │
       └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
              │                 │                 │
              │   MCP Client    │   MCP Client    │   MCP Client
              │                 │                 │
              └─────────────────┼─────────────────┘
                                │
                                ▼
                  ┌─────────────────────────────┐
                  │   MCP GitHub Server         │
                  │   (port 8100)               │
                  │                             │
                  │  - create_repository        │
                  │  - create_file              │
                  │  - get_workflow_run         │
                  │  - list_repositories        │
                  │  - get_repository           │
                  └──────────────┬──────────────┘
                                 │
                                 ▼
                  ┌─────────────────────────────┐
                  │  AWS Secrets Manager        │
                  │  (dev-github-credentials)   │
                  └──────────────┬──────────────┘
                                 │
                                 ▼
                  ┌─────────────────────────────┐
                  │      GitHub API             │
                  │  (api.github.com)           │
                  └─────────────────────────────┘
```

## Components

### 1. MCP GitHub Server

**Purpose**: Centralized GitHub API integration service

**Location**: `backend/mcp-server/github/`

**Technology**:
- FastAPI (Python 3.11)
- PyGithub library
- Boto3 for AWS integration

**Key Features**:
- JSON-RPC 2.0 protocol implementation
- AWS Secrets Manager integration
- Error handling and logging
- Health check endpoint

**Endpoints**:
- `POST /mcp/call` - Main MCP method execution endpoint
- `GET /mcp/info` - Server capabilities and tool listing
- `GET /health` - Health check

**Tools Provided**:

| Tool | Description | Parameters |
|------|-------------|------------|
| `github.create_repository` | Create a new repository | name, description, private, auto_init |
| `github.create_file` | Create/update file in repo | repo_name, file_path, content, message, branch |
| `github.get_workflow_run` | Get GitHub Actions run details | repo_name, run_id |
| `github.list_repositories` | List user repositories | limit |
| `github.get_repository` | Get repository details | repo_name |

### 2. MCP Client Library

**Purpose**: Simplified client interface for agents

**Location**: `backend/agents/common/mcp_client.py`

**Classes**:
- `MCPClient`: Low-level JSON-RPC client
- `GitHubMCPClient`: High-level GitHub operations wrapper

**Features**:
- Async/await support (httpx)
- Automatic error handling
- Service discovery via environment variables
- Connection pooling

**Usage Pattern**:
```python
# Initialize client
github = GitHubMCPClient()

# Call MCP methods
result = await github.create_repository(
    name="my-repo",
    description="Test repo",
    private=True
)
```

### 3. Agent Integration

**Agents using MCP**:
- **CodeGen Agent**: Creates repositories and pushes generated code
- **Remediation Agent**: Fetches workflow logs and analyzes failures
- **Planner Agent**: Orchestrates repository operations

**Integration Points**:
- Agents import `GitHubMCPClient` from common module
- MCP server URL resolved via `MCP_GITHUB_URL` environment variable
- Default: `http://dev-mcp-github:8100` (ECS service discovery)

## Deployment

### ECS Service Configuration

**Service Name**: `dev-mcp-github`
**Task Definition**: `dev-mcp-github-agent`
**Networking**: Private subnets only
**Port**: 8100
**Health Check**: `/health` endpoint

### Environment Variables

```bash
ENVIRONMENT=dev
AWS_REGION=us-east-1
MCP_GITHUB_URL=http://dev-mcp-github:8100  # For agents
```

### AWS Secrets Manager

**Secret**: `dev-github-credentials`

**Structure**:
```json
{
  "token": "ghp_...",
  "owner": "darrylbowler72"
}
```

**IAM Permissions**:
- ECS task role has `secretsmanager:GetSecretValue` on `dev-*` secrets
- MCP server retrieves credentials at startup

## Security

### Authentication Flow

```
1. MCP Server starts
2. Fetches GitHub credentials from Secrets Manager
3. Initializes PyGithub client with PAT
4. Caches client for subsequent requests
5. Agents call MCP server (no credentials needed)
```

### Benefits

- **Centralized Credentials**: Only MCP server has GitHub token access
- **Least Privilege**: Agents don't need GitHub credentials
- **Easy Rotation**: Update token in Secrets Manager, restart MCP server
- **Audit Trail**: All GitHub operations logged in MCP server

### Network Security

- MCP server in private subnet (no internet access required)
- Agents communicate via ECS service discovery
- NAT Gateway used for outbound GitHub API calls
- Security group restricts inbound to port 8100

## Protocol Details

### JSON-RPC 2.0 Request

```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "method": "github.create_repository",
  "params": {
    "name": "my-service",
    "description": "A new microservice",
    "private": true
  }
}
```

### JSON-RPC 2.0 Response (Success)

```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "result": {
    "name": "my-service",
    "full_name": "darrylbowler72/my-service",
    "html_url": "https://github.com/darrylbowler72/my-service",
    "clone_url": "https://github.com/darrylbowler72/my-service.git",
    "default_branch": "main"
  }
}
```

### JSON-RPC 2.0 Response (Error)

```json
{
  "jsonrpc": "2.0",
  "id": "unique-request-id",
  "error": {
    "code": -32603,
    "message": "Repository already exists"
  }
}
```

## Benefits

### 1. Separation of Concerns

- **Agents**: Focus on business logic (workflow orchestration, code generation)
- **MCP Server**: Handles GitHub API complexities (authentication, rate limiting, error handling)

### 2. Standardized Interface

- Consistent API across all agents
- Easy to mock for testing
- Version control for tool definitions

### 3. Extensibility

Add new Git providers without changing agents:
- `mcp-gitlab-server` for GitLab
- `mcp-bitbucket-server` for Bitbucket
- Agents use same client interface

### 4. Maintainability

- Update GitHub logic in one place
- Easier debugging (centralized logs)
- Simpler agent code

### 5. Performance

- Connection pooling in MCP server
- Cached GitHub client
- Reduced agent complexity

## Future Enhancements

### Short Term
- [ ] Add GitLab MCP server
- [ ] Implement request caching
- [ ] Add rate limiting protection
- [ ] Metrics and monitoring

### Long Term
- [ ] Multi-provider routing (GitHub, GitLab, Bitbucket)
- [ ] Webhook support for GitHub events
- [ ] Advanced error recovery
- [ ] Request queueing for rate limit management

## Testing

### Unit Tests

```python
import pytest
from common.mcp_client import GitHubMCPClient

@pytest.mark.asyncio
async def test_create_repository():
    client = GitHubMCPClient("http://localhost:8100")
    repo = await client.create_repository(
        name="test-repo",
        description="Test",
        private=True
    )
    assert repo['name'] == 'test-repo'
```

### Integration Tests

```bash
# Start MCP server locally
cd backend/mcp-server/github
python server.py

# Test with curl
curl -X POST http://localhost:8100/mcp/call \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "github.list_repositories",
    "params": {"limit": 5}
  }'
```

## Troubleshooting

### MCP Server Not Reachable

```bash
# Check ECS service status
aws ecs describe-services \
  --cluster dev-agentic-cluster \
  --services dev-mcp-github \
  --region us-east-1

# Check logs
aws logs tail /aws/ecs/dev-agentic-cluster \
  --follow --filter-pattern mcp-github
```

### GitHub Authentication Errors

```bash
# Verify secret
aws secretsmanager get-secret-value \
  --secret-id dev-github-credentials \
  --region us-east-1

# Test GitHub token
curl -H "Authorization: token ghp_..." \
  https://api.github.com/user
```

### Agent Cannot Connect to MCP

Check environment variables:
```bash
# In agent container
echo $MCP_GITHUB_URL

# Should be: http://dev-mcp-github:8100
```

## References

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Anthropic MCP Documentation](https://docs.anthropic.com/mcp)
- [PyGithub Documentation](https://pygithub.readthedocs.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## Contact

For questions or issues:
- GitHub Issues: https://github.com/darrylbowler72/agenticframework/issues
- Documentation: https://github.com/darrylbowler72/agenticframework/tree/main/docs

---

**Last Updated**: 2024-12-05
**Version**: 1.0.0
**Status**: Implemented
