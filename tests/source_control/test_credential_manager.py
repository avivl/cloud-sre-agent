# tests/source_control/test_credential_manager.py

import os
import tempfile

import pytest

from gemini_sre_agent.source_control.credential_manager import (
    CredentialManager,
    EnvironmentBackend,
    FileBackend,
)


class TestEnvironmentBackend:
    """Test the EnvironmentBackend class."""

    @pytest.fixture
    def backend(self):
        return EnvironmentBackend()

    @pytest.mark.asyncio
    async def test_get_existing_env_var(self, backend):
        """Test getting an existing environment variable."""
        os.environ["TEST_KEY"] = "test_value"
        try:
            result = await backend.get("TEST_KEY")
            assert result == "test_value"
        finally:
            if "TEST_KEY" in os.environ:
                del os.environ["TEST_KEY"]

    @pytest.mark.asyncio
    async def test_get_nonexistent_env_var(self, backend):
        """Test getting a non-existent environment variable."""
        result = await backend.get("NONEXISTENT_KEY")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_env_var(self, backend):
        """Test setting an environment variable."""
        try:
            await backend.set("TEST_SET_KEY", "test_set_value")
            assert os.environ["TEST_SET_KEY"] == "test_set_value"
        finally:
            if "TEST_SET_KEY" in os.environ:
                del os.environ["TEST_SET_KEY"]

    @pytest.mark.asyncio
    async def test_delete_existing_env_var(self, backend):
        """Test deleting an existing environment variable."""
        os.environ["TEST_DELETE_KEY"] = "test_delete_value"
        try:
            await backend.delete("TEST_DELETE_KEY")
            assert "TEST_DELETE_KEY" not in os.environ
        finally:
            if "TEST_DELETE_KEY" in os.environ:
                del os.environ["TEST_DELETE_KEY"]

    @pytest.mark.asyncio
    async def test_delete_nonexistent_env_var(self, backend):
        """Test deleting a non-existent environment variable."""
        # Should not raise an exception
        await backend.delete("NONEXISTENT_DELETE_KEY")


