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

        # Internal API endpoints for agents
        self.agent_endpoints = {
            'planner': 'http://internal-dev-agents-alb-2094161508.us-east-1.elb.amazonaws.com/workflows',
            'codegen': 'http://internal-dev-agents-alb-2094161508.us-east-1.elb.amazonaws.com/generate',
            'remediation': 'http://internal-dev-agents-alb-2094161508.us-east-1.elb.amazonaws.com/remediate'
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
4. **General Help** - Answer questions about DevOps, the framework, or provide guidance

Analyze the user's message and respond with JSON in this format:
{
  "intent": "workflow|codegen|remediation|help|general",
  "action_needed": true/false,
  "parameters": {
    // Extract relevant parameters based on intent
  },
  "response": "Your conversational response to the user"
}

For action_needed=true, extract parameters:
- workflow: {"description": "...", "environment": "dev/staging/prod"}
- codegen: {"service_name": "...", "language": "...", "database": "...", "api_type": "..."}
- remediation: {"pipeline_id": "...", "project_id": "..."}

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
                            "project_id": parameters.get("project_id", "default")
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
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "chatbot",
        "service": "DevOps at Your Service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
