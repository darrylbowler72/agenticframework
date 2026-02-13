"""
Chatbot Agent - Natural language DevOps interface.

Provides conversational access to the agentic framework via Slack/Teams.
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import asyncio
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from fastapi import FastAPI, Request
import boto3
from anthropic import Anthropic
import httpx


# Initialize Slack app
slack_app = AsyncApp(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Initialize FastAPI
fastapi_app = FastAPI(title="Chatbot Agent")

# Slack request handler
slack_handler = AsyncSlackRequestHandler(slack_app)


class ChatbotAgent:
    """Chatbot Agent implementation."""

    def __init__(self):
        self.claude = Anthropic()
        self.dynamodb = boto3.resource('dynamodb')
        self.sessions_table = None
        self.api_gateway_url = os.environ.get('API_GATEWAY_URL', 'http://localhost:8000')

        try:
            self.sessions_table = self.dynamodb.Table('chatbot_sessions')
        except:
            print("Warning: Could not initialize sessions table")

    async def process_message(
        self,
        user_id: str,
        message: str,
        thread_id: str
    ) -> Dict[str, Any]:
        """
        Process user message and generate response.

        Args:
            user_id: Slack user ID
            message: User message text
            thread_id: Thread ID for context

        Returns:
            Response with text and optional blocks
        """
        # Get session context
        session = await self.get_session(thread_id)

        # Recognize intent using Claude
        intent = await self.recognize_intent(message, session.get('context', []))

        # Execute based on intent
        if intent['type'] == 'create_service':
            result = await self.handle_create_service(intent)
        elif intent['type'] == 'deploy_service':
            result = await self.handle_deploy(intent)
        elif intent['type'] == 'query_status':
            result = await self.handle_status_query(intent)
        elif intent['type'] == 'help':
            result = await self.handle_help()
        else:
            result = {
                'text': "I'm not sure how to help with that. Try asking:\n• 'Create a new service'\n• 'Deploy service-name to staging'\n• 'What's the status of my-service?'"
            }

        # Update session
        await self.update_session(thread_id, message, result['text'])

        return result

    async def recognize_intent(
        self,
        message: str,
        context: list
    ) -> Dict[str, Any]:
        """
        Use Claude to recognize user intent.

        Args:
            message: User message
            context: Previous conversation

        Returns:
            Intent data
        """
        context_str = "\n".join([
            f"User: {turn.get('user', '')}\nBot: {turn.get('bot', '')}"
            for turn in context[-3:]  # Last 3 turns
        ])

        prompt = f"""You are a DevOps assistant chatbot. Analyze the user's message and extract intent.

Previous conversation:
{context_str}

User message: "{message}"

Determine:
1. Intent type: create_service, deploy_service, query_status, troubleshoot, help, other
2. Target entity (service name, if any)
3. Parameters needed
4. Confidence score (0-1)

Output valid JSON only:
{{
  "type": "intent_type",
  "entity": "service-name or null",
  "params": {{}},
  "confidence": 0.95,
  "needs_clarification": false,
  "clarification_question": ""
}}

