"""
MCP GitHub Server

Implements Model Context Protocol server for GitHub operations.
Provides standardized GitHub API access for all agents.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from github import Github, GithubException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "service": "mcp-github", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MCP GitHub Server",
    description="Model Context Protocol server for GitHub operations",
    version="1.0.0"
)

# Global GitHub client (initialized on first request)
_github_client: Optional[Github] = None
_github_owner: Optional[str] = None

def get_github_client() -> tuple[Github, str]:
    """Get or initialize GitHub client from environment variables."""
    global _github_client, _github_owner

    if _github_client is None:
        try:
            token = os.getenv('GITHUB_TOKEN', '')
            owner = os.getenv('GITHUB_OWNER', 'darrylbowler72')
            if not token:
                raise ValueError("GITHUB_TOKEN environment variable not set")
            logger.info("Using GitHub credentials from environment variables")

            _github_client = Github(token)
            _github_owner = owner

            # Test authentication
            user = _github_client.get_user()
            logger.info(f"GitHub client initialized for user: {user.login}")

        except Exception as e:
            logger.error(f"Failed to initialize GitHub client: {e}")
            raise HTTPException(status_code=500, detail=f"GitHub initialization failed: {str(e)}")

    return _github_client, _github_owner


# Pydantic models for MCP requests/responses

class MCPRequest(BaseModel):
    """Base MCP request model."""
    jsonrpc: str = "2.0"
    id: str
    method: str
    params: Dict[str, Any]


class MCPResponse(BaseModel):
    """Base MCP response model."""
    jsonrpc: str = "2.0"
    id: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class CreateRepositoryRequest(BaseModel):
    """Create GitHub repository request."""
    name: str
    description: Optional[str] = None
    private: bool = True
    auto_init: bool = False


class CreateFileRequest(BaseModel):
    """Create file in repository request."""
    repo_name: str
    file_path: str
    content: str
    message: str
    branch: str = "main"


class GetWorkflowRunRequest(BaseModel):
    """Get workflow run request."""
    repo_name: str
    run_id: int


class ListRepositoriesRequest(BaseModel):
    """List repositories request."""
    limit: int = 10


class CreateBranchRequest(BaseModel):
    """Create branch in repository request."""
    repo_name: str
    branch_name: str
    from_branch: str = "main"


# MCP Tool Handlers

@app.post("/mcp/call")
async def mcp_call(request: MCPRequest) -> MCPResponse:
    """
    Main MCP call endpoint.
    Routes requests to appropriate GitHub operations.
    """
    try:
        method = request.method
        params = request.params

        # Route to appropriate handler
        if method == "github.create_repository":
            result = await create_repository(params)
        elif method == "github.create_file":
            result = await create_file(params)
        elif method == "github.create_branch":
            result = await create_branch(params)
        elif method == "github.get_workflow_run":
            result = await get_workflow_run(params)
        elif method == "github.list_repositories":
            result = await list_repositories(params)
        elif method == "github.get_repository":
            result = await get_repository(params)
        else:
            return MCPResponse(
                id=request.id,
                error={
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            )

        return MCPResponse(id=request.id, result=result)

    except HTTPException as e:
        logger.error(f"MCP call error: HTTP {e.status_code}: {e.detail}")
        return MCPResponse(
            id=request.id,
            error={
                "code": -32603,
                "message": f"HTTP {e.status_code}: {e.detail}"
            }
        )
    except Exception as e:
        logger.error(f"MCP call error: {type(e).__name__}: {e}")
        return MCPResponse(
            id=request.id,
            error={
                "code": -32603,
                "message": f"{type(e).__name__}: {e}"
            }
        )


async def create_repository(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a GitHub repository."""
    gh_client, owner = get_github_client()

    name = params.get('name')
    description = params.get('description', '')
    private = params.get('private', True)
    auto_init = params.get('auto_init', False)

    if not name:
        raise ValueError("Repository name is required")

    try:
        user = gh_client.get_user()
        repo = user.create_repo(
            name=name,
            description=description,
            private=private,
            auto_init=auto_init
        )

        logger.info(f"Created repository: {repo.full_name}")

        return {
            "name": repo.name,
            "full_name": repo.full_name,
            "html_url": repo.html_url,
            "clone_url": repo.clone_url,
            "default_branch": repo.default_branch
        }

    except GithubException as e:
        logger.error(f"GitHub API error creating repository: {e}")
        raise HTTPException(status_code=e.status, detail=e.data.get('message', str(e)))


