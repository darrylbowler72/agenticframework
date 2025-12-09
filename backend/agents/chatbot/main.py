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
import httpx

# Add parent directory to path for imports
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.agent_base import BaseAgent
from common.version import __version__

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
        self.environment = os.getenv('ENVIRONMENT', 'dev')
        self.sessions_table = self.dynamodb.Table(f'{self.environment}-chatbot-sessions')

        # Internal API endpoints for agents - use environment variable or fallback to hardcoded
        alb_base_url = os.getenv('INTERNAL_ALB_URL', 'http://internal-dev-agents-alb-1798962120.us-east-1.elb.amazonaws.com')
        self.agent_endpoints = {
            'planner': f'{alb_base_url}/workflows',
            'codegen': f'{alb_base_url}/generate',
            'remediation': f'{alb_base_url}/remediate',
            'migration': f'{alb_base_url}/migrate'
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
                    if "error" in result:
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
4. **GitHub Operations** - Create/delete/list repositories, create branches, manage gitflow branching (owner: darrylbowler72)
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
- github: {"operation": "create_repo|delete_repo|list_repos|create_branch|create_gitflow", "repo_name": "...", "description": "...", "private": true/false, "max_repos": 30, "branch_name": "...", "from_branch": "main"}
- jenkins: {"operation": "list_jobs|get_job|test_connection", "job_name": "...", "jenkins_url": "http://dev-agents-alb-1535480028.us-east-1.elb.amazonaws.com/jenkins", "username": "admin", "password": "admin"}
- migration: {"jenkinsfile_content": "...", "project_name": "...", "repository_url": "..."}

GitHub operation notes:
- "create_repo": Create a new repository
- "create_branch": Create a single branch in an existing repo
- "create_gitflow": Create standard gitflow branches (develop, feature/*, release/*, hotfix/*)

Jenkins operation notes:
- "list_jobs": List all Jenkins jobs (ALWAYS set action_needed=true when user asks to: "list", "show", "get", "display" Jenkins jobs or pipelines)
- "get_job": Get details about a specific Jenkins job (requires job_name)
- "test_connection": Test connection to Jenkins server

**IMPORTANT**: When the user asks to list/show/get Jenkins jobs or pipelines, you MUST:
1. Set "action_needed": true
2. Set "intent": "jenkins"
3. Set "parameters": {"operation": "list_jobs"}

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
                        # Create gitflow branches: develop, feature, release, hotfix
                        repo_name = parameters.get("repo_name", "")
                        results = []
                        for branch in ["develop"]:  # Start with develop
                            result = await self.create_github_branch(
                                repo_name=repo_name,
                                branch_name=branch,
                                from_branch="main"
                            )
                            results.append({"branch": branch, "result": result})
                        return {"success": True, "branches": results}
                    else:
                        return {"error": f"Unknown GitHub operation: {operation}"}

                else:
                    return {"info": f"Intent '{intent}' does not require backend agent execution"}

        except Exception as e:
            self.logger.error(f"Error executing action: {e}")
            return {"error": str(e)}

    async def process_message(self, session_id: str, user_message: str) -> ChatResponse:
        """Process user message and generate response."""

        # Get session history
        session = await self.get_session(session_id)
        messages = session.get('messages', [])

        # Add user message
        messages.append({
            'role': 'user',
            'content': user_message,
            'timestamp': datetime.utcnow().isoformat()
        })

        # Analyze intent
        intent_analysis = await self.analyze_intent(user_message, messages)

        # Execute action if needed
        action_result = None
        if intent_analysis.get('action_needed'):
            action_result = await self.execute_action(
                intent_analysis['intent'],
                intent_analysis.get('parameters', {})
            )

        # Generate response
        assistant_message = intent_analysis.get('response',
            "I'm here to help with your DevOps tasks! What would you like to do?")

        # Add action result to response if available
        if action_result:
            if 'error' in action_result:
                assistant_message += f"\n\nI encountered an error: {action_result['error']}"
            elif intent_analysis['intent'] == 'workflow':
                assistant_message += f"\n\n✅ Workflow created! ID: {action_result.get('workflow_id', 'N/A')}"
            elif intent_analysis['intent'] == 'codegen':
                assistant_message += f"\n\n✅ Service generated! {action_result.get('files_generated', 0)} files created."
            elif intent_analysis['intent'] == 'remediation':
                assistant_message += f"\n\n✅ Remediation initiated!"
            elif intent_analysis['intent'] == 'migration':
                if action_result.get('success'):
                    report = action_result.get('migration_report', {})
                    assistant_message += f"\n\n✅ Pipeline migrated successfully!"
                    assistant_message += f"\n- Pipeline type: {report.get('pipeline_type')}"
                    assistant_message += f"\n- Stages converted: {report.get('stages_converted')}"
                    assistant_message += f"\n- Environment variables: {report.get('environment_variables')}"
                    if action_result.get('warnings'):
                        assistant_message += f"\n\n⚠️ Warnings:"
                        for warning in action_result['warnings']:
                            assistant_message += f"\n- {warning}"
            elif intent_analysis['intent'] == 'github':
                if action_result.get('success'):
                    operation = intent_analysis.get('parameters', {}).get('operation')
                    if operation == 'create_repo':
                        repo = action_result.get('repository', {})
                        assistant_message += f"\n\n✅ Repository created successfully!"
                        assistant_message += f"\n- Name: {repo.get('full_name')}"
                        assistant_message += f"\n- URL: {repo.get('url')}"
                        assistant_message += f"\n- Private: {repo.get('private')}"
                    elif operation == 'delete_repo':
                        repo = action_result.get('repository', {})
                        assistant_message += f"\n\n✅ Repository deleted successfully!"
                        assistant_message += f"\n- Name: {repo.get('full_name')}"
                    elif operation == 'list_repos':
                        count = action_result.get('count', 0)
                        owner = action_result.get('owner', 'N/A')
                        repos = action_result.get('repositories', [])
                        assistant_message += f"\n\n✅ Found {count} repositories for {owner}:"
                        for repo in repos[:10]:  # Show first 10
                            assistant_message += f"\n- {repo.get('name')} ({repo.get('language', 'N/A')}) - {repo.get('description', 'No description')}"
                        if count > 10:
                            assistant_message += f"\n... and {count - 10} more repositories"
                    elif operation == 'create_branch':
                        branch = action_result.get('branch', {})
                        assistant_message += f"\n\n✅ Branch created successfully!"
                        assistant_message += f"\n- Branch: {branch.get('branch_name')}"
                        assistant_message += f"\n- Repository: {branch.get('repo_name')}"
                        assistant_message += f"\n- From: {branch.get('from_branch')}"
                        assistant_message += f"\n- URL: {branch.get('url')}"
                    elif operation == 'create_gitflow':
                        branches = action_result.get('branches', [])
                        assistant_message += f"\n\n✅ Gitflow branches created successfully!"
                        for branch_result in branches:
                            if branch_result.get('result', {}).get('success'):
                                assistant_message += f"\n- ✅ {branch_result['branch']}"
                            else:
                                assistant_message += f"\n- ❌ {branch_result['branch']}: {branch_result.get('result', {}).get('error', 'Unknown error')}"
            elif intent_analysis['intent'] == 'jenkins':
                if action_result.get('success'):
                    operation = intent_analysis.get('parameters', {}).get('operation')
                    if operation == 'list_jobs':
                        jobs = action_result.get('jobs', [])
                        count = action_result.get('jobs_count', 0)
                        jenkins_url = action_result.get('jenkins_url', 'N/A')
                        assistant_message += f"\n\n✅ Found {count} Jenkins jobs on {jenkins_url}:"
                        for job in jobs[:15]:  # Show first 15
                            color = job.get('color', 'notbuilt')
                            status_icon = "🟢" if color in ['blue', 'success'] else "🔴" if color in ['red', 'failed'] else "🟡" if color in ['yellow', 'unstable'] else "⚪"
                            assistant_message += f"\n{status_icon} {job.get('name')}"
                        if count > 15:
                            assistant_message += f"\n... and {count - 15} more jobs"
                    elif operation == 'get_job':
                        job_name = action_result.get('name', 'N/A')
                        description = action_result.get('description', 'No description')
                        url = action_result.get('url', 'N/A')
                        buildable = action_result.get('buildable', False)
                        last_build = action_result.get('last_build', {})
                        assistant_message += f"\n\n✅ Jenkins Job Details:"
                        assistant_message += f"\n- Name: {job_name}"
                        assistant_message += f"\n- Description: {description}"
                        assistant_message += f"\n- URL: {url}"
                        assistant_message += f"\n- Buildable: {buildable}"
                        if last_build:
                            assistant_message += f"\n- Last Build: #{last_build.get('number')} - {last_build.get('result', 'N/A')}"
                        if action_result.get('pipeline_script'):
                            assistant_message += f"\n- Has Pipeline Script: Yes"
                    elif operation == 'test_connection':
                        jenkins_url = action_result.get('url', 'N/A')
                        version = action_result.get('version', 'N/A')
                        jobs_count = action_result.get('jobs_count', 0)
                        assistant_message += f"\n\n✅ Jenkins connection successful!"
                        assistant_message += f"\n- URL: {jenkins_url}"
                        assistant_message += f"\n- Version: {version}"
                        assistant_message += f"\n- Total Jobs: {jobs_count}"

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
            agent_action=intent_analysis['intent'] if intent_analysis.get('action_needed') else None,
            action_result=action_result
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
    alb_base_url = os.getenv('INTERNAL_ALB_URL', 'http://internal-dev-agents-alb-1798962120.us-east-1.elb.amazonaws.com')
    agents = {
        "planner": f"{alb_base_url}/planner/health",
        "codegen": f"{alb_base_url}/codegen/health",
        "remediation": f"{alb_base_url}/remediation/health",
        "chatbot": "healthy",  # Self
        "migration": f"{alb_base_url}/migration/health"
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
