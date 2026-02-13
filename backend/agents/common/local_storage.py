"""
Local storage implementations for running agents without AWS infrastructure.

When LOCAL_MODE=true, these classes replace AWS services:
- DynamoDB -> JSON file-backed in-memory store
- S3 -> Local filesystem (/data/artifacts/)
- EventBridge -> No-op with logging
- Secrets Manager -> Environment variables
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Directory for persistent JSON data
LOCAL_DATA_DIR = os.getenv('LOCAL_DATA_DIR', '/data/db')
LOCAL_ARTIFACTS_DIR = os.getenv('LOCAL_ARTIFACTS_DIR', '/data/artifacts')


class LocalDynamoDBTable:
    """In-memory dict with JSON file persistence, mimics boto3 DynamoDB Table."""

    def __init__(self, table_name: str):
        self.table_name = table_name
        self._data: Dict[str, Any] = {}
        self._file_path = os.path.join(LOCAL_DATA_DIR, f"{table_name}.json")
        self._load()

    def _load(self):
        """Load data from JSON file if it exists."""
        try:
            if os.path.exists(self._file_path):
                with open(self._file_path, 'r') as f:
                    self._data = json.load(f)
                logger.info(f"Loaded {len(self._data)} items from {self._file_path}")
        except Exception as e:
            logger.warning(f"Could not load {self._file_path}: {e}")
            self._data = {}

    def _save(self):
        """Persist data to JSON file."""
        try:
            os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
            with open(self._file_path, 'w') as f:
                json.dump(self._data, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Could not save {self._file_path}: {e}")

    def _make_key(self, key_dict: Dict[str, Any]) -> str:
        """Create a string key from a DynamoDB key dict."""
        return "|".join(f"{k}={v}" for k, v in sorted(key_dict.items()))

    def load(self):
        """Mimic boto3 Table.load() - verifies the table 'exists'."""
        self._load()

    def put_item(self, Item: Dict[str, Any], **kwargs):
        """Store an item."""
        # Try to detect the key from common patterns
        key = self._make_key({k: v for k, v in Item.items() if k.endswith('_id') or k == 'id'})
        if not key:
            key = self._make_key({"_auto": str(len(self._data))})
        self._data[key] = Item
        self._save()
        return {}

    def get_item(self, Key: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Retrieve an item by key."""
        key = self._make_key(Key)
        item = self._data.get(key)
        if item:
            return {'Item': item}
        return {}

    def query(self, **kwargs) -> Dict[str, Any]:
        """Simple query - returns all items (local mode doesn't need complex queries)."""
        items = list(self._data.values())
        return {'Items': items, 'Count': len(items)}

    def update_item(self, Key: Dict[str, Any], UpdateExpression: str = "",
                    ExpressionAttributeValues: Dict = None, **kwargs):
        """Update an item (simplified - merges values)."""
        key = self._make_key(Key)
        item = self._data.get(key, dict(Key))
        if ExpressionAttributeValues:
            for attr_key, attr_val in ExpressionAttributeValues.items():
                # Strip the leading ':' from expression attribute names
                clean_key = attr_key.lstrip(':')
                item[clean_key] = attr_val
        self._data[key] = item
        self._save()
        return {}

    def scan(self, **kwargs) -> Dict[str, Any]:
        """Scan all items."""
        items = list(self._data.values())
        return {'Items': items, 'Count': len(items)}


class LocalDynamoDBResource:
    """Factory that returns LocalDynamoDBTable instances, mimics boto3.resource('dynamodb')."""

    def Table(self, name: str) -> LocalDynamoDBTable:
        return LocalDynamoDBTable(name)


class LocalS3Client:
    """Filesystem-backed S3 client."""

    def put_object(self, Bucket: str, Key: str, Body: bytes, **kwargs):
        """Store object to local filesystem."""
        file_path = os.path.join(LOCAL_ARTIFACTS_DIR, Bucket, Key)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(Body if isinstance(Body, bytes) else Body.encode('utf-8'))
        logger.info(f"[LocalS3] Stored: {Bucket}/{Key}")
        return {}

    def get_object(self, Bucket: str, Key: str, **kwargs) -> Dict[str, Any]:
        """Retrieve object from local filesystem."""
        file_path = os.path.join(LOCAL_ARTIFACTS_DIR, Bucket, Key)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No such key: {Bucket}/{Key}")
        with open(file_path, 'rb') as f:
            data = f.read()

        class _Body:
            def __init__(self, content):
                self._content = content
            def read(self):
                return self._content

        return {'Body': _Body(data)}


class LocalEventsClient:
    """No-op EventBridge client that logs events."""

    def put_events(self, Entries: list, **kwargs):
        """Log events instead of publishing to EventBridge."""
        for entry in Entries:
            logger.info(
                f"[LocalEventBridge] Event: source={entry.get('Source')}, "
                f"type={entry.get('DetailType')}, detail={entry.get('Detail', '')[:200]}"
            )
        return {'FailedEntryCount': 0, 'Entries': [{'EventId': 'local-event'}]}


class LocalSecretsClient:
    """Reads secrets from environment variables."""

    def get_secret_value(self, SecretId: str, **kwargs) -> Dict[str, Any]:
        """Return secrets from environment variables."""
        secret_id_lower = SecretId.lower()

        if 'anthropic' in secret_id_lower:
            api_key = os.getenv('ANTHROPIC_API_KEY', '')
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            return {'SecretString': json.dumps({'api_key': api_key})}

        if 'github' in secret_id_lower:
            token = os.getenv('GITHUB_TOKEN', '')
            owner = os.getenv('GITHUB_OWNER', 'darrylbowler72')
            if not token:
                raise ValueError("GITHUB_TOKEN environment variable not set")
            return {'SecretString': json.dumps({'token': token, 'owner': owner})}

        if 'slack' in secret_id_lower:
            bot_token = os.getenv('SLACK_BOT_TOKEN', '')
            signing_secret = os.getenv('SLACK_SIGNING_SECRET', '')
            return {'SecretString': json.dumps({
                'bot_token': bot_token,
                'signing_secret': signing_secret
            })}

        raise ValueError(f"Unknown secret: {SecretId}")
