"""
Base Agent class providing common functionality for all agents.

Includes AWS SDK integrations, Claude API client, logging, and EventBridge communication.
"""

import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Optional, List

import boto3
import anthropic
from github import Github
from botocore.exceptions import ClientError


class BaseAgent(ABC):
    """
    Base class for all agents providing common functionality.

    Features:
    - AWS SDK integrations (S3, DynamoDB, EventBridge, Secrets Manager)
    - Claude AI API client
    - Structured logging
    - Event-driven task processing
    """

    def __init__(self, agent_name: str):
        """
        Initialize base agent.

        Args:
            agent_name: Name of the agent (e.g., 'planner', 'codegen', 'remediation')
        """
        self.agent_name = agent_name
        self.environment = os.getenv('ENVIRONMENT', 'dev')

        # Setup logging
        self.logger = self._setup_logging()

        # AWS clients
        self.s3_client = boto3.client('s3')
        self.dynamodb = boto3.resource('dynamodb')
        self.events_client = boto3.client('events')
        self.secrets_client = boto3.client('secretsmanager')

        # DynamoDB table references (initialized from environment variables)
        self.workflows_table = self._init_dynamodb_table('WORKFLOWS_TABLE_NAME', 'workflows')
        self.tasks_table = self._init_dynamodb_table('TASKS_TABLE_NAME', 'tasks')

        # Claude API client (will be initialized lazily)
        self._anthropic_client: Optional[anthropic.Anthropic] = None

        # GitHub API client (will be initialized lazily)
        self._github_client: Optional[Github] = None
        self._github_owner: Optional[str] = None

        self.logger.info(f"{agent_name.capitalize()} Agent initialized")

    def _setup_logging(self) -> logging.Logger:
        """Setup structured JSON logging."""
        logger = logging.getLogger(self.agent_name)
        logger.setLevel(logging.INFO)

        # Remove existing handlers
        logger.handlers = []

        # Create handler with JSON formatter
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)

        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3],
                    'agent': record.name,
                    'level': record.levelname,
                    'message': record.getMessage()
                }
                if record.exc_info:
                    log_data['exception'] = self.formatException(record.exc_info)
                return json.dumps(log_data)

        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)

        return logger

    def _init_dynamodb_table(self, env_var_name: str, default_table_suffix: str):
        """
        Initialize a DynamoDB table reference.

        Args:
            env_var_name: Environment variable name for the table
            default_table_suffix: Default table name suffix (will be prefixed with environment)

        Returns:
            DynamoDB Table resource or None if table not configured
        """
        try:
            # Check for environment variable override
            table_name = os.getenv(env_var_name)

            # If not set, use default with environment prefix
            if not table_name:
                table_name = f"{self.environment}-{default_table_suffix}"

            # Get table resource
            table = self.dynamodb.Table(table_name)

            # Verify table exists by checking its table_status
            # This will raise an exception if table doesn't exist
            table.load()

            return table

        except Exception as e:
            # Table doesn't exist or can't be accessed - this is OK for some agents
            # Log at debug level to avoid noise
            if hasattr(self, 'logger'):
                self.logger.debug(f"DynamoDB table not initialized for {env_var_name}: {e}")
            return None

    async def get_secret(self, secret_name: str) -> Dict[str, Any]:
        """
        Retrieve secret from AWS Secrets Manager.

        Args:
            secret_name: Name of the secret

        Returns:
            Secret value as dictionary
        """
        try:
            full_secret_name = f"{self.environment}-{secret_name}"
            response = self.secrets_client.get_secret_value(SecretId=full_secret_name)

            if 'SecretString' in response:
                return json.loads(response['SecretString'])
            else:
                # Binary secret
                return {'secret': response['SecretBinary']}

        except ClientError as e:
            self.logger.error(f"Error retrieving secret {secret_name}: {e}")
            raise

    async def _get_anthropic_client(self) -> anthropic.Anthropic:
        """Get or create Anthropic API client."""
        if self._anthropic_client is None:
            try:
                secret = await self.get_secret('anthropic-api-key')
                api_key = secret.get('api_key') or secret.get('key')
                self._anthropic_client = anthropic.Anthropic(api_key=api_key)
            except Exception as e:
                self.logger.error(f"Failed to initialize Anthropic client: {e}")
                raise

        return self._anthropic_client

    async def call_claude(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 1.0
    ) -> str:
        """
        Call Claude AI API.

        Args:
            prompt: User prompt
            system: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Claude's response text
        """
        try:
            client = await self._get_anthropic_client()

            kwargs = {
                'model': 'claude-3-haiku-20240307',
                'max_tokens': max_tokens,
                'temperature': temperature,
                'messages': [{'role': 'user', 'content': prompt}]
            }

            if system:
                kwargs['system'] = system

            message = client.messages.create(**kwargs)
            return message.content[0].text

        except Exception as e:
            self.logger.error(f"Error calling Claude API: {e}")
            raise

    async def _get_github_client(self) -> tuple[Github, str]:
        """
        Get or create GitHub API client.

        Returns:
            Tuple of (Github client, owner username)
        """
        if self._github_client is None:
            try:
                secret = await self.get_secret('github-credentials')
                token = secret.get('token') or secret.get('github_token')
                owner = secret.get('owner', 'darrylbowler72')

                self._github_client = Github(token)
                self._github_owner = owner

                # Test authentication
                user = self._github_client.get_user()
                self.logger.info(f"GitHub client initialized for user: {user.login}")

            except Exception as e:
                self.logger.error(f"Failed to initialize GitHub client: {e}")
                raise

        return self._github_client, self._github_owner

    async def store_artifact_s3(
        self,
        bucket: str,
        key: str,
        data: bytes,
        metadata: Optional[Dict[str, str]] = None
    ):
        """
        Store artifact in S3.

        Args:
            bucket: S3 bucket name
            key: Object key
            data: Data to store
            metadata: Optional metadata
        """
        try:
            full_bucket = f"{self.environment}-{bucket}"

            kwargs = {'Body': data}
            if metadata:
                kwargs['Metadata'] = metadata

            self.s3_client.put_object(
                Bucket=full_bucket,
                Key=key,
                **kwargs
            )

            self.logger.info(f"Stored artifact in S3: s3://{full_bucket}/{key}")

        except ClientError as e:
            self.logger.error(f"Error storing artifact in S3: {e}")
            raise

    async def get_artifact_s3(self, bucket: str, key: str) -> bytes:
        """
        Retrieve artifact from S3.

        Args:
            bucket: S3 bucket name
            key: Object key

        Returns:
            Object data
        """
        try:
            full_bucket = f"{self.environment}-{bucket}"
            response = self.s3_client.get_object(Bucket=full_bucket, Key=key)
            return response['Body'].read()

        except ClientError as e:
            self.logger.error(f"Error retrieving artifact from S3: {e}")
            raise

    async def put_dynamodb_item(self, table_name: str, item: Dict[str, Any]):
        """
        Put item in DynamoDB table.

        Args:
            table_name: Table name
            item: Item to store
        """
        try:
            full_table_name = f"{self.environment}-{table_name}"
            table = self.dynamodb.Table(full_table_name)
            table.put_item(Item=item)

            self.logger.info(f"Stored item in DynamoDB table {full_table_name}")

        except ClientError as e:
            self.logger.error(f"Error putting item in DynamoDB: {e}")
            raise

    async def get_dynamodb_item(
        self,
        table_name: str,
        key: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Get item from DynamoDB table.

        Args:
            table_name: Table name
            key: Primary key

        Returns:
            Item or None if not found
        """
        try:
            full_table_name = f"{self.environment}-{table_name}"
            table = self.dynamodb.Table(full_table_name)
            response = table.get_item(Key=key)
            return response.get('Item')

        except ClientError as e:
            self.logger.error(f"Error getting item from DynamoDB: {e}")
            raise

    async def update_dynamodb_item(
        self,
        table_name: str,
        key: Dict[str, Any],
        update_expression: str,
        expression_values: Dict[str, Any]
    ):
        """
        Update item in DynamoDB table.

        Args:
            table_name: Table name
            key: Primary key
            update_expression: Update expression
            expression_values: Expression attribute values
        """
        try:
            full_table_name = f"{self.environment}-{table_name}"
            table = self.dynamodb.Table(full_table_name)

            table.update_item(
                Key=key,
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )

            self.logger.info(f"Updated item in DynamoDB table {full_table_name}")

        except ClientError as e:
            self.logger.error(f"Error updating item in DynamoDB: {e}")
            raise

    async def publish_event(
        self,
        detail_type: str,
        detail: Dict[str, Any],
        source: Optional[str] = None
    ):
        """
        Publish event to EventBridge.

        Args:
            detail_type: Event detail type
            detail: Event detail
            source: Event source (defaults to agent name)
        """
        try:
            event_bus_name = f"{self.environment}-agentic-framework"
            event_source = source or f"agentic.{self.agent_name}"

            self.events_client.put_events(
                Entries=[{
                    'EventBusName': event_bus_name,
                    'Source': event_source,
                    'DetailType': detail_type,
                    'Detail': json.dumps(detail)
                }]
            )

            self.logger.info(f"Published event: {detail_type}")

        except ClientError as e:
            self.logger.error(f"Error publishing event: {e}")
            raise

    @abstractmethod
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a task. Must be implemented by subclasses.

        Args:
            task: Task data

        Returns:
            Task result
        """
        pass
