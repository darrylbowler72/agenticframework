"""
DevOps at Your Service - Chatbot Agent

A conversational interface for the DevOps Agentic Framework.
Provides natural language interaction with all framework capabilities.
"""

import os
import uuid
import json
from datetime import datetime
from typing import List, Dict, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import httpx

# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.agent_base import BaseAgent
from common.version import __version__
from common.graphs import build_chatbot_graph

app = FastAPI(
    title="DevOps at Your Service - Chatbot",
    description="Conversational interface for DevOps Agentic Framework",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/dev/static", StaticFiles(directory=static_dir), name="static")


class ChatMessage(BaseModel):
    """Chat message model."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    """Chat request model."""
    session_id: str
    message: str


class ChatResponse(BaseModel):
    """Chat response model."""
    session_id: str
    message: str
    agent_action: Optional[str] = None
    action_result: Optional[Dict] = None


class ChatbotAgent(BaseAgent):
    """Chatbot agent for conversational DevOps interface."""

    def __init__(self):
        super().__init__(agent_name="chatbot")
        self.graph = build_chatbot_graph(self)
        self.environment = os.getenv('ENVIRONMENT', 'dev')
        self.sessions_table = self.dynamodb.Table(f'{self.environment}-chatbot-sessions')

        # Agent endpoints via container DNS names (configurable via env vars)
        self.agent_endpoints = {
            'planner': os.getenv('PLANNER_URL', 'http://planner-agent:8000') + '/workflows',
            'codegen': os.getenv('CODEGEN_URL', 'http://codegen-agent:8001') + '/generate',
            'remediation': os.getenv('REMEDIATION_URL', 'http://remediation-agent:8002') + '/remediate',
            'migration': os.getenv('MIGRATION_URL', 'http://migration-agent:8004') + '/migrate'
        }

    async def process_task(self, task_data: Dict) -> Dict:
        """Process a task (required by BaseAgent, but chatbot uses process_message instead)."""
        return {"status": "not_implemented", "message": "Chatbot uses process_message method"}

    async def get_session(self, session_id: str) -> Dict:
        """Retrieve chat session from DynamoDB."""
        try:
            response = self.sessions_table.get_item(Key={'session_id': session_id})
            if 'Item' in response:
                return response['Item']
            return {
                'session_id': session_id,
                'messages': [],
                'created_at': datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error retrieving session: {e}")
            return {
                'session_id': session_id,
                'messages': [],
                'created_at': datetime.utcnow().isoformat()
            }

    async def save_session(self, session_id: str, messages: List[Dict]):
        """Save chat session to DynamoDB."""
        try:
            self.sessions_table.put_item(
                Item={
                    'session_id': session_id,
                    'messages': messages,
                    'updated_at': datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            self.logger.error(f"Error saving session: {e}")

    async def create_github_repository(
        self,
        repo_name: str,
        description: str = "",
        private: bool = False,
        auto_init: bool = True
    ) -> Dict:
        """
        Create a GitHub repository.

        Args:
            repo_name: Name of the repository
            description: Repository description
            private: Whether the repository should be private
            auto_init: Initialize with README

        Returns:
            Repository creation result
        """
        try:
            client, owner = await self._get_github_client()
            user = client.get_user()

            repo = user.create_repo(
                name=repo_name,
                description=description,
                private=private,
                auto_init=auto_init
            )

            self.logger.info(f"Created repository: {repo.full_name}")

            return {
                "success": True,
                "repository": {
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "url": repo.html_url,
                    "description": repo.description,
                    "private": repo.private,
                    "default_branch": repo.default_branch
                }
            }

        except Exception as e:
            self.logger.error(f"Error creating repository: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def delete_github_repository(self, repo_name: str) -> Dict:
        """
        Delete a GitHub repository.

        Args:
            repo_name: Name of the repository to delete

        Returns:
            Deletion result
        """
        try:
            client, owner = await self._get_github_client()
            repo = client.get_repo(f"{owner}/{repo_name}")
            repo.delete()

            self.logger.info(f"Deleted repository: {owner}/{repo_name}")

            return {
                "success": True,
                "repository": {
                    "name": repo_name,
                    "full_name": f"{owner}/{repo_name}"
                }
            }

        except Exception as e:
            self.logger.error(f"Error deleting repository: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def list_github_repositories(self, max_repos: int = 30) -> Dict:
        """
        List GitHub repositories for the authenticated user.

        Args:
            max_repos: Maximum number of repositories to return

        Returns:
            List of repositories
        """
        try:
            client, owner = await self._get_github_client()
            user = client.get_user()
            repos = user.get_repos()

            repository_list = []
            count = 0
            for repo in repos:
                if count >= max_repos:
                    break

                repository_list.append({
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "url": repo.html_url,
                    "description": repo.description,
                    "private": repo.private,
                    "language": repo.language,
                    "stars": repo.stargazers_count,
                    "forks": repo.forks_count,
                    "updated_at": repo.updated_at.isoformat() if repo.updated_at else None
                })
                count += 1

            self.logger.info(f"Listed {len(repository_list)} repositories for {owner}")

            return {
                "success": True,
                "owner": owner,
                "count": len(repository_list),
                "repositories": repository_list
            }

        except Exception as e:
            self.logger.error(f"Error listing repositories: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def call_mcp_github(self, method: str, params: Dict) -> Dict:
        """
        Call MCP GitHub server.

        Args:
            method: MCP method name (e.g., 'github.create_branch')
            params: Method parameters

        Returns:
            MCP response
        """
        mcp_url = os.getenv('MCP_GITHUB_URL', 'http://dev-mcp-github.dev-agentic.local:8100')

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{mcp_url}/mcp/call",
                    json={
                        "jsonrpc": "2.0",
                        "id": str(uuid.uuid4()),
                        "method": method,
                        "params": params
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("error"):
                        self.logger.error(f"MCP error: {result['error']}")
                        return {"success": False, "error": result['error']}
                    return {"success": True, "result": result.get("result", {})}
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

        except Exception as e:
            self.logger.error(f"Error calling MCP GitHub: {e}")
            return {"success": False, "error": str(e)}

    async def create_github_branch(
        self,
        repo_name: str,
        branch_name: str,
        from_branch: str = "main"
    ) -> Dict:
        """
        Create a branch in a GitHub repository via MCP server.

        Args:
            repo_name: Repository name
            branch_name: New branch name
            from_branch: Branch to create from

        Returns:
            Branch creation result
        """
        try:
            result = await self.call_mcp_github(
                "github.create_branch",
                {
                    "repo_name": repo_name,
                    "branch_name": branch_name,
                    "from_branch": from_branch
                }
            )

            if result.get("success"):
                branch_info = result.get("result", {})
                self.logger.info(f"Created branch {branch_name} in {repo_name}")
                return {
                    "success": True,
                    "branch": branch_info
                }
            else:
                return result

        except Exception as e:
            self.logger.error(f"Error creating branch: {e}")
            return {"success": False, "error": str(e)}

    async def analyze_intent(self, message: str, conversation_history: List[Dict]) -> Dict:
        """Use Claude to analyze user intent and determine action."""

        # Build context from conversation history
        context = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in conversation_history[-5:]  # Last 5 messages
        ])

        system_prompt = """You are "DevOps at Your Service", an AI assistant for a DevOps automation framework.

You can help users with:
1. **Create Workflows** - Plan and decompose DevOps tasks into executable workflows
2. **Generate Code** - Create microservices, infrastructure code, CI/CD pipelines
3. **Remediate Issues** - Analyze and fix CI/CD pipeline failures
4. **GitHub Operations** - Create/delete/list repositories, create branches, manage gitflow branching, set up new projects with framework templates (owner: darrylbowler72)
5. **Jenkins Operations** - List Jenkins jobs, get job details, test Jenkins connection, create jobs
6. **Pipeline Migration** - Convert Jenkins pipelines to GitHub Actions workflows
7. **General Help** - Answer questions about DevOps, the framework, or provide guidance

Analyze the user's message and respond with JSON in this format:
{
  "intent": "workflow|codegen|remediation|github|jenkins|migration|help|general",
  "action_needed": true/false,
  "parameters": {
    // Extract relevant parameters based on intent
  },
  "response": "Your conversational response to the user"
}

For action_needed=true, extract parameters:
- workflow: {"description": "...", "environment": "dev/staging/prod", "template": "default", "requested_by": "user", "parameters": {}}
- codegen: {"service_name": "...", "language": "...", "database": "...", "api_type": "..."}
- remediation: {"pipeline_id": "...", "project_id": "..."}
- github: {"operation": "create_repo|delete_repo|list_repos|create_branch|create_gitflow|setup_project", "repo_name": "...", "description": "...", "private": true/false, "max_repos": 30, "branch_name": "...", "from_branch": "main", "template_framework": "python|fastapi|flask|django|nodejs|express|react|angular|vue|nextjs|none"}
- jenkins: {"operation": "list_jobs|get_job|test_connection", "job_name": "...", "jenkins_url": "http://dev-agents-alb-1535480028.us-east-1.elb.amazonaws.com/jenkins", "username": "admin", "password": "admin"}
- migration: {"job_name": "...", "github_repo": "...", "jenkins_migration": true} for Jenkins job migration OR {"jenkinsfile_content": "...", "project_name": "...", "repository_url": "..."} for generic Jenkinsfile migration

GitHub operation notes:
- "create_repo": Create a new repository
- "create_branch": Create a single branch in an existing repo
- "create_gitflow": Create standard gitflow branches (develop, release/1.0.0, hotfix/initial) - auto-creates repo if needed
- "setup_project": Create repo + gitflow branches + push framework template files (Angular, React, Next.js, etc.). Use this when the user wants to bootstrap/scaffold a new project.

Jenkins operation notes:
- "list_jobs": List all Jenkins jobs (ALWAYS set action_needed=true when user asks to: "list", "show", "get", "display" Jenkins jobs or pipelines)
- "get_job": Get details about a specific Jenkins job (requires job_name)
- "test_connection": Test connection to Jenkins server

**IMPORTANT**: When the user asks to list/show/get Jenkins jobs or pipelines, you MUST:
1. Set "action_needed": true
2. Set "intent": "jenkins"
3. Set "parameters": {"operation": "list_jobs"}

Migration operation notes:
- For Jenkins job migration (e.g., "migrate jenkins job X to github"), extract: {"job_name": "X", "github_repo": "owner/repo-name", "jenkins_migration": true}
- The system will automatically fetch the Jenkinsfile from Jenkins and convert it to GitHub Actions

Be friendly, helpful, and conversational. If you need more information, ask the user."""

        user_prompt = f"""Conversation history:
{context}

New user message: {message}

Analyze the intent and provide your response in JSON format."""

        try:
            response = await self.call_claude(
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.7
            )

            # Parse JSON response
            return json.loads(response)
        except json.JSONDecodeError:
            # If Claude doesn't return valid JSON, wrap the response
            return {
                "intent": "general",
                "action_needed": False,
                "response": response if 'response' in locals() else "I received an unexpected response format."
            }
        except Exception as e:
            self.logger.error(f"Error analyzing intent: {e}")
            return {
                "intent": "error",
                "action_needed": False,
                "response": "I apologize, but I encountered an error processing your request. Could you please try rephrasing?"
            }

    async def execute_action(self, intent: str, parameters: Dict) -> Optional[Dict]:
        """Execute action with the appropriate agent."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if intent == "workflow":
                    response = await client.post(
                        self.agent_endpoints['planner'],
                        json={
                            "description": parameters.get("description", ""),
                            "environment": parameters.get("environment", "dev"),
                            "project_id": parameters.get("project_id", "default"),
                            "template": parameters.get("template", "default"),
                            "requested_by": parameters.get("requested_by", "chatbot-user"),
                            "parameters": parameters.get("parameters", {})
                        }
                    )
                    return response.json()

                elif intent == "codegen":
                    response = await client.post(
                        self.agent_endpoints['codegen'],
                        json={
                            "service_name": parameters.get("service_name", ""),
                            "language": parameters.get("language", "python"),
                            "database": parameters.get("database", "postgresql"),
                            "api_type": parameters.get("api_type", "rest"),
                            "environment": parameters.get("environment", "dev")
                        }
                    )
                    return response.json()

                elif intent == "remediation":
                    response = await client.post(
                        self.agent_endpoints['remediation'],
                        params={
                            "pipeline_id": parameters.get("pipeline_id", 0),
                            "project_id": parameters.get("project_id", 0)
                        }
                    )
                    return response.json()

                elif intent == "jenkins":
                    operation = parameters.get("operation")
                    jenkins_url = parameters.get("jenkins_url", "http://dev-agents-alb-1535480028.us-east-1.elb.amazonaws.com/jenkins")
                    username = parameters.get("username", "admin")
                    password = parameters.get("password", "admin")

                    if operation == "list_jobs":
                        response = await client.get(
                            f"{self.agent_endpoints['migration']}/jenkins/jobs",
                            params={
                                "jenkins_url": jenkins_url,
                                "username": username,
                                "password": password
                            }
                        )
                        return response.json()
                    elif operation == "get_job":
                        job_name = parameters.get("job_name", "")
                        response = await client.get(
                            f"{self.agent_endpoints['migration']}/jenkins/jobs/{job_name}",
                            params={
                                "jenkins_url": jenkins_url,
                                "username": username,
                                "password": password
                            }
                        )
                        return response.json()
                    elif operation == "test_connection":
                        response = await client.get(
                            f"{self.agent_endpoints['migration']}/jenkins/test",
                            params={
                                "jenkins_url": jenkins_url,
                                "username": username,
                                "password": password
                            }
                        )
                        return response.json()

                elif intent == "migration":
                    # Check if this is a Jenkins job migration
                    if parameters.get("job_name") or parameters.get("jenkins_migration"):
                        # Jenkins-to-GitHub migration
                        jenkins_url = parameters.get("jenkins_url", "http://dev-agents-alb-1535480028.us-east-1.elb.amazonaws.com/jenkins")
                        username = parameters.get("username", "admin")
                        password = parameters.get("password", "admin")

                        # Get GitHub token from environment or parameters
                        github_token = parameters.get("github_token", os.getenv("GITHUB_TOKEN", ""))

                        response = await client.post(
                            f"{self.agent_endpoints['migration']}/jenkins/migrate-job",
                            json={
                                "job_name": parameters.get("job_name", ""),
                                "jenkins_url": jenkins_url,
                                "username": username,
                                "password": password,
                                "github_repo": parameters.get("github_repo", ""),
                                "github_token": github_token
                            }
                        )
                        return response.json()
                    else:
                        # Generic Jenkinsfile migration
                        response = await client.post(
                            self.agent_endpoints['migration'],
                            json={
                                "jenkinsfile_content": parameters.get("jenkinsfile_content", ""),
                                "project_name": parameters.get("project_name", "project"),
                                "repository_url": parameters.get("repository_url", "")
                            }
                        )
                        return response.json()

                elif intent == "github":
                    operation = parameters.get("operation")
                    if operation == "create_repo":
                        return await self.create_github_repository(
                            repo_name=parameters.get("repo_name", ""),
                            description=parameters.get("description", ""),
                            private=parameters.get("private", False),
                            auto_init=parameters.get("auto_init", True)
                        )
                    elif operation == "delete_repo":
                        return await self.delete_github_repository(
                            repo_name=parameters.get("repo_name", "")
                        )
                    elif operation == "list_repos":
                        return await self.list_github_repositories(
                            max_repos=parameters.get("max_repos", 30)
                        )
                    elif operation == "create_branch":
                        return await self.create_github_branch(
                            repo_name=parameters.get("repo_name", ""),
                            branch_name=parameters.get("branch_name", ""),
                            from_branch=parameters.get("from_branch", "main")
                        )
                    elif operation == "create_gitflow":
                        # Create gitflow branches: develop, release, hotfix
                        repo_name = parameters.get("repo_name", "")
                        results = []

                        # Auto-create the repo if it doesn't exist
                        try:
                            gh_client, owner = await self._get_github_client()
                            gh_client.get_repo(f"{owner}/{repo_name}")
                            self.logger.info(f"Repository {repo_name} already exists")
                        except Exception:
                            self.logger.info(f"Repository {repo_name} not found, creating it")
                            create_result = await self.create_github_repository(
                                repo_name=repo_name,
                                description=parameters.get("description", f"{repo_name} with gitflow branching"),
                                auto_init=True
                            )
                            if not create_result.get("success"):
                                return create_result
                            # Wait for GitHub to initialize the default branch
                            await asyncio.sleep(3)

                        for branch in ["develop", "release/1.0.0", "hotfix/initial"]:
                            result = await self.create_github_branch(
                                repo_name=repo_name,
                                branch_name=branch,
                                from_branch="main"
                            )
                            results.append({"branch": branch, "result": result})
                        return {"success": True, "branches": results}
                    elif operation == "setup_project":
                        return await self._setup_project(parameters)
                    else:
                        return {"error": f"Unknown GitHub operation: {operation}"}

                else:
                    return {"info": f"Intent '{intent}' does not require backend agent execution"}

        except Exception as e:
            self.logger.error(f"Error executing action: {e}")
            return {"error": str(e)}

    async def _setup_project(self, parameters: Dict) -> Dict:
        """Set up a new project: create repo, gitflow branches, and push template files."""
        repo_name = parameters.get("repo_name", "")
        description = parameters.get("description", f"{repo_name} project")
        framework = parameters.get("template_framework", "none").lower()
        private = parameters.get("private", False)

        setup_result = {
            "operation": "setup_project",
            "repo_name": repo_name,
            "framework": framework,
            "steps": {}
        }

        # Step 1: Create the repository
        self.logger.info(f"setup_project: creating repo {repo_name}")
        create_result = await self.create_github_repository(
            repo_name=repo_name,
            description=description,
            private=private,
            auto_init=True
        )
        setup_result["steps"]["create_repo"] = create_result
        if not create_result.get("success"):
            setup_result["success"] = False
            setup_result["error"] = f"Failed to create repository: {create_result.get('error')}"
            return setup_result

        repo_url = create_result.get("repository", {}).get("url", "")

        # Step 2: Wait for GitHub to initialize the default branch
        await asyncio.sleep(3)

        # Step 3: Create gitflow branches
        self.logger.info(f"setup_project: creating gitflow branches for {repo_name}")
        branches_created = []
        for branch in ["develop", "release/1.0.0"]:
            result = await self.create_github_branch(
                repo_name=repo_name,
                branch_name=branch,
                from_branch="main"
            )
            branches_created.append({
                "branch": branch,
                "success": result.get("success", False)
            })
        setup_result["steps"]["branches"] = branches_created

        # Step 4: Generate template files for the framework
        if framework and framework != "none":
            self.logger.info(f"setup_project: generating {framework} template for {repo_name}")
            template_files = await self._generate_project_template(framework, repo_name)

            # Brief pause to let branch refs propagate on GitHub
            await asyncio.sleep(2)

            # Step 5: Push template files to the develop branch (sequential with retry)
            files_pushed = []
            files_failed = []
            for file_path, content in template_files.items():
                # Ensure content is always a string (Claude may return dicts for JSON files)
                if not isinstance(content, str):
                    content = json.dumps(content, indent=2)
                last_error = None
                for attempt in range(3):
                    try:
                        push_result = await self.call_mcp_github(
                            "github.update_file",
                            {
                                "repo_name": repo_name,
                                "file_path": file_path,
                                "content": content,
                                "message": f"Add {file_path} - {framework} project bootstrap",
                                "branch": "develop"
                            }
                        )
                        if push_result.get("success"):
                            files_pushed.append(file_path)
                            last_error = None
                            break
                        else:
                            last_error = push_result.get("error")
                            self.logger.warning(f"File push attempt {attempt + 1} failed for {file_path}: {last_error}")
                            await asyncio.sleep(2)
                    except Exception as e:
                        last_error = str(e)
                        await asyncio.sleep(2)
                if last_error:
                    files_failed.append({"path": file_path, "error": last_error})
                # Small delay between files to avoid GitHub API rate issues
                await asyncio.sleep(0.5)

            setup_result["steps"]["files"] = {
                "pushed": files_pushed,
                "failed": files_failed,
                "total": len(template_files)
            }

        setup_result["success"] = True
        setup_result["repo_url"] = repo_url
        return setup_result

    def _build_gitflow_workflow(self, framework: str, project_name: str) -> str:
        """Build a framework-aware Gitflow CI/CD workflow YAML."""
        is_python = framework.lower() in ("python", "fastapi", "flask", "django")
        is_node = framework.lower() in ("nodejs", "node", "express", "react", "angular", "vue", "next", "nextjs")

        if is_python:
            install_step = "run: pip install -r requirements.txt"
            test_step = "run: python -m pytest --tb=short || echo 'No tests yet'"
            build_steps = "      - name: Lint\n        run: python -m py_compile $(find . -name '*.py' | head -20) && echo 'Syntax OK'"
        else:
            install_step = "run: npm install"
            test_step = "run: npm test"
            build_steps = "      - name: Install dependencies\n        run: npm install\n      - name: Build\n        run: npm run build --if-present"

        return f"""name: Gitflow CI/CD

on:
  push:
    branches:
      - develop
      - 'release/**'
      - 'hotfix/**'
  pull_request:
    branches:
      - develop
      - main

jobs:
  test:
    name: Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install dependencies
        {install_step}
      - name: Run tests
        {test_step}

  build:
    name: Build
    runs-on: ubuntu-latest
    needs: test
    if: github.event_name == 'push'
    steps:
      - uses: actions/checkout@v3
{build_steps}

  deploy-dev:
    name: Deploy to Dev
    runs-on: ubuntu-latest
    needs: build
    if: github.ref == 'refs/heads/develop'
    steps:
      - name: Deploy
        run: echo "Deploying {project_name} to development - commit ${{{{ github.sha }}}}"

  deploy-staging:
    name: Deploy to Staging
    runs-on: ubuntu-latest
    needs: build
    if: startsWith(github.ref, 'refs/heads/release/')
    steps:
      - name: Deploy
        run: echo "Deploying {project_name} to staging - release ${{{{ github.ref_name }}}}"
"""

    async def _generate_project_template(self, framework: str, project_name: str) -> Dict[str, str]:
        """Generate boilerplate project files for a given framework using Claude.

        Uses two separate LLM calls:
        1. App code files (returned as JSON to allow structured parsing)
        2. GitHub Actions workflow (returned as raw YAML to avoid JSON escaping issues)
        Falls back to hardcoded templates if either LLM call fails.
        """
        # ── Call 1: Generate app code files ──────────────────────────────────
        is_python = framework.lower() in ("python", "fastapi", "flask", "django")
        is_node = framework.lower() in ("nodejs", "node", "express", "react", "angular", "vue", "nextjs")

        if is_python:
            framework_hint = (
                "Python/FastAPI: main.py (FastAPI app with /, /health routes), "
                "requirements.txt (fastapi, uvicorn), .gitignore"
            )
        elif framework.lower() in ("react",):
            framework_hint = (
                "React/TypeScript: src/App.tsx, src/index.tsx, public/index.html, "
                "package.json (test script: \"echo 'No tests yet' && exit 0\"), tsconfig.json, .gitignore"
            )
        elif framework.lower() in ("angular",):
            framework_hint = (
                "Angular: src/main.ts, src/app/app.component.ts, src/app/app.module.ts, "
                "src/index.html, package.json, angular.json, tsconfig.json, .gitignore"
            )
        else:
            framework_hint = (
                f"Node.js/Express: src/index.js (Express app with /, /health routes), "
                f"package.json (express dep, start script, test: \"echo 'No tests yet' && exit 0\"), .gitignore"
            )

        code_prompt = f"""Generate boilerplate source files for a new {framework} project named "{project_name}".

Files to generate: {framework_hint}

Rules:
- Return ONLY a valid JSON object: keys=file paths, values=file contents as strings
- Escape ALL special characters in values (backslashes, quotes, newlines as \\n)
- Do NOT include node_modules, lock files, binary files, or .github/workflows files
- Keep code minimal but functional and runnable

Return ONLY the JSON object. No markdown. No explanation."""

        files = {}
        try:
            response = await self.call_claude(
                prompt=code_prompt,
                system="You are a code generator. Output ONLY a valid JSON object. No markdown fences. No extra text.",
                temperature=0.2
            )
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned[cleaned.index("\n") + 1:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            files = json.loads(cleaned)
            # Strip any leading project-name prefix Claude may add to paths
            stripped = {}
            for path, content in files.items():
                if path.startswith(f"{project_name}/"):
                    path = path[len(project_name) + 1:]
                stripped[path] = content
            files = stripped

            # Ensure package.json test script exits 0
            if "package.json" in files:
                try:
                    pkg = json.loads(files["package.json"])
                    test_script = pkg.get("scripts", {}).get("test", "")
                    if "exit 1" in test_script or test_script.startswith("echo \"Error"):
                        pkg["scripts"]["test"] = "echo 'No tests yet' && exit 0"
                        files["package.json"] = json.dumps(pkg, indent=2)
                except (json.JSONDecodeError, KeyError):
                    pass

            self.logger.info(f"LLM generated {len(files)} app files for {framework}/{project_name}")

        except (json.JSONDecodeError, ValueError) as e:
            self.logger.warning(f"LLM code generation failed ({e}), using hardcoded fallback")
            if is_python:
                files = {
                    "main.py": f'from fastapi import FastAPI\n\napp = FastAPI(title="{project_name}")\n\n\n@app.get("/")\ndef root():\n    return {{"service": "{project_name}", "status": "running"}}\n\n\n@app.get("/health")\ndef health():\n    return {{"status": "healthy"}}\n',
                    "requirements.txt": "fastapi>=0.104.0\nuvicorn[standard]>=0.24.0\n",
                    ".gitignore": "__pycache__/\n*.pyc\n.env\nvenv/\n.venv/\ndist/\n",
                }
            elif framework.lower() in ("react",):
                files = {
                    "src/App.tsx": f'import React from \'react\';\nexport default function App() {{\n  return <div><h1>{project_name}</h1></div>;\n}}\n',
                    "src/index.tsx": 'import React from \'react\';\nimport ReactDOM from \'react-dom/client\';\nimport App from \'./App\';\nReactDOM.createRoot(document.getElementById(\'root\')!).render(<React.StrictMode><App /></React.StrictMode>);\n',
                    "package.json": json.dumps({"name": project_name, "version": "0.1.0", "private": True, "dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0", "react-scripts": "5.0.1"}, "scripts": {"start": "react-scripts start", "build": "react-scripts build", "test": "echo 'No tests yet' && exit 0"}}, indent=2),
                    ".gitignore": "node_modules/\ndist/\nbuild/\n.env\n",
                }
            elif is_node:
                files = {
                    "src/index.js": f'const express = require(\'express\');\nconst app = express();\nconst PORT = process.env.PORT || 3000;\n\napp.use(express.json());\n\napp.get(\'/\', (req, res) => res.json({{ service: \'{project_name}\', status: \'running\' }}));\napp.get(\'/health\', (req, res) => res.json({{ status: \'healthy\' }}));\n\napp.listen(PORT, () => console.log(`Server on port ${{PORT}}`));\n',
                    "package.json": json.dumps({"name": project_name, "version": "1.0.0", "main": "src/index.js", "scripts": {"start": "node src/index.js", "test": "echo 'No tests yet' && exit 0"}, "dependencies": {"express": "^4.18.2"}}, indent=2),
                    ".gitignore": "node_modules/\n.env\ndist/\n",
                }
            else:
                files = {
                    "README.md": f"# {project_name}\n\nA {framework} project.\n",
                    ".gitignore": "node_modules/\ndist/\n.env\n__pycache__/\n",
                }

        # ── Call 2: Generate GitHub Actions workflow (raw YAML) ───────────────
        if is_python:
            install_cmd = "pip install -r requirements.txt"
            test_cmd = "python -m pytest --tb=short || echo 'No tests yet'"
            build_cmd = "python -m py_compile $(find . -name '*.py' | head -20) && echo 'Build OK'"
            language_hint = "Python (pip/pytest)"
        else:
            install_cmd = "npm install"
            test_cmd = "npm test"
            build_cmd = "npm run build --if-present"
            language_hint = "Node.js (npm)"

        workflow_prompt = f"""Generate a GitHub Actions Gitflow CI/CD workflow YAML for a {framework} project named "{project_name}".

Requirements:
- Trigger on push to: develop, release/**, hotfix/**
- Trigger on pull_request to: develop, main
- Language: {language_hint}
- Jobs (in order):
  1. test: checkout, install ({install_cmd}), run tests ({test_cmd})
  2. build: needs test, only on push events, checkout, install, build ({build_cmd})
  3. deploy-dev: needs build, only when github.ref == refs/heads/develop, echo deploy message
  4. deploy-staging: needs build, only when ref starts with refs/heads/release/, echo deploy message

Return ONLY the raw YAML. No markdown fences. No explanation."""

        workflow_yaml = None
        try:
            workflow_yaml = await self.call_claude(
                prompt=workflow_prompt,
                system="You are a DevOps engineer. Output ONLY valid GitHub Actions YAML. No markdown fences. No extra text.",
                temperature=0.1
            )
            workflow_yaml = workflow_yaml.strip()
            # Strip markdown fences if present
            if workflow_yaml.startswith("```"):
                workflow_yaml = workflow_yaml[workflow_yaml.index("\n") + 1:]
            if workflow_yaml.endswith("```"):
                workflow_yaml = workflow_yaml[:-3]
            workflow_yaml = workflow_yaml.strip()
            self.logger.info(f"LLM generated GitHub Actions workflow for {framework}/{project_name}")
        except Exception as e:
            self.logger.warning(f"LLM workflow generation failed ({e}), using hardcoded fallback")

        # Fall back to programmatic workflow if LLM failed
        if not workflow_yaml:
            workflow_yaml = self._build_gitflow_workflow(framework, project_name)

        files[".github/workflows/ci.yml"] = workflow_yaml
        return files

    def _format_action_response(self, response: str, intent: str, action_result: Dict) -> str:
        """Format action results into the response string for the user."""
        if 'error' in action_result:
            response += f"\n\nI encountered an error: {action_result['error']}"
        elif intent == 'workflow':
            response += f"\n\n Workflow created! ID: {action_result.get('workflow_id', 'N/A')}"
        elif intent == 'codegen':
            response += f"\n\n Service generated! {action_result.get('files_generated', 0)} files created."
        elif intent == 'remediation':
            response += f"\n\n Remediation initiated!"
        elif intent == 'migration':
            if action_result.get('success'):
                report = action_result.get('migration_report', {})
                response += f"\n\n Pipeline migrated successfully!"
                response += f"\n- Pipeline type: {report.get('pipeline_type')}"
                response += f"\n- Stages converted: {report.get('stages_converted')}"
                response += f"\n- Environment variables: {report.get('environment_variables')}"
                if action_result.get('warnings'):
                    response += f"\n\nWarnings:"
                    for warning in action_result['warnings']:
                        response += f"\n- {warning}"
        elif intent == 'github':
            if action_result.get('success'):
                operation = getattr(self, '_last_operation', '')
                if 'repository' in action_result:
                    repo = action_result['repository']
                    if 'url' in repo:
                        response += f"\n\n Repository operation successful!"
                        response += f"\n- Name: {repo.get('full_name', repo.get('name', 'N/A'))}"
                        response += f"\n- URL: {repo.get('url', 'N/A')}"
                elif 'repositories' in action_result:
                    count = action_result.get('count', 0)
                    owner = action_result.get('owner', 'N/A')
                    repos = action_result.get('repositories', [])
                    response += f"\n\n Found {count} repositories for {owner}:"
                    for repo in repos[:10]:
                        response += f"\n- {repo.get('name')} ({repo.get('language', 'N/A')}) - {repo.get('description', 'No description')}"
                    if count > 10:
                        response += f"\n... and {count - 10} more repositories"
                elif action_result.get('operation') == 'setup_project':
                    steps = action_result.get('steps', {})
                    framework = action_result.get('framework', 'none')
                    repo_url = action_result.get('repo_url', '')
                    response += f"\n\n Project setup complete!"
                    response += f"\n- Repository: {repo_url}"
                    # Branches
                    branches = steps.get('branches', [])
                    created_branches = [b['branch'] for b in branches if b.get('success')]
                    if created_branches:
                        response += f"\n- Branches: main, {', '.join(created_branches)}"
                    # Files
                    files_info = steps.get('files', {})
                    if files_info:
                        pushed = files_info.get('pushed', [])
                        failed = files_info.get('failed', [])
                        response += f"\n- Framework: {framework}"
                        response += f"\n- Files pushed to develop: {len(pushed)}"
                        if failed:
                            response += f"\n- Files failed: {len(failed)}"
                elif 'branches' in action_result:
                    branches = action_result.get('branches', [])
                    response += f"\n\n Gitflow branches created!"
                    for branch_result in branches:
                        if branch_result.get('result', {}).get('success'):
                            response += f"\n- {branch_result['branch']}"
                        else:
                            response += f"\n- {branch_result['branch']}: {branch_result.get('result', {}).get('error', 'Unknown error')}"
        elif intent == 'jenkins':
            if action_result.get('success'):
                if 'jobs' in action_result:
                    jobs = action_result.get('jobs', [])
                    count = action_result.get('jobs_count', 0)
                    jenkins_url = action_result.get('jenkins_url', 'N/A')
                    response += f"\n\n Found {count} Jenkins jobs on {jenkins_url}:"
                    for job in jobs[:15]:
                        color = job.get('color', 'notbuilt')
                        status_icon = "+" if color in ['blue', 'success'] else "-" if color in ['red', 'failed'] else "~" if color in ['yellow', 'unstable'] else "o"
                        response += f"\n[{status_icon}] {job.get('name')}"
                    if count > 15:
                        response += f"\n... and {count - 15} more jobs"
                elif 'version' in action_result:
                    response += f"\n\n Jenkins connection successful!"
                    response += f"\n- URL: {action_result.get('url', 'N/A')}"
                    response += f"\n- Version: {action_result.get('version', 'N/A')}"
        return response

    async def process_message(self, session_id: str, user_message: str) -> ChatResponse:
        """
        Process user message and generate response.

        Uses LangGraph to orchestrate: analyze_intent -> [execute_action] -> compose_response
        """

        # Get session history
        session = await self.get_session(session_id)
        messages = session.get('messages', [])

        # Add user message
        messages.append({
            'role': 'user',
            'content': user_message,
            'timestamp': datetime.utcnow().isoformat()
        })

        # Run the LangGraph chatbot workflow
        result = await self.graph.ainvoke({
            "session_id": session_id,
            "user_message": user_message,
            "conversation_history": messages,
        })

        assistant_message = result.get('final_response',
            "I'm here to help with your DevOps tasks! What would you like to do?")

        # Add assistant message
        messages.append({
            'role': 'assistant',
            'content': assistant_message,
            'timestamp': datetime.utcnow().isoformat()
        })

        # Save session
        await self.save_session(session_id, messages)

        return ChatResponse(
            session_id=session_id,
            message=assistant_message,
            agent_action=result.get('intent') if result.get('action_needed') else None,
            action_result=result.get('action_result')
        )


# Initialize chatbot agent
chatbot_agent = ChatbotAgent()


@app.get("/", response_class=HTMLResponse)
async def get_chat_interface():
    """Serve the chat interface."""
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(html_path):
        with open(html_path, 'r') as f:
            return HTMLResponse(content=f.read())

    # Fallback minimal HTML if template doesn't exist
    return HTMLResponse(content="""
    <html>
        <head><title>DevOps at Your Service</title></head>
        <body>
            <h1>DevOps at Your Service</h1>
            <p>Chat interface loading...</p>
            <script>
                window.location.href = '/static/index.html';
            </script>
        </body>
    </html>
    """)


@app.get("/dev", response_class=HTMLResponse)
@app.get("/dev/", response_class=HTMLResponse)
async def get_chat_interface_dev():
    """Serve the chat interface (dev route)."""
    return await get_chat_interface()


@app.post("/chat")
@app.post("/dev/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Process chat message."""
    try:
        response = await chatbot_agent.process_message(
            request.session_id,
            request.message
        )
        return response
    except Exception as e:
        chatbot_agent.logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/session/{session_id}")
@app.get("/dev/session/{session_id}")
async def get_session(session_id: str):
    """Get chat session history."""
    try:
        session = await chatbot_agent.get_session(session_id)
        return session
    except Exception as e:
        chatbot_agent.logger.error(f"Error retrieving session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
@app.get("/dev/health")
@app.get("/chatbot/health")
@app.get("/dev/chatbot/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "chatbot",
        "service": "DevOps at Your Service",
        "version": __version__,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/agents/health")
@app.get("/dev/api/agents/health")
async def get_agents_health():
    """Get health status of all agents."""
    agents = {
        "planner": os.getenv('PLANNER_URL', 'http://planner-agent:8000') + '/health',
        "codegen": os.getenv('CODEGEN_URL', 'http://codegen-agent:8001') + '/health',
        "remediation": os.getenv('REMEDIATION_URL', 'http://remediation-agent:8002') + '/health',
        "chatbot": "healthy",
        "migration": os.getenv('MIGRATION_URL', 'http://migration-agent:8004') + '/health',
    }

    health_status = {}

    async with httpx.AsyncClient(timeout=5.0) as client:
        for agent_name, endpoint in agents.items():
            if agent_name == "chatbot":
                health_status[agent_name] = {
                    "status": "healthy",
                    "agent": "chatbot",
                    "version": __version__,
                    "http_status": "healthy"
                }
            else:
                try:
                    response = await client.get(endpoint)
                    if response.status_code == 200:
                        health_status[agent_name] = response.json()
                        health_status[agent_name]["http_status"] = "healthy"
                    else:
                        health_status[agent_name] = {
                            "status": "unhealthy",
                            "http_status": f"error_{response.status_code}"
                        }
                except httpx.TimeoutException:
                    health_status[agent_name] = {
                        "status": "timeout",
                        "http_status": "timeout"
                    }
                except Exception as e:
                    health_status[agent_name] = {
                        "status": "error",
                        "http_status": "error",
                        "error": str(e)
                    }

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "agents": health_status
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
