"""Secure configuration manager for API key management and rotation."""

import asyncio
import hashlib
import logging
import os
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
from cryptography.fernet import Fernet
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class APIKeyInfo(BaseModel):
    """Information about an API key."""

    key_id: str = Field(..., description="Unique identifier for the key")
    provider: str = Field(..., description="Provider this key belongs to")
    key_hash: str = Field(..., description="SHA-256 hash of the key")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = Field(default=None)
    expires_at: Optional[datetime] = Field(default=None)
    is_active: bool = Field(default=True)
    usage_count: int = Field(default=0)
    last_rotated: Optional[datetime] = Field(default=None)


class RotationPolicy(BaseModel):
    """Policy for API key rotation."""

    max_age_days: int = Field(default=90, description="Maximum age before rotation")
    max_usage_count: int = Field(default=10000, description="Max usage before rotation")
    rotation_grace_period_hours: int = Field(
        default=24, description="Grace period before forced rotation"
    )
    auto_rotate: bool = Field(default=True, description="Enable automatic rotation")


class SecureConfigManager:
    """Secure configuration manager with API key rotation capabilities."""

    def __init__(
        self,
        encryption_key: Optional[str] = None,
        aws_region: str = "us-east-1",
        secrets_manager_secret_name: Optional[str] = None,
    ):
        """Initialize the secure config manager.

        Args:
            encryption_key: Encryption key for local storage (if not using AWS)
            aws_region: AWS region for Secrets Manager
            secrets_manager_secret_name: Name of the secret in AWS Secrets Manager
        """
        self.encryption_key = encryption_key or os.getenv("GEMINI_SRE_ENCRYPTION_KEY")
        self.aws_region = aws_region
        self.secrets_manager_secret_name = secrets_manager_secret_name

        # Initialize encryption
        if self.encryption_key:
            self._fernet = Fernet(self.encryption_key.encode())
        else:
            self._fernet = None

        # Initialize AWS clients if using Secrets Manager
        self._secrets_client = None
        if self.secrets_manager_secret_name:
            try:
                self._secrets_client = boto3.client(
                    "secretsmanager", region_name=aws_region
                )
            except Exception as e:
                logger.warning(f"Failed to initialize AWS Secrets Manager: {e}")

        # In-memory cache for API keys
        self._key_cache: Dict[str, APIKeyInfo] = {}
        self._rotation_policies: Dict[str, RotationPolicy] = {}

        # Load existing keys
        asyncio.create_task(self._load_keys())

    def _hash_key(self, key: str) -> str:
        """Create a secure hash of the API key."""
        return hashlib.sha256(key.encode()).hexdigest()

    async def _load_keys(self) -> None:
        """Load API keys from storage."""
        try:
            if self._secrets_client and self.secrets_manager_secret_name:
                await self._load_from_aws_secrets()
            else:
                await self._load_from_env()
        except Exception as e:
            logger.error(f"Failed to load API keys: {e}")

    async def _load_from_aws_secrets(self) -> None:
        """Load API keys from AWS Secrets Manager."""
        try:
            if self._secrets_client is None:
                raise ValueError("Secrets client not initialized")
            response = await asyncio.to_thread(
                self._secrets_client.get_secret_value,
                SecretId=self.secrets_manager_secret_name,
            )

            secret_data = response["SecretString"]
            if self._fernet:
                secret_data = self._fernet.decrypt(secret_data.encode()).decode()

            import json

            keys_data = json.loads(secret_data)

            for key_data in keys_data.get("api_keys", []):
                key_info = APIKeyInfo(**key_data)
                self._key_cache[key_info.key_id] = key_info

        except Exception as e:
            logger.error(f"Failed to load keys from AWS Secrets Manager: {e}")

    async def _load_from_env(self) -> None:
        """Load API keys from environment variables."""
        env_mappings = {
            "GOOGLE_API_KEY": "gemini",
            "ANTHROPIC_API_KEY": "anthropic",
            "OPENAI_API_KEY": "openai",
            "XAI_API_KEY": "grok",
            "AWS_ACCESS_KEY_ID": "bedrock",
        }

        for env_var, provider in env_mappings.items():
            key_value = os.getenv(env_var)
            if key_value:
                key_id = f"{provider}_{secrets.token_hex(8)}"
                key_info = APIKeyInfo(
                    key_id=key_id,
                    provider=provider,
                    key_hash=self._hash_key(key_value),
                    created_at=datetime.utcnow(),
                )
                self._key_cache[key_id] = key_info

    async def store_key(
        self,
        provider: str,
        key_value: str,
        expires_at: Optional[datetime] = None,
    ) -> str:
        """Store a new API key securely.

        Args:
            provider: Provider name
            key_value: The actual API key
            expires_at: Optional expiration date

        Returns:
            Key ID for the stored key
        """
        key_id = f"{provider}_{secrets.token_hex(8)}"
        key_info = APIKeyInfo(
            key_id=key_id,
            provider=provider,
            key_hash=self._hash_key(key_value),
            expires_at=expires_at,
        )

        self._key_cache[key_id] = key_info
        await self._persist_keys()

        logger.info(f"Stored new API key for provider: {provider}")
        return key_id

    async def get_key(self, key_id: str) -> Optional[str]:
        """Retrieve an API key by ID.

        Args:
            key_id: The key identifier

        Returns:
            The API key value or None if not found
        """
        key_info = self._key_cache.get(key_id)
        if not key_info or not key_info.is_active:
            return None

        # Update usage statistics
        key_info.last_used = datetime.utcnow()
        key_info.usage_count += 1

        # Check if key needs rotation
        if await self._should_rotate_key(key_info):
            await self._schedule_rotation(key_info)

        return await self._retrieve_key_value(key_id)

    async def _should_rotate_key(self, key_info: APIKeyInfo) -> bool:
        """Check if a key should be rotated."""
        policy = self._rotation_policies.get(key_info.provider)
        if not policy or not policy.auto_rotate:
            return False

        # Check age
        if key_info.expires_at and datetime.utcnow() > key_info.expires_at:
            return True

        # Check usage count
        if key_info.usage_count >= policy.max_usage_count:
            return True

        # Check age policy
        age_days = (datetime.utcnow() - key_info.created_at).days
        if age_days >= policy.max_age_days:
            return True

        return False

    async def _schedule_rotation(self, key_info: APIKeyInfo) -> None:
        """Schedule a key for rotation."""
        logger.warning(f"Key {key_info.key_id} scheduled for rotation")
        # In a real implementation, this would trigger rotation workflow
        # For now, we just log the need for rotation

    async def _retrieve_key_value(self, key_id: str) -> Optional[str]:
        """Retrieve the actual key value from storage."""
        # In a real implementation, this would decrypt and return the key
        # For security, we don't store the actual key values in memory
        # This is a placeholder that would integrate with your key storage
        return os.getenv(f"API_KEY_{key_id}")

    async def _persist_keys(self) -> None:
        """Persist keys to storage."""
        try:
            keys_data = {
                "api_keys": [key_info.dict() for key_info in self._key_cache.values()]
            }

            if self._secrets_client and self.secrets_manager_secret_name:
                await self._persist_to_aws_secrets(keys_data)
            else:
                await self._persist_to_local(keys_data)

        except Exception as e:
            logger.error(f"Failed to persist keys: {e}")

    async def _persist_to_aws_secrets(self, keys_data: Dict[str, Any]) -> None:
        """Persist keys to AWS Secrets Manager."""
        import json

        secret_data = json.dumps(keys_data)

        if self._fernet:
            secret_data = self._fernet.encrypt(secret_data.encode()).decode()

        if self._secrets_client is None:
            raise ValueError("Secrets client not initialized")

        await asyncio.to_thread(
            self._secrets_client.update_secret,
            SecretId=self.secrets_manager_secret_name,
            SecretString=secret_data,
        )

    async def _persist_to_local(self, keys_data: Dict[str, Any]) -> None:
        """Persist keys to local encrypted storage."""
        # In a real implementation, this would write to encrypted local storage
        logger.debug("Keys persisted to local storage")

    def set_rotation_policy(self, provider: str, policy: RotationPolicy) -> None:
        """Set rotation policy for a provider."""
        self._rotation_policies[provider] = policy
        logger.info(f"Set rotation policy for provider: {provider}")

    def get_rotation_policy(self, provider: str) -> Optional[RotationPolicy]:
        """Get rotation policy for a provider."""
        return self._rotation_policies.get(provider)

    async def list_keys(self, provider: Optional[str] = None) -> List[APIKeyInfo]:
        """List all keys, optionally filtered by provider."""
        keys = list(self._key_cache.values())
        if provider:
            keys = [key for key in keys if key.provider == provider]
        return keys

    async def deactivate_key(self, key_id: str) -> bool:
        """Deactivate a key."""
        key_info = self._key_cache.get(key_id)
        if key_info:
            key_info.is_active = False
            await self._persist_keys()
            logger.info(f"Deactivated key: {key_id}")
            return True
        return False

    async def rotate_key(self, key_id: str, new_key_value: str) -> bool:
        """Rotate a key to a new value."""
        key_info = self._key_cache.get(key_id)
        if not key_info:
            return False

        # Update key info
        key_info.key_hash = self._hash_key(new_key_value)
        key_info.last_rotated = datetime.utcnow()
        key_info.usage_count = 0

        await self._persist_keys()
        logger.info(f"Rotated key: {key_id}")
        return True
