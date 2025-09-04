"""Tests for SecureConfigManager."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from gemini_sre_agent.security.config_manager import (
    APIKeyInfo,
    RotationPolicy,
    SecureConfigManager,
)


@pytest.fixture
def mock_config_manager():
    """Create a mock SecureConfigManager."""
    return SecureConfigManager(
        encryption_key="test-key",
        aws_region="us-east-1",
        secrets_manager_secret_name="test-secret",
    )


@pytest.fixture
def sample_api_key():
    """Create a sample API key info."""
    return APIKeyInfo(
        key_id="test-key-123",
        provider="gemini",
        key_hash="abc123",
        created_at=datetime.utcnow(),
    )


class TestSecureConfigManager:
    """Test cases for SecureConfigManager."""

    def test_initialization(self):
        """Test SecureConfigManager initialization."""
        manager = SecureConfigManager()
        assert manager.encryption_key is None
        assert manager.aws_region == "us-east-1"
        assert manager.secrets_manager_secret_name is None

    def test_initialization_with_params(self):
        """Test SecureConfigManager initialization with parameters."""
        manager = SecureConfigManager(
            encryption_key="test-key",
            aws_region="eu-west-1",
            secrets_manager_secret_name="my-secret",
        )
        assert manager.encryption_key == "test-key"
        assert manager.aws_region == "eu-west-1"
        assert manager.secrets_manager_secret_name == "my-secret"

    def test_hash_key(self, mock_config_manager):
        """Test API key hashing."""
        key = "test-api-key-123"
        hash1 = mock_config_manager._hash_key(key)
        hash2 = mock_config_manager._hash_key(key)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length
        assert hash1 != key

    @pytest.mark.asyncio
    async def test_store_key(self, mock_config_manager):
        """Test storing an API key."""
        with patch.object(mock_config_manager, "_persist_keys", new_callable=AsyncMock):
            key_id = await mock_config_manager.store_key(
                provider="gemini",
                key_value="test-key-value",
            )

            assert key_id.startswith("gemini_")
            assert len(key_id) > 10
            assert key_id in mock_config_manager._key_cache

    @pytest.mark.asyncio
    async def test_get_key(self, mock_config_manager, sample_api_key):
        """Test retrieving an API key."""
        mock_config_manager._key_cache["test-key-123"] = sample_api_key

        with patch.object(
            mock_config_manager, "_retrieve_key_value", return_value="test-key-value"
        ):
            key_value = await mock_config_manager.get_key("test-key-123")

            assert key_value == "test-key-value"
            assert sample_api_key.last_used is not None
            assert sample_api_key.usage_count == 1

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, mock_config_manager):
        """Test retrieving a non-existent key."""
        key_value = await mock_config_manager.get_key("nonexistent-key")
        assert key_value is None

    @pytest.mark.asyncio
    async def test_get_inactive_key(self, mock_config_manager, sample_api_key):
        """Test retrieving an inactive key."""
        sample_api_key.is_active = False
        mock_config_manager._key_cache["test-key-123"] = sample_api_key

        key_value = await mock_config_manager.get_key("test-key-123")
        assert key_value is None

    def test_set_rotation_policy(self, mock_config_manager):
        """Test setting rotation policy."""
        policy = RotationPolicy(
            max_age_days=30,
            max_usage_count=5000,
            auto_rotate=True,
        )

        mock_config_manager.set_rotation_policy("gemini", policy)

        stored_policy = mock_config_manager.get_rotation_policy("gemini")
        assert stored_policy == policy
        assert stored_policy.max_age_days == 30
        assert stored_policy.max_usage_count == 5000

    def test_get_rotation_policy_nonexistent(self, mock_config_manager):
        """Test getting rotation policy for non-existent provider."""
        policy = mock_config_manager.get_rotation_policy("nonexistent")
        assert policy is None

    @pytest.mark.asyncio
    async def test_should_rotate_key_by_age(self, mock_config_manager, sample_api_key):
        """Test key rotation by age."""
        # Set policy with short max age
        policy = RotationPolicy(max_age_days=1, auto_rotate=True)
        mock_config_manager.set_rotation_policy("gemini", policy)

        # Set key to be old
        sample_api_key.created_at = datetime.utcnow().replace(day=1)
        sample_api_key.provider = "gemini"

        should_rotate = await mock_config_manager._should_rotate_key(sample_api_key)
        assert should_rotate is True

    @pytest.mark.asyncio
    async def test_should_rotate_key_by_usage(
        self, mock_config_manager, sample_api_key
    ):
        """Test key rotation by usage count."""
        # Set policy with low usage limit
        policy = RotationPolicy(max_usage_count=100, auto_rotate=True)
        mock_config_manager.set_rotation_policy("gemini", policy)

        # Set key to have high usage
        sample_api_key.usage_count = 150
        sample_api_key.provider = "gemini"

        should_rotate = await mock_config_manager._should_rotate_key(sample_api_key)
        assert should_rotate is True

    @pytest.mark.asyncio
    async def test_should_rotate_key_expired(self, mock_config_manager, sample_api_key):
        """Test key rotation by expiration."""
        # Set key to be expired
        sample_api_key.expires_at = datetime.utcnow().replace(day=1)

        should_rotate = await mock_config_manager._should_rotate_key(sample_api_key)
        assert should_rotate is True

    @pytest.mark.asyncio
    async def test_should_not_rotate_key(self, mock_config_manager, sample_api_key):
        """Test that key should not be rotated."""
        # Set policy with high limits
        policy = RotationPolicy(
            max_age_days=365, max_usage_count=100000, auto_rotate=True
        )
        mock_config_manager.set_rotation_policy("gemini", policy)

        # Set key to be new and low usage
        sample_api_key.created_at = datetime.utcnow()
        sample_api_key.usage_count = 10
        sample_api_key.provider = "gemini"

        should_rotate = await mock_config_manager._should_rotate_key(sample_api_key)
        assert should_rotate is False

    @pytest.mark.asyncio
    async def test_list_keys(self, mock_config_manager):
        """Test listing keys."""
        # Add some test keys
        key1 = APIKeyInfo(key_id="key1", provider="gemini", key_hash="hash1")
        key2 = APIKeyInfo(key_id="key2", provider="openai", key_hash="hash2")
        key3 = APIKeyInfo(key_id="key3", provider="gemini", key_hash="hash3")

        mock_config_manager._key_cache = {"key1": key1, "key2": key2, "key3": key3}

        # List all keys
        all_keys = await mock_config_manager.list_keys()
        assert len(all_keys) == 3

        # List keys by provider
        gemini_keys = await mock_config_manager.list_keys(provider="gemini")
        assert len(gemini_keys) == 2
        assert all(key.provider == "gemini" for key in gemini_keys)

    @pytest.mark.asyncio
    async def test_deactivate_key(self, mock_config_manager, sample_api_key):
        """Test deactivating a key."""
        mock_config_manager._key_cache["test-key-123"] = sample_api_key

        with patch.object(mock_config_manager, "_persist_keys", new_callable=AsyncMock):
            result = await mock_config_manager.deactivate_key("test-key-123")

            assert result is True
            assert sample_api_key.is_active is False

    @pytest.mark.asyncio
    async def test_deactivate_nonexistent_key(self, mock_config_manager):
        """Test deactivating a non-existent key."""
        result = await mock_config_manager.deactivate_key("nonexistent-key")
        assert result is False

    @pytest.mark.asyncio
    async def test_rotate_key(self, mock_config_manager, sample_api_key):
        """Test rotating a key."""
        mock_config_manager._key_cache["test-key-123"] = sample_api_key

        with patch.object(mock_config_manager, "_persist_keys", new_callable=AsyncMock):
            result = await mock_config_manager.rotate_key(
                "test-key-123", "new-key-value"
            )

            assert result is True
            assert sample_api_key.key_hash != "abc123"  # Hash should change
            assert sample_api_key.last_rotated is not None
            assert sample_api_key.usage_count == 0

    @pytest.mark.asyncio
    async def test_rotate_nonexistent_key(self, mock_config_manager):
        """Test rotating a non-existent key."""
        result = await mock_config_manager.rotate_key(
            "nonexistent-key", "new-key-value"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_load_from_env(self, mock_config_manager):
        """Test loading keys from environment variables."""
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test-google-key"}):
            await mock_config_manager._load_from_env()

            # Should have created a key for gemini provider
            gemini_keys = [
                key
                for key in mock_config_manager._key_cache.values()
                if key.provider == "gemini"
            ]
            assert len(gemini_keys) == 1
            assert gemini_keys[0].key_hash == mock_config_manager._hash_key(
                "test-google-key"
            )

    @pytest.mark.asyncio
    async def test_load_from_aws_secrets(self, mock_config_manager):
        """Test loading keys from AWS Secrets Manager."""
        mock_response = {
            "SecretString": '{"api_keys": [{"key_id": "test-key", "provider": "gemini", "key_hash": "hash123", "created_at": "2023-01-01T00:00:00", "is_active": true, "usage_count": 0}]}'
        }

        with patch.object(
            mock_config_manager._secrets_client,
            "get_secret_value",
            return_value=mock_response,
        ):
            await mock_config_manager._load_from_aws_secrets()

            assert "test-key" in mock_config_manager._key_cache
            assert mock_config_manager._key_cache["test-key"].provider == "gemini"

    @pytest.mark.asyncio
    async def test_persist_to_aws_secrets(self, mock_config_manager):
        """Test persisting keys to AWS Secrets Manager."""
        keys_data = {"api_keys": []}

        with patch.object(
            mock_config_manager._secrets_client, "update_secret"
        ) as mock_update:
            await mock_config_manager._persist_to_aws_secrets(keys_data)

            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_persist_to_local(self, mock_config_manager):
        """Test persisting keys to local storage."""
        keys_data = {"api_keys": []}

        # Should not raise an exception
        await mock_config_manager._persist_to_local(keys_data)


class TestAPIKeyInfo:
    """Test cases for APIKeyInfo model."""

    def test_api_key_info_creation(self):
        """Test APIKeyInfo creation."""
        key_info = APIKeyInfo(
            key_id="test-key",
            provider="gemini",
            key_hash="abc123",
        )

        assert key_info.key_id == "test-key"
        assert key_info.provider == "gemini"
        assert key_info.key_hash == "abc123"
        assert key_info.is_active is True
        assert key_info.usage_count == 0

    def test_api_key_info_with_optional_fields(self):
        """Test APIKeyInfo with optional fields."""
        expires_at = datetime.utcnow()
        key_info = APIKeyInfo(
            key_id="test-key",
            provider="gemini",
            key_hash="abc123",
            expires_at=expires_at,
            is_active=False,
            usage_count=100,
        )

        assert key_info.expires_at == expires_at
        assert key_info.is_active is False
        assert key_info.usage_count == 100


class TestRotationPolicy:
    """Test cases for RotationPolicy model."""

    def test_rotation_policy_creation(self):
        """Test RotationPolicy creation."""
        policy = RotationPolicy(
            max_age_days=90,
            max_usage_count=10000,
            rotation_grace_period_hours=24,
            auto_rotate=True,
        )

        assert policy.max_age_days == 90
        assert policy.max_usage_count == 10000
        assert policy.rotation_grace_period_hours == 24
        assert policy.auto_rotate is True

    def test_rotation_policy_defaults(self):
        """Test RotationPolicy with default values."""
        policy = RotationPolicy()

        assert policy.max_age_days == 90
        assert policy.max_usage_count == 10000
        assert policy.rotation_grace_period_hours == 24
        assert policy.auto_rotate is True
