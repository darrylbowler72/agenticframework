"""Base agent class providing common functionality for all agents."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging
import json
from datetime import datetime
import boto3
from anthropic import Anthropic
from botocore.exceptions import ClientError


class BaseAgent(ABC):
    """
    Base class for all agents in the DevOps Agentic Framework.

    Provides common functionality:
    - Event publishing to EventBridge
    - Task state management in DynamoDB
    - Claude API integration
    - Logging and telemetry
    """

    def __init__(self, agent_name: str, region: str = "us-east-1"):
        """
        Initialize base agent.

        Args:
            agent_name: Unique identifier for this agent
            region: AWS region
        """
        self.agent_name = agent_name
        self.region = region

        # AWS clients
        self.eventbridge = boto3.client('events', region_name=region)
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.s3 = boto3.client('s3', region_name=region)
        self.secrets_manager = boto3.client('secretsmanager', region_name=region)

        # AI client
        self.claude_client = Anthropic()

        # Logging
        self.logger = self._setup_logger()

        # Tables
        self.workflows_table = None
        self._initialize_tables()

    def _setup_logger(self) -> logging.Logger:
        """Configure structured logging."""
        logger = logging.getLogger(self.agent_name)
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '{"timestamp": "%(asctime)s", "agent": "%(name)s", '
                '"level": "%(levelname)s", "message": "%(message)s"}'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _initialize_tables(self):
        """Initialize DynamoDB table references."""
        try:
            self.workflows_table = self.dynamodb.Table('workflows')
        except Exception as e:
            self.logger.warning(f"Could not initialize workflows table: {e}")

    @abstractmethod
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main task processing logic - must be implemented by subclasses.

        Args:
            task: Task data including parameters and context

        Returns:
            Dict containing task results
        """
        pass

    async def publish_event(
        self,
        event_type: str,
        detail: Dict[str, Any],
        event_bus_name: str = "default"
    ) -> Dict[str, Any]:
        """
        Publish event to AWS EventBridge.

        Args:
            event_type: Event detail type (e.g., 'task.created', 'deployment.completed')
            detail: Event payload
            event_bus_name: EventBridge bus name

        Returns:
            EventBridge response
        """
        try:
            event = {
                'Source': f'agentic-framework.{self.agent_name}',
                'DetailType': event_type,
                'Detail': json.dumps(detail),
                'EventBusName': event_bus_name
            }

            response = self.eventbridge.put_events(Entries=[event])

            if response['FailedEntryCount'] > 0:
                self.logger.error(f"Failed to publish event: {response}")
                raise Exception("Event publication failed")

            self.logger.info(f"Published event: {event_type}")
            return response

        except ClientError as e:
            self.logger.error(f"AWS error publishing event: {e}")
            raise

    async def update_task_status(
        self,
        workflow_id: str,
        task_id: str,
        status: str,
        output_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update task status in DynamoDB.

        Args:
            workflow_id: Workflow identifier
            task_id: Task identifier
            status: Task status (pending, in_progress, completed, failed)
            output_data: Optional task output data
            error_message: Optional error message if failed

        Returns:
            DynamoDB response
        """
        try:
            if not self.workflows_table:
                self.logger.warning("Workflows table not initialized")
                return {}

            update_expression = "SET #status = :status, updated_at = :updated_at"
            expression_values = {
                ':status': status,
                ':updated_at': datetime.utcnow().isoformat()
            }
            expression_names = {'#status': 'status'}

            if status in ['completed', 'failed']:
                update_expression += ", completed_at = :completed_at"
                expression_values[':completed_at'] = datetime.utcnow().isoformat()

            if output_data:
                update_expression += ", output_data = :output_data"
                expression_values[':output_data'] = output_data

            if error_message:
                update_expression += ", error_message = :error_message"
                expression_values[':error_message'] = error_message

            response = self.workflows_table.update_item(
                Key={
                    'workflow_id': workflow_id,
                    'task_id': task_id
                },
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values,
                ExpressionAttributeNames=expression_names,
                ReturnValues='ALL_NEW'
            )

            self.logger.info(f"Updated task {task_id} status to {status}")
            return response

        except ClientError as e:
            self.logger.error(f"Error updating task status: {e}")
            raise

    async def get_task(self, workflow_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve task data from DynamoDB.

        Args:
            workflow_id: Workflow identifier
            task_id: Task identifier

        Returns:
            Task data or None if not found
        """
        try:
            if not self.workflows_table:
                return None

            response = self.workflows_table.get_item(
                Key={
                    'workflow_id': workflow_id,
                    'task_id': task_id
                }
            )

            return response.get('Item')

        except ClientError as e:
            self.logger.error(f"Error retrieving task: {e}")
            return None

    async def call_claude(
        self,
        prompt: str,
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 4096,
        temperature: float = 1.0
    ) -> str:
        """
        Call Claude API for AI-powered analysis.

        Args:
            prompt: User prompt
            model: Claude model to use
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            Claude's response text
        """
        try:
            message = self.claude_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = message.content[0].text
            self.logger.info(f"Claude API call successful, tokens: {message.usage.input_tokens + message.usage.output_tokens}")

            return response_text

        except Exception as e:
            self.logger.error(f"Claude API error: {e}")
            raise

    async def store_artifact_s3(
        self,
        bucket: str,
        key: str,
        data: bytes,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Store artifact in S3.

        Args:
            bucket: S3 bucket name
            key: Object key
            data: Data to store
            metadata: Optional metadata

        Returns:
            S3 object URL
        """
        try:
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata

            self.s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                **extra_args
            )

            url = f"s3://{bucket}/{key}"
            self.logger.info(f"Stored artifact: {url}")

            return url

        except ClientError as e:
            self.logger.error(f"Error storing artifact: {e}")
            raise

    async def get_secret(self, secret_name: str) -> Dict[str, Any]:
        """
        Retrieve secret from AWS Secrets Manager.

        Args:
            secret_name: Secret identifier

        Returns:
            Secret data as dictionary
        """
        try:
            response = self.secrets_manager.get_secret_value(SecretId=secret_name)

            if 'SecretString' in response:
                return json.loads(response['SecretString'])
            else:
                return json.loads(response['SecretBinary'].decode('utf-8'))

        except ClientError as e:
            self.logger.error(f"Error retrieving secret {secret_name}: {e}")
            raise
