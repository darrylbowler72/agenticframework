"""
MCP Client for Agents

Provides a simple client interface for agents to communicate with MCP servers.
"""

import os
import uuid
import logging
from typing import Dict, Optional, Any
import httpx

logger = logging.getLogger(__name__)


class MCPClient:
    """Simple MCP client for agent-to-MCP-server communication."""

    def __init__(self, server_url: str):
        """
        Initialize MCP client.

        Args:
            server_url: Base URL of the MCP server (e.g., http://localhost:8100)
        """
        self.server_url = server_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)

    async def call(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call an MCP method.

        Args:
            method: MCP method name (e.g., "github.create_repository")
            params: Method parameters

        Returns:
            Method result dictionary

        Raises:
            Exception: If the MCP call fails
        """
        request_id = str(uuid.uuid4())

        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }

        try:
            response = await self.client.post(
                f"{self.server_url}/mcp/call",
                json=payload
            )
            response.raise_for_status()

            result = response.json()

            if "error" in result and result["error"] is not None:
                error = result["error"]
                raise Exception(f"MCP error: {error.get('message', 'Unknown error')}")

            return result.get("result", {})

        except httpx.HTTPError as e:
            logger.error(f"MCP HTTP error: {e}")
            raise Exception(f"MCP HTTP error: {str(e)}")
        except Exception as e:
            logger.error(f"MCP call failed: {e}")
            raise

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class GitHubMCPClient:
    """High-level GitHub operations via MCP."""

    def __init__(self, mcp_server_url: Optional[str] = None):
        """
        Initialize GitHub MCP client.

        Args:
            mcp_server_url: MCP server URL. If not provided, uses MCP_GITHUB_URL env var
                           or defaults to internal ECS service name.
        """
        if mcp_server_url is None:
            mcp_server_url = os.getenv(
                'MCP_GITHUB_URL',
                'http://mcp-github:8100'
            )

        self.mcp = MCPClient(mcp_server_url)
        logger.info(f"GitHub MCP client initialized with server: {mcp_server_url}")

    async def create_repository(
        self,
        name: str,
        description: str = "",
        private: bool = True,
        auto_init: bool = False
    ) -> Dict[str, Any]:
        """
        Create a GitHub repository via MCP.

        Args:
            name: Repository name
            description: Repository description
            private: Whether the repository is private
            auto_init: Whether to initialize with README

        Returns:
            Repository details dictionary
        """
        return await self.mcp.call("github.create_repository", {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init
        })

    async def create_file(
        self,
        repo_name: str,
        file_path: str,
        content: str,
        message: str,
        branch: str = "main"
    ) -> Dict[str, Any]:
        """
        Create a file in a repository via MCP.

        Args:
            repo_name: Repository name
            file_path: Path to file in repository
            content: File content
            message: Commit message
            branch: Branch name

        Returns:
            File details dictionary
        """
        return await self.mcp.call("github.create_file", {
            "repo_name": repo_name,
            "file_path": file_path,
            "content": content,
            "message": message,
            "branch": branch
        })

    async def get_workflow_run(
        self,
        repo_name: str,
        run_id: int
    ) -> Dict[str, Any]:
        """
        Get GitHub Actions workflow run details via MCP.

        Args:
            repo_name: Repository name
            run_id: Workflow run ID

        Returns:
            Workflow run details dictionary
        """
        return await self.mcp.call("github.get_workflow_run", {
            "repo_name": repo_name,
            "run_id": run_id
        })

    async def list_repositories(self, limit: int = 10) -> Dict[str, Any]:
        """
        List repositories via MCP.

        Args:
            limit: Maximum number of repositories to return

        Returns:
            Repositories list dictionary
        """
        return await self.mcp.call("github.list_repositories", {
            "limit": limit
        })

    async def get_repository(self, repo_name: str) -> Dict[str, Any]:
        """
        Get repository details via MCP.

        Args:
            repo_name: Repository name

        Returns:
            Repository details dictionary
        """
        return await self.mcp.call("github.get_repository", {
            "repo_name": repo_name
        })

    async def close(self):
        """Close the MCP client."""
        await self.mcp.close()
