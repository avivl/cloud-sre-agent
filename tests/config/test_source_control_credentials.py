# tests/config/test_source_control_credentials.py

"""
Tests for source control credential configuration models.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from gemini_sre_agent.config.source_control_credentials import CredentialConfig


class TestCredentialConfig:
    """Test cases for CredentialConfig."""

    def test_minimal_valid_config(self):
        """Test minimal valid configuration."""
        config = CredentialConfig(token_env="GITHUB_TOKEN")
        assert config.token_env == "GITHUB_TOKEN"
        assert config.token is None
        assert config.username is None

    def test_token_from_env(self):
        """Test getting token from environment variable."""
        config = CredentialConfig(token_env="GITHUB_TOKEN")
        
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token_123"}):
            token = config.get_token()
            assert token == "test_token_123"

    def test_token_from_file(self):
        """Test getting token from file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test_token_from_file")
            temp_file = f.name

        try:
            config = CredentialConfig(token_file=temp_file)
            token = config.get_token()
            assert token == "test_token_from_file"
        finally:
            os.unlink(temp_file)

    def test_token_direct_value(self):
        """Test getting token from direct value."""
        config = CredentialConfig(token="direct_token")
        token = config.get_token()
        assert token == "direct_token"

    def test_username_from_env(self):
        """Test getting username from environment variable."""
        config = CredentialConfig(username_env="GITHUB_USERNAME")
        
        with patch.dict(os.environ, {"GITHUB_USERNAME": "testuser"}):
            username = config.get_username()
            assert username == "testuser"

    def test_username_direct_value(self):
        """Test getting username from direct value."""
        config = CredentialConfig(username="direct_user")
        username = config.get_username()
        assert username == "direct_user"

    def test_password_from_env(self):
        """Test getting password from environment variable."""
        config = CredentialConfig(token_env="GITHUB_TOKEN", password_env="GITHUB_PASSWORD")
        
        with patch.dict(os.environ, {"GITHUB_PASSWORD": "testpass"}):
            password = config.get_password()
            assert password == "testpass"

    def test_password_direct_value(self):
        """Test getting password from direct value."""
        config = CredentialConfig(token_env="GITHUB_TOKEN", password="direct_pass")
        password = config.get_password()
        assert password == "direct_pass"

    def test_ssh_key_path_validation(self):
        """Test SSH key path validation."""
        # Test with non-existent path
        with pytest.raises(ValidationError) as exc_info:
            CredentialConfig(ssh_key_path="/non/existent/path")
        assert "SSH key path does not exist" in str(exc_info.value)

        # Test with existing file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_file = f.name

        try:
            config = CredentialConfig(ssh_key_path=temp_file)
            assert config.ssh_key_path == temp_file
        finally:
            os.unlink(temp_file)

    def test_ssh_key_path_not_file(self):
        """Test SSH key path validation when path is not a file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValidationError) as exc_info:
                CredentialConfig(ssh_key_path=temp_dir)
            assert "SSH key path is not a file" in str(exc_info.value)

    def test_service_account_key_file_validation(self):
        """Test service account key file validation."""
        # Test with non-existent path
        with pytest.raises(ValidationError) as exc_info:
            CredentialConfig(service_account_key_file="/non/existent/path")
        assert "Service account key file does not exist" in str(exc_info.value)

        # Test with existing file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write('{"type": "service_account", "project_id": "test"}')
            temp_file = f.name

        try:
            config = CredentialConfig(service_account_key_file=temp_file)
            assert config.service_account_key_file == temp_file
        finally:
            os.unlink(temp_file)

    def test_service_account_key_file_not_file(self):
        """Test service account key file validation when path is not a file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ValidationError) as exc_info:
                CredentialConfig(service_account_key_file=temp_dir)
            assert "Service account key file is not a file" in str(exc_info.value)

    def test_no_auth_method_raises_error(self):
        """Test that no authentication method raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CredentialConfig()
        assert "At least one authentication method must be provided" in str(exc_info.value)

    def test_get_service_account_key_from_env(self):
        """Test getting service account key from environment variable."""
        config = CredentialConfig(service_account_key_env="SERVICE_ACCOUNT_KEY")
        
        key_data = {"type": "service_account", "project_id": "test"}
        with patch.dict(os.environ, {"SERVICE_ACCOUNT_KEY": '{"type": "service_account", "project_id": "test"}'}):
            key = config.get_service_account_key()
            assert key == key_data

    def test_get_service_account_key_from_file(self):
        """Test getting service account key from file."""
        key_data = {"type": "service_account", "project_id": "test"}
        
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            import json
            json.dump(key_data, f)
            temp_file = f.name

        try:
            config = CredentialConfig(service_account_key_file=temp_file)
            key = config.get_service_account_key()
            assert key == key_data
        finally:
            os.unlink(temp_file)

    def test_get_client_credentials(self):
        """Test getting OAuth client credentials."""
        config = CredentialConfig(
            client_id_env="CLIENT_ID",
            client_secret_env="CLIENT_SECRET"
        )
        
        with patch.dict(os.environ, {
            "CLIENT_ID": "test_client_id",
            "CLIENT_SECRET": "test_client_secret"
        }):
            client_id, client_secret = config.get_client_credentials()
            assert client_id == "test_client_id"
            assert client_secret == "test_client_secret"

    def test_get_client_credentials_direct(self):
        """Test getting OAuth client credentials from direct values."""
        config = CredentialConfig(
            client_id="direct_client_id",
            client_secret="direct_client_secret"
        )
        
        client_id, client_secret = config.get_client_credentials()
        assert client_id == "direct_client_id"
        assert client_secret == "direct_client_secret"

    def test_ssh_key_passphrase_from_env(self):
        """Test getting SSH key passphrase from environment variable."""
        config = CredentialConfig(token_env="GITHUB_TOKEN", ssh_key_passphrase_env="SSH_PASSPHRASE")
        
        with patch.dict(os.environ, {"SSH_PASSPHRASE": "test_passphrase"}):
            passphrase = config.get_ssh_key_passphrase()
            assert passphrase == "test_passphrase"

    def test_ssh_key_passphrase_direct(self):
        """Test getting SSH key passphrase from direct value."""
        config = CredentialConfig(token_env="GITHUB_TOKEN", ssh_key_passphrase="direct_passphrase")
        passphrase = config.get_ssh_key_passphrase()
        assert passphrase == "direct_passphrase"

    def test_token_file_read_error(self):
        """Test error handling when reading token file fails."""
        config = CredentialConfig(token_file="/non/existent/file")
        
        with pytest.raises(ValueError) as exc_info:
            config.get_token()
        assert "Failed to read token from file" in str(exc_info.value)

    def test_service_account_key_invalid_json(self):
        """Test error handling for invalid JSON in service account key."""
        config = CredentialConfig(service_account_key_env="INVALID_JSON")
        
        with patch.dict(os.environ, {"INVALID_JSON": "invalid json"}):
            with pytest.raises(ValueError) as exc_info:
                config.get_service_account_key()
            assert "Invalid JSON in service account key" in str(exc_info.value)

    def test_service_account_key_file_read_error(self):
        """Test error handling when reading service account key file fails."""
        # Create a temporary file first, then delete it to simulate read error
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            temp_file = f.name

        try:
            config = CredentialConfig(token_env="GITHUB_TOKEN", service_account_key_file=temp_file)
            # Delete the file after config creation to simulate read error
            os.unlink(temp_file)
            
            with pytest.raises(ValueError) as exc_info:
                config.get_service_account_key()
            assert "Failed to read service account key" in str(exc_info.value)
        except Exception:
            # Clean up if file still exists
            if os.path.exists(temp_file):
                os.unlink(temp_file)
            raise
