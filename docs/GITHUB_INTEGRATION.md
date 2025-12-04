# GitHub Integration Guide

## Overview

The DevOps Agentic Framework is fully integrated with GitHub for repository management, code generation, and CI/CD pipeline remediation. All agents use the configured GitHub account for their operations.

## Configured Account

**GitHub Account**: [darrylbowler72](https://github.com/darrylbowler72)

All agents have been configured to use this account for:
- Creating new repositories
- Pushing generated code
- Fetching workflow logs
- Monitoring CI/CD pipelines

## Configuration

### AWS Secrets Manager

The GitHub Personal Access Token (PAT) is securely stored in AWS Secrets Manager:

```bash
# Secret Name
dev-github-credentials

# Secret Structure
{
  "token": "ghp_...",
  "owner": "darrylbowler72"
}

# View secret (requires AWS permissions)
aws secretsmanager get-secret-value \
  --secret-id dev-github-credentials \
  --region us-east-1
```

### Required Token Scopes

The GitHub PAT must have the following scopes:
- `repo` (all) - Full control of private repositories
- `workflow` - Update GitHub Action workflows
- `admin:repo_hook` - Manage repository webhooks

### IAM Permissions

ECS task roles have permissions to access the GitHub credentials:

```hcl
# Task execution role (iac/terraform/modules/ecs/main.tf:52-68)
secretsmanager:GetSecretValue on arn:aws:secretsmanager:*:*:secret:${environment}-*

# Task role (iac/terraform/modules/ecs/main.tf:123-127)
secretsmanager:GetSecretValue on all resources
```

## Agent Integration

### BaseAgent Class

All agents inherit GitHub client initialization from `backend/agents/common/agent_base.py`:

```python
async def _get_github_client(self) -> tuple[Github, str]:
    """
    Get or create GitHub API client.

    Returns:
        Tuple of (Github client, owner username)
    """
    if self._github_client is None:
        secret = await self.get_secret('github-credentials')
        token = secret.get('token') or secret.get('github_token')
        owner = secret.get('owner', 'darrylbowler72')

        self._github_client = Github(token)
        self._github_owner = owner

        # Test authentication
        user = self._github_client.get_user()
        self.logger.info(f"GitHub client initialized for user: {user.login}")

    return self._github_client, self._github_owner
```

### CodeGen Agent

**Purpose**: Generates microservice code and creates GitHub repositories

**Implementation**: `backend/agents/codegen/main.py:215-270`

**Features**:
- Creates private repositories under darrylbowler72
- Pushes generated code as initial commit
- Supports multiple programming languages (Python, Node.js, Go, Java)
- Generates complete microservice structure (API, tests, Docker, CI/CD)

**Usage Example**:

```bash
curl -X POST https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/generate \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "my-awesome-service",
    "language": "python",
    "database": "postgresql",
    "api_type": "rest"
  }'
```

**Expected Output**:
- New repository created at: `https://github.com/darrylbowler72/my-awesome-service`
- Initial commit with complete microservice code
- GitHub Actions workflow for CI/CD

### Remediation Agent

**Purpose**: Monitors GitHub Actions workflows and automatically remediates failures

**Implementation**: `backend/agents/remediation/main.py:185-235`

**Features**:
- Fetches workflow run logs from GitHub Actions
- Analyzes failure patterns using Claude AI
- Generates fixes for common issues:
  - Missing dependencies
  - Configuration errors
  - Test failures
  - Build errors
- Webhook endpoint for GitHub Actions notifications

**Webhook Configuration**:

To enable automatic remediation, add a webhook to your repository:

```
URL: https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/webhooks/github/workflow
Content type: application/json
Events: Workflow runs
```

**Manual Remediation**:

```bash
curl -X POST https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/remediate \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline_id": 123456789,
    "project_id": "darrylbowler72/my-service",
    "pipeline_url": "https://github.com/darrylbowler72/my-service/actions/runs/123456789"
  }'
```

### Planner Agent

**Purpose**: Orchestrates multi-step workflows involving GitHub operations

**Implementation**: `backend/agents/planner/main.py`

**Features**:
- Plans complex DevOps workflows
- Coordinates CodeGen and Remediation agents
- Manages repository creation and CI/CD setup

## Testing the Integration

### 1. Test CodeGen Agent

Create a test microservice:

```bash
# Generate a Python microservice
curl -X POST https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/generate \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "test-python-api",
    "language": "python",
    "database": "postgresql",
    "api_type": "rest"
  }'
```

**Expected Result**:
- New repository: `https://github.com/darrylbowler72/test-python-api`
- Files: `main.py`, `requirements.txt`, `Dockerfile`, `.github/workflows/ci.yml`

### 2. Test Remediation Agent

Trigger a workflow failure and remediate:

```bash
# Create a repository with a failing workflow
# Then trigger remediation
curl -X POST https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/remediate \
  -H "Content-Type: application/json" \
  -d '{
    "pipeline_id": <workflow_run_id>,
    "project_id": "darrylbowler72/test-python-api",
    "pipeline_url": "https://github.com/darrylbowler72/test-python-api/actions/runs/<run_id>"
  }'
```

**Expected Result**:
- Agent fetches workflow logs
- Analyzes failure using Claude AI
- Proposes fixes (returned in response)

### 3. Test via Chatbot

Use natural language:

```bash
curl -X POST https://d9bf4clz2f.execute-api.us-east-1.amazonaws.com/dev/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a new Node.js microservice called user-auth-api with PostgreSQL"
  }'
```

## Monitoring

### Check Agent Logs

```bash
# CodeGen Agent logs
aws logs tail /aws/ecs/dev-agentic-cluster --follow --filter-pattern codegen

# Remediation Agent logs
aws logs tail /aws/ecs/dev-agentic-cluster --follow --filter-pattern remediation

# Look for GitHub API calls
aws logs tail /aws/ecs/dev-agentic-cluster --follow --filter-pattern "GitHub"
```

### Verify Repositories

```bash
# List repositories for darrylbowler72
curl -H "Authorization: token ghp_..." \
  https://api.github.com/users/darrylbowler72/repos

# Or via web
https://github.com/darrylbowler72?tab=repositories
```

### Check ECS Service Status

```bash
aws ecs describe-services \
  --cluster dev-agentic-cluster \
  --services dev-codegen-agent dev-remediation-agent \
  --region us-east-1 \
  --query 'services[*].{Name:serviceName,Status:status,Running:runningCount}'
```

## Troubleshooting

### Issue: Agent can't access GitHub credentials

**Symptoms**: Logs show "Could not initialize GitHub client"

**Solution**:
```bash
# Verify secret exists
aws secretsmanager describe-secret \
  --secret-id dev-github-credentials \
  --region us-east-1

# Check IAM permissions
aws iam get-role-policy \
  --role-name dev-ecs-task-role \
  --policy-name dev-ecs-task-permissions
```

### Issue: Repository creation fails

**Symptoms**: 403 Forbidden or 401 Unauthorized errors

**Solutions**:
1. Verify PAT has correct scopes:
   ```bash
   # Check token via GitHub API
   curl -H "Authorization: token ghp_..." \
     https://api.github.com/user
   ```

2. Regenerate PAT if expired:
   - Go to GitHub Settings → Developer settings → Personal access tokens
   - Generate new token with required scopes
   - Update secret:
     ```bash
     aws secretsmanager put-secret-value \
       --secret-id dev-github-credentials \
       --secret-string '{"token":"<new_token>","owner":"darrylbowler72"}'
     ```

### Issue: Workflow logs not found

**Symptoms**: Remediation agent can't fetch logs

**Solutions**:
1. Verify workflow run ID is correct
2. Check repository name format (use "owner/repo" or just "repo")
3. Ensure PAT has `repo` scope

### Issue: PyGithub import errors

**Symptoms**: "ModuleNotFoundError: No module named 'github'"

**Solution**:
```bash
# Rebuild and redeploy agents
cd scripts
bash 05-deploy-agents-podman.sh
```

## Architecture

### GitHub Integration Flow

```
User Request
     ↓
API Gateway
     ↓
CodeGen/Remediation Agent
     ↓
BaseAgent._get_github_client()
     ↓
AWS Secrets Manager (dev-github-credentials)
     ↓
PyGithub Library
     ↓
GitHub API (api.github.com)
     ↓
Repository Operations (create, commit, push, fetch logs)
```

### Code Locations

| Component | File Path | Purpose |
|-----------|-----------|---------|
| Base GitHub Client | `backend/agents/common/agent_base.py:165-189` | Shared GitHub API client initialization |
| CodeGen Integration | `backend/agents/codegen/main.py:215-270` | Repository creation and code push |
| Remediation Integration | `backend/agents/remediation/main.py:185-235` | Workflow log fetching |
| Webhook Handler | `backend/agents/remediation/main.py:360-385` | GitHub Actions webhook receiver |
| Terraform Secret | `iac/terraform/main.tf:107-110` | GitHub credentials secret resource |
| IAM Policies | `iac/terraform/modules/ecs/main.tf:52-68, 123-127` | Secrets Manager access policies |

## Security Best Practices

1. **Token Rotation**: Regularly rotate the GitHub PAT (recommended: every 90 days)
2. **Minimal Scopes**: Only grant necessary scopes to the PAT
3. **Private Repositories**: Create all generated repositories as private by default
4. **Audit Logs**: Monitor GitHub audit logs for unexpected API usage
5. **Secrets Management**: Never commit tokens to code; always use AWS Secrets Manager
6. **IAM Least Privilege**: ECS tasks only have access to secrets they need

## Future Enhancements

- [ ] Add GitLab support for hybrid repository management
- [ ] Implement repository template support
- [ ] Add branch protection rules automatically
- [ ] Create pull requests instead of direct commits
- [ ] Integrate with GitHub Projects for issue tracking
- [ ] Add support for GitHub Codespaces setup
- [ ] Implement automatic dependency updates via Dependabot config

## Support

For issues or questions:
- **GitHub Issues**: https://github.com/darrylbowler72/agenticframework/issues
- **AWS Logs**: Check CloudWatch logs for detailed error messages
- **Agent Health**: Monitor ECS service health and task status

---

**Last Updated**: 2024-12-04
**Configured Account**: darrylbowler72
**AWS Region**: us-east-1
**Environment**: dev