async def create_file(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a file in a GitHub repository."""
    gh_client, owner = get_github_client()

    repo_name = params.get('repo_name')
    file_path = params.get('file_path')
    content = params.get('content')
    message = params.get('message', f'Add {file_path}')
    branch = params.get('branch', 'main')

    if not all([repo_name, file_path, content]):
        raise ValueError("repo_name, file_path, and content are required")

    try:
        repo = gh_client.get_user().get_repo(repo_name)
        result = repo.create_file(
            path=file_path,
            message=message,
            content=content,
            branch=branch
        )

        logger.info(f"Created file {file_path} in {repo_name}")

        return {
            "path": file_path,
            "sha": result['content'].sha,
            "html_url": result['content'].html_url
        }

    except GithubException as e:
        logger.error(f"GitHub API error creating file: {e}")
        raise HTTPException(status_code=e.status, detail=e.data.get('message', str(e)))


async def create_branch(params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a branch in a GitHub repository."""
    gh_client, owner = get_github_client()

    repo_name = params.get('repo_name')
    branch_name = params.get('branch_name')
    from_branch = params.get('from_branch', 'main')

    if not all([repo_name, branch_name]):
        raise ValueError("repo_name and branch_name are required")

    try:
        # Get repository
        if '/' in repo_name:
            repo = gh_client.get_repo(repo_name)
        else:
            repo = gh_client.get_user().get_repo(repo_name)

        # Get the source branch reference
        source_branch = repo.get_branch(from_branch)
        source_sha = source_branch.commit.sha

        # Create the new branch
        repo.create_git_ref(
            ref=f"refs/heads/{branch_name}",
            sha=source_sha
        )

        logger.info(f"Created branch {branch_name} in {repo_name} from {from_branch}")

        return {
            "branch_name": branch_name,
            "repo_name": repo.name,
            "from_branch": from_branch,
            "sha": source_sha,
            "url": f"{repo.html_url}/tree/{branch_name}"
        }

    except GithubException as e:
        logger.error(f"GitHub API error creating branch: {e}")
        raise HTTPException(status_code=e.status, detail=e.data.get('message', str(e)))


async def get_workflow_run(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get GitHub Actions workflow run details."""
    gh_client, owner = get_github_client()

    repo_name = params.get('repo_name')
    run_id = params.get('run_id')

    if not all([repo_name, run_id]):
        raise ValueError("repo_name and run_id are required")

    try:
        # Get repository
        if '/' in repo_name:
            repo = gh_client.get_repo(repo_name)
        else:
            repo = gh_client.get_user().get_repo(repo_name)

        # Get workflow run
        run = repo.get_workflow_run(run_id)

        # Get logs if available
        logs_url = None
        try:
            logs_url = run.logs_url
        except:
            pass

        # Get jobs and steps if available
        jobs_data = []
        try:
            jobs = run.jobs()
            for job in jobs:
                steps_data = []
                try:
                    for step in job.steps:
                        steps_data.append({
                            "name": step.name,
                            "status": step.status,
                            "conclusion": step.conclusion,
                            "number": step.number
                        })
                except Exception as step_error:
                    logger.warning(f"Error fetching steps for job {job.name}: {step_error}")

                jobs_data.append({
                    "id": job.id,
                    "name": job.name,
                    "status": job.status,
                    "conclusion": job.conclusion,
                    "started_at": job.started_at.isoformat() if job.started_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "steps": steps_data
                })
        except Exception as jobs_error:
            logger.warning(f"Error fetching jobs: {jobs_error}")

        return {
            "id": run.id,
            "name": run.name,
            "status": run.status,
            "conclusion": run.conclusion,
            "html_url": run.html_url,
            "logs_url": logs_url,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "updated_at": run.updated_at.isoformat() if run.updated_at else None,
            "jobs": jobs_data
        }

    except GithubException as e:
        logger.error(f"GitHub API error getting workflow run: {e}")
        raise HTTPException(status_code=e.status, detail=e.data.get('message', str(e)))


async def list_repositories(params: Dict[str, Any]) -> Dict[str, Any]:
    """List user's GitHub repositories."""
    gh_client, owner = get_github_client()

    limit = params.get('limit', 10)

    try:
        user = gh_client.get_user()
        repos = user.get_repos(sort='updated')[:limit]

        return {
            "repositories": [
                {
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "html_url": repo.html_url,
                    "private": repo.private,
                    "description": repo.description
                }
                for repo in repos
            ]
        }

    except GithubException as e:
        logger.error(f"GitHub API error listing repositories: {e}")
        raise HTTPException(status_code=e.status, detail=e.data.get('message', str(e)))


async def get_repository(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get repository details."""
    gh_client, owner = get_github_client()

    repo_name = params.get('repo_name')

    if not repo_name:
        raise ValueError("repo_name is required")

    try:
        if '/' in repo_name:
            repo = gh_client.get_repo(repo_name)
        else:
            repo = gh_client.get_user().get_repo(repo_name)

        return {
            "name": repo.name,
            "full_name": repo.full_name,
            "html_url": repo.html_url,
            "clone_url": repo.clone_url,
            "default_branch": repo.default_branch,
            "private": repo.private,
            "description": repo.description
        }

    except GithubException as e:
        logger.error(f"GitHub API error getting repository: {e}")
        raise HTTPException(status_code=e.status, detail=e.data.get('message', str(e)))


# Health check endpoint

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    # Basic health check - just verify service is running
    # GitHub connection will be tested on actual API calls
    return {
        "status": "healthy",
        "service": "mcp-github-server",
        "version": "1.0.5"
    }


# MCP Server Information

@app.get("/mcp/info")
async def mcp_info():
    """Get MCP server information and available tools."""
    return {
        "name": "github",
        "version": "1.0.0",
        "tools": [
            {
                "name": "github.create_repository",
                "description": "Create a new GitHub repository",
                "parameters": {
                    "name": {"type": "string", "required": True},
                    "description": {"type": "string", "required": False},
                    "private": {"type": "boolean", "required": False},
                    "auto_init": {"type": "boolean", "required": False}
                }
            },
            {
                "name": "github.create_file",
                "description": "Create a file in a repository",
                "parameters": {
                    "repo_name": {"type": "string", "required": True},
                    "file_path": {"type": "string", "required": True},
                    "content": {"type": "string", "required": True},
                    "message": {"type": "string", "required": False},
                    "branch": {"type": "string", "required": False}
                }
            },
            {
                "name": "github.get_workflow_run",
                "description": "Get GitHub Actions workflow run details",
                "parameters": {
                    "repo_name": {"type": "string", "required": True},
                    "run_id": {"type": "integer", "required": True}
                }
            },
            {
                "name": "github.list_repositories",
                "description": "List user's repositories",
                "parameters": {
                    "limit": {"type": "integer", "required": False}
                }
            },
            {
                "name": "github.get_repository",
                "description": "Get repository details",
                "parameters": {
                    "repo_name": {"type": "string", "required": True}
                }
            },
            {
                "name": "github.create_branch",
                "description": "Create a new branch in a repository",
                "parameters": {
                    "repo_name": {"type": "string", "required": True},
                    "branch_name": {"type": "string", "required": True},
                    "from_branch": {"type": "string", "required": False}
                }
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
