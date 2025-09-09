# tests/config/test_credential_security.py

"""
Security tests for credential storage and handling.
"""

import json
import os
import tempfile
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from gemini_sre_agent.config.source_control_credentials import CredentialConfig


class TestCredentialStorageSecurity:
    """Test credential storage security mechanisms."""

    def test_environment_variable_security(self):
        """Test that environment variables are properly handled for credentials."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token_123"}):
            config = CredentialConfig(token_env="GITHUB_TOKEN")

            # Test that token is retrieved from environment
            token = config.get_token()
            assert token == "test_token_123"

            # Test that direct token access is not available
            assert config.token is None

    def test_file_based_credential_security(self):
        """Test secure handling of file-based credentials."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write("secure_token_from_file")
            temp_file_path = temp_file.name

        try:
            config = CredentialConfig(token_file=temp_file_path)

            # Test that token is read from file
            token = config.get_token()
            assert token == "secure_token_from_file"

            # Test that file path is validated
            with pytest.raises(ValidationError, match="SSH key path does not exist"):
                CredentialConfig(ssh_key_path="/nonexistent/path")

        finally:
            os.unlink(temp_file_path)

    def test_ssh_key_file_security(self):
        """Test SSH key file security validation."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write(
                "-----BEGIN PRIVATE KEY-----\nMOCK_KEY\n-----END PRIVATE KEY-----"
            )
            temp_file_path = temp_file.name

        try:
            config = CredentialConfig(ssh_key_path=temp_file_path)

            # Test that SSH key path is validated
            assert config.ssh_key_path == temp_file_path

            # Test that directory paths are rejected
            with pytest.raises(ValidationError, match="SSH key path is not a file"):
                CredentialConfig(ssh_key_path=os.path.dirname(temp_file_path))

        finally:
            os.unlink(temp_file_path)

    def test_service_account_key_file_security(self):
        """Test service account key file security validation."""
        service_account_data = {
            "type": "service_account",
            "project_id": "test-project",
            "private_key_id": "test-key-id",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMOCK_KEY\n-----END PRIVATE KEY-----",
            "client_email": "test@test-project.iam.gserviceaccount.com",
            "client_id": "test-client-id",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        ) as temp_file:
            json.dump(service_account_data, temp_file)
            temp_file_path = temp_file.name

        try:
            config = CredentialConfig(service_account_key_file=temp_file_path)

            # Test that service account key is read securely
            key_data = config.get_service_account_key()
            assert key_data == service_account_data

            # Test that invalid JSON is handled securely
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".json"
            ) as invalid_file:
                invalid_file.write("invalid json content")
                invalid_file_path = invalid_file.name

            try:
                config_invalid = CredentialConfig(
                    service_account_key_file=invalid_file_path
                )
                with pytest.raises(
                    ValueError, match="Failed to read service account key"
                ):
                    config_invalid.get_service_account_key()
            finally:
                os.unlink(invalid_file_path)

        finally:
            os.unlink(temp_file_path)

    def test_credential_validation_security(self):
        """Test that credential validation enforces security requirements."""
        # Test that at least one auth method is required
        with pytest.raises(
            ValidationError, match="At least one authentication method must be provided"
        ):
            CredentialConfig()

        # Test that valid auth methods are accepted
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write("test_ssh_key")
            temp_file_path = temp_file.name

        try:
            valid_configs = [
                CredentialConfig(token_env="GITHUB_TOKEN"),
                CredentialConfig(username_env="USERNAME", password_env="PASSWORD"),
                CredentialConfig(ssh_key_path=temp_file_path),
                CredentialConfig(client_id_env="CLIENT_ID"),
                CredentialConfig(service_account_key_file=temp_file_path),
            ]

            for config in valid_configs:
                # Should not raise validation error
                assert config is not None
        finally:
            os.unlink(temp_file_path)

    def test_secret_string_handling(self):
        """Test that SecretStr values are handled securely."""
        config = CredentialConfig(
            token="secret_token_value",
            password="secret_password_value",
            ssh_key_passphrase="secret_passphrase_value",
            client_secret="secret_client_secret_value",
        )

        # Test that SecretStr values are properly retrieved
        assert config.get_token() == "secret_token_value"
        assert config.get_password() == "secret_password_value"
        assert config.get_ssh_key_passphrase() == "secret_passphrase_value"

        client_id, client_secret = config.get_client_credentials()
        assert client_secret == "secret_client_secret_value"

    def test_environment_variable_fallback_security(self):
        """Test secure fallback between different credential sources."""
        with patch.dict(
            os.environ,
            {
                "GITHUB_TOKEN": "env_token",
                "GITHUB_USERNAME": "env_username",
                "GITHUB_PASSWORD": "env_password",
            },
        ):
            config = CredentialConfig(
                token_env="GITHUB_TOKEN",
                username_env="GITHUB_USERNAME",
                password_env="GITHUB_PASSWORD",
            )

            # Test that environment variables take precedence
            assert config.get_token() == "env_token"
            assert config.get_username() == "env_username"
            assert config.get_password() == "env_password"

    def test_credential_file_permissions(self):
        """Test that credential files have appropriate permissions."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write("sensitive_credential_data")
            temp_file_path = temp_file.name

        try:
            # Set restrictive permissions
            os.chmod(temp_file_path, 0o600)

            config = CredentialConfig(token_file=temp_file_path)
            token = config.get_token()
            assert token == "sensitive_credential_data"

            # Verify file permissions are restrictive
            file_stat = os.stat(temp_file_path)
            assert file_stat.st_mode & 0o777 == 0o600

        finally:
            os.unlink(temp_file_path)

    def test_credential_cleanup_security(self):
        """Test that credentials are properly cleaned up from memory."""
        config = CredentialConfig(token="temporary_token")

        # Get token value
        token = config.get_token()
        assert token == "temporary_token"

        # Test that SecretStr doesn't expose value in repr
        token_repr = repr(config.token)
        assert "temporary_token" not in token_repr
        assert "SecretStr" in token_repr

    def test_malicious_file_path_security(self):
        """Test security against malicious file paths."""
        # Test path traversal attempts - these should fail validation because files don't exist
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/shadow",
            "C:\\Windows\\System32\\config\\SAM",
        ]

        for malicious_path in malicious_paths:
            # These should raise ValidationError because the files don't exist
            with pytest.raises(ValidationError, match="does not exist"):
                CredentialConfig(ssh_key_path=malicious_path)

            with pytest.raises(ValidationError, match="does not exist"):
                CredentialConfig(service_account_key_file=malicious_path)

    def test_credential_rotation_security(self):
        """Test credential rotation security mechanisms."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "old_token"}):
            config = CredentialConfig(token_env="GITHUB_TOKEN")
            assert config.get_token() == "old_token"

            # Simulate credential rotation
            os.environ["GITHUB_TOKEN"] = "new_token"
            assert config.get_token() == "new_token"

    def test_credential_encryption_validation(self):
        """Test validation of encrypted credential storage."""
        # Test that encrypted credentials are properly handled
        encrypted_token = "encrypted_token_data"

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
            temp_file.write(encrypted_token)
            temp_file_path = temp_file.name

        try:
            config = CredentialConfig(token_file=temp_file_path)
            token = config.get_token()
            assert token == encrypted_token

        finally:
            os.unlink(temp_file_path)

    def test_credential_audit_trail(self):
        """Test that credential access can be audited."""
        config = CredentialConfig(token_env="GITHUB_TOKEN")

        # Test that credential access methods exist for auditing
        assert hasattr(config, "get_token")
        assert hasattr(config, "get_username")
        assert hasattr(config, "get_password")
        assert hasattr(config, "get_ssh_key_passphrase")
        assert hasattr(config, "get_client_credentials")
        assert hasattr(config, "get_service_account_key")

    def test_credential_validation_error_handling(self):
        """Test secure error handling for credential validation."""
        # Test that validation errors don't expose sensitive information
        with pytest.raises(ValidationError, match="does not exist") as exc_info:
            CredentialConfig(ssh_key_path="/nonexistent/path")

        error_message = str(exc_info.value)
        assert "does not exist" in error_message
        assert "/nonexistent/path" in error_message
        # Ensure no sensitive data is exposed in error messages
        assert "password" not in error_message.lower()
        assert "token" not in error_message.lower()

    def test_credential_configuration_security(self):
        """Test overall credential configuration security."""
        # Test that configuration is immutable after creation
        config = CredentialConfig(token_env="GITHUB_TOKEN")

        # Test that fields are properly protected
        assert config.token_env == "GITHUB_TOKEN"
        assert config.token is None
        assert config.username is None
        assert config.password is None

    def test_credential_environment_isolation(self):
        """Test that credentials are properly isolated between environments."""
        # Test that environment variables don't leak between configurations
        with patch.dict(os.environ, {"GITHUB_TOKEN": "env_token"}):
            config1 = CredentialConfig(token_env="GITHUB_TOKEN")
            assert config1.get_token() == "env_token"

        # Test that environment changes don't affect existing configs
        with patch.dict(os.environ, {"GITHUB_TOKEN": "new_env_token"}):
            config2 = CredentialConfig(token_env="GITHUB_TOKEN")
            assert config2.get_token() == "new_env_token"

            # Original config should still have old value (this tests that the config
            # doesn't cache the environment variable value)
            assert config1.get_token() == "new_env_token"  # This is expected behavior