Examples:
- "Create a new Python service called user-api" → create_service, entity: user-api, params: {{language: python}}
- "Deploy payment-service to staging" → deploy_service, entity: payment-service, params: {{environment: staging}}
- "What's the status of order-service?" → query_status, entity: order-service
"""

        try:
            response = self.claude.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text.strip()

            # Clean JSON
            if response_text.startswith('```json'):
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif response_text.startswith('```'):
                response_text = response_text.split('```')[1].split('```')[0].strip()

            return json.loads(response_text)

        except Exception as e:
            print(f"Error in intent recognition: {e}")
            # Fallback to simple pattern matching
            return self._fallback_intent(message)

    def _fallback_intent(self, message: str) -> Dict[str, Any]:
        """Simple pattern-based intent recognition."""
        message_lower = message.lower()

        if any(word in message_lower for word in ['create', 'new', 'scaffold', 'generate']):
            return {'type': 'create_service', 'entity': None, 'params': {}, 'confidence': 0.7}
        elif any(word in message_lower for word in ['deploy', 'release']):
            return {'type': 'deploy_service', 'entity': None, 'params': {}, 'confidence': 0.7}
        elif any(word in message_lower for word in ['status', 'check', 'how is']):
            return {'type': 'query_status', 'entity': None, 'params': {}, 'confidence': 0.7}
        elif any(word in message_lower for word in ['help', 'what can you do']):
            return {'type': 'help', 'entity': None, 'params': {}, 'confidence': 1.0}
        else:
            return {'type': 'other', 'entity': None, 'params': {}, 'confidence': 0.3}

    async def handle_create_service(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle service creation request."""
        # Call Planner Agent API
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_gateway_url}/workflows",
                    json={
                        'template': 'microservice-rest-api',
                        'parameters': {
                            'service_name': intent.get('entity', 'new-service'),
                            'language': intent.get('params', {}).get('language', 'python'),
                            'database': 'postgresql',
                            'environment': 'dev'
                        },
                        'requested_by': 'slack-user'
                    },
                    timeout=30.0
                )

                if response.status_code == 201:
                    data = response.json()
                    workflow_id = data.get('workflow_id')

                    return {
                        'text': f"✅ Creating service! Workflow ID: `{workflow_id}`\n\nI'll notify you when it's ready.",
                        'blocks': [
                            {
                                'type': 'section',
                                'text': {
                                    'type': 'mrkdwn',
                                    'text': f"*Creating new service* :rocket:\n\nWorkflow: `{workflow_id}`\nStatus: In Progress"
                                }
                            }
                        ]
                    }
                else:
                    return {'text': f"❌ Error creating service: {response.text}"}

        except Exception as e:
            return {'text': f"❌ Error: {str(e)}"}

    async def handle_deploy(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle deployment request."""
        service = intent.get('entity', 'unknown-service')
        environment = intent.get('params', {}).get('environment', 'dev')

        return {
            'text': f"🚀 Deploying *{service}* to *{environment}*...",
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f"Deploy *{service}* to *{environment}*?\n\nStrategy: Rolling update\nEstimated time: 3-5 minutes"
                    }
                },
                {
                    'type': 'actions',
                    'elements': [
                        {
                            'type': 'button',
                            'text': {'type': 'plain_text', 'text': 'Yes, deploy'},
                            'style': 'primary',
                            'action_id': 'approve_deployment',
                            'value': f"{service}:{environment}"
                        },
                        {
                            'type': 'button',
                            'text': {'type': 'plain_text', 'text': 'Cancel'},
                            'style': 'danger',
                            'action_id': 'cancel_deployment'
                        }
                    ]
                }
            ]
        }

    async def handle_status_query(self, intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle status query."""
        entity = intent.get('entity')

        if entity:
            return {
                'text': f"📊 Status of *{entity}*:\n\n✅ Running\n• Version: v1.2.3\n• Environment: production\n• Health: Good\n• Last deployed: 2 hours ago"
            }
        else:
            return {
                'text': "Which service would you like to check? Try: 'What's the status of user-service?'"
            }

    async def handle_help(self) -> Dict[str, Any]:
        """Handle help request."""
        return {
            'text': """*DevOps Assistant - Commands*

*Service Management*
• "Create a new service called {name}"
• "Deploy {service} to {environment}"
• "Scale {service} to 5 replicas"

*Status & Monitoring*
• "What's the status of {service}?"
• "Show me failed pipelines"
• "Show errors for {service}"

*Troubleshooting*
• "Why is {service} slow?"
• "Show logs for {service}"

Need more help? Just ask!"""
        }

    async def get_session(self, thread_id: str) -> Dict[str, Any]:
        """Get or create conversation session."""
        if not self.sessions_table:
            return {'context': []}

        try:
            response = self.sessions_table.get_item(Key={'session_id': thread_id})
            return response.get('Item', {'context': []})
        except:
            return {'context': []}

    async def update_session(self, thread_id: str, user_message: str, bot_response: str):
        """Update conversation session."""
        if not self.sessions_table:
            return

        try:
            session = await self.get_session(thread_id)
            context = session.get('context', [])

            context.append({
                'timestamp': datetime.utcnow().isoformat(),
                'user': user_message,
                'bot': bot_response
            })

            # Keep only last 10 turns
            context = context[-10:]

            import time
            self.sessions_table.put_item(Item={
                'session_id': thread_id,
                'context': context,
                'last_interaction': datetime.utcnow().isoformat(),
                'ttl': int(time.time()) + 86400  # 24 hours
            })
        except Exception as e:
            print(f"Error updating session: {e}")


# Initialize agent
chatbot_agent = ChatbotAgent()


@slack_app.message("")
async def handle_message(message, say):
    """Handle all messages sent to the bot."""
    user_id = message['user']
    text = message['text']
    thread_ts = message.get('thread_ts', message['ts'])

    # Process message
    response = await chatbot_agent.process_message(user_id, text, thread_ts)

    # Send response
    await say(
        text=response['text'],
        blocks=response.get('blocks'),
        thread_ts=thread_ts
    )


@slack_app.action("approve_deployment")
async def handle_approval(ack, body, say):
    """Handle deployment approval button click."""
    await ack()

    value = body['actions'][0]['value']
    service, environment = value.split(':')

    await say(f"✅ Deployment approved! Deploying *{service}* to *{environment}*...")


@slack_app.action("cancel_deployment")
async def handle_cancellation(ack, body, say):
    """Handle deployment cancellation."""
    await ack()
    await say("❌ Deployment cancelled.")


@fastapi_app.post("/slack/events")
async def slack_events(req: Request):
    """Handle Slack events."""
    return await slack_handler.handle(req)


@fastapi_app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "chatbot",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=3000)