class TestFileBackend:
    """Test the FileBackend class."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def backend(self, temp_dir):
        return FileBackend(temp_dir)

    @pytest.mark.asyncio
    async def test_get_nonexistent_file(self, backend):
        """Test getting a non-existent file."""
        result = await backend.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get_file(self, backend):
        """Test setting and getting a file."""
        test_data = '{"key": "value"}'
        await backend.set("test_key", test_data)
        result = await backend.get("test_key")
        assert result == test_data

    @pytest.mark.asyncio
    async def test_delete_file(self, backend):
        """Test deleting a file."""
        test_data = '{"key": "value"}'
        await backend.set("test_delete_key", test_data)
        await backend.delete("test_delete_key")
        result = await backend.get("test_delete_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_sanitize_key(self, backend):
        """Test that keys are properly sanitized."""
        test_data = '{"key": "value"}'
        await backend.set("test/key/with/slashes", test_data)
        result = await backend.get("test/key/with/slashes")
        assert result == test_data


class TestCredentialManager:
    """Test the CredentialManager class."""

    @pytest.fixture
    def manager(self):
        return CredentialManager()

    @pytest.fixture
    def manager_with_encryption(self):
        return CredentialManager(encryption_key="test-key-12345")

    @pytest.mark.asyncio
    async def test_get_credentials_success(self, manager):
        """Test successful credential retrieval."""
        # Register environment backend
        env_backend = EnvironmentBackend()
        manager.register_backend("env", env_backend, default=True)

        # Set test environment variable with JSON format
        os.environ["github-token"] = (
            '{"token": "test-token", "provider_type": "github"}'
        )
        try:
            credentials = await manager.get_credentials("env:github-token", "github")
            assert credentials["token"] == "test-token"
        finally:
            if "github-token" in os.environ:
                del os.environ["github-token"]

    @pytest.mark.asyncio
    async def test_get_credentials_with_explicit_backend(self, manager):
        """Test credential retrieval with explicit backend."""
        env_backend = EnvironmentBackend()
        manager.register_backend("env", env_backend)

        os.environ["github-token"] = (
            '{"token": "test-token", "provider_type": "github"}'
        )
        try:
            credentials = await manager.get_credentials("env:github-token", "github")
            assert credentials["token"] == "test-token"
        finally:
            if "github-token" in os.environ:
                del os.environ["github-token"]

    @pytest.mark.asyncio
    async def test_get_credentials_not_found(self, manager):
        """Test credential retrieval when not found."""
        env_backend = EnvironmentBackend()
        manager.register_backend("env", env_backend, default=True)

        with pytest.raises(ValueError, match="Credential not found"):
            await manager.get_credentials("nonexistent", "github")

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    async def test_get_credentials_invalid_json(self, manager, temp_dir):
        """Test credential retrieval with invalid JSON."""
        file_backend = FileBackend(temp_dir)
        manager.register_backend("file", file_backend, default=True)

        # Create a file with invalid JSON
        with open(os.path.join(temp_dir, "invalid.json"), "w") as f:
            f.write("invalid json")

        with pytest.raises(ValueError, match="Invalid credential format"):
            await manager.get_credentials("invalid", "github")

    @pytest.mark.asyncio
    async def test_get_credentials_provider_type_mismatch(self, manager):
        """Test credential retrieval with provider type mismatch."""
        env_backend = EnvironmentBackend()
        manager.register_backend("env", env_backend, default=True)

        os.environ["github-token"] = (
            '{"token": "test-token", "provider_type": "gitlab"}'
        )
        try:
            credentials = await manager.get_credentials("env:github-token", "github")
            # Should still return the credentials but with a warning
            assert credentials["token"] == "test-token"
        finally:
            if "github-token" in os.environ:
                del os.environ["github-token"]

    @pytest.mark.asyncio
    async def test_credential_caching(self, manager):
        """Test that credentials are cached."""
        env_backend = EnvironmentBackend()
        manager.register_backend("env", env_backend, default=True)

        os.environ["github-token"] = (
            '{"token": "test-token", "provider_type": "github"}'
        )
        try:
            # First call
            credentials1 = await manager.get_credentials("env:github-token", "github")
            # Second call should use cache
            credentials2 = await manager.get_credentials("env:github-token", "github")
            assert credentials1 == credentials2
        finally:
            if "github-token" in os.environ:
                del os.environ["github-token"]

    @pytest.mark.asyncio
    async def test_store_credentials(self, manager, temp_dir):
        """Test storing credentials."""
        file_backend = FileBackend(temp_dir)
        manager.register_backend("file", file_backend, default=True)

        credentials = {"token": "test-token", "provider_type": "github"}
        await manager.store_credentials("test-creds", credentials)

        # Verify the file was created
        assert os.path.exists(os.path.join(temp_dir, "test-creds.json"))

        # Verify we can retrieve it
        retrieved = await manager.get_credentials("test-creds", "github")
        assert retrieved == credentials

    @pytest.mark.asyncio
    async def test_rotate_credentials(self, manager, temp_dir):
        """Test credential rotation."""
        file_backend = FileBackend(temp_dir)
        manager.register_backend("file", file_backend, default=True)

        # Store initial credentials
        initial_creds = {"token": "old-token", "provider_type": "github"}
        await manager.store_credentials("test-creds", initial_creds)

        # Rotate credentials
        new_creds = {"token": "new-token", "provider_type": "github"}
        await manager.rotate_credentials("test-creds", new_creds)

        # Verify the credentials were updated
        retrieved = await manager.get_credentials("test-creds", "github")
        assert retrieved["token"] == "new-token"

    @pytest.mark.asyncio
    async def test_unknown_backend(self, manager):
        """Test error handling for unknown backend."""
        with pytest.raises(ValueError, match="Unknown credential backend"):
            await manager.get_credentials("unknown:test", "github")

    @pytest.mark.asyncio
    async def test_encryption(self, manager_with_encryption, temp_dir):
        """Test credential encryption."""
        file_backend = FileBackend(temp_dir)
        manager_with_encryption.register_backend("file", file_backend, default=True)

        credentials = {"token": "sensitive-token", "provider_type": "github"}
        await manager_with_encryption.store_credentials("encrypted-creds", credentials)

        # Verify the file was created
        cred_file = os.path.join(temp_dir, "encrypted-creds.json")
        assert os.path.exists(cred_file)

        # Verify the content is encrypted (not plain text)
        with open(cred_file, "r") as f:
            content = f.read()
            assert "sensitive-token" not in content

        # Verify we can decrypt and retrieve it
        retrieved = await manager_with_encryption.get_credentials(
            "encrypted-creds", "github"
        )
        assert retrieved == credentials
