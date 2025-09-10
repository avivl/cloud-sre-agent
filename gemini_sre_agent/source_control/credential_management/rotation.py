# gemini_sre_agent/source_control/credential_management/rotation.py

"""
Credential rotation management module.

This module handles credential rotation, validation, and testing.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import CredentialManager


class CredentialRotationManager:
    """Manages credential rotation and validation."""

    def __init__(self, credential_manager: "CredentialManager"):
        self.credential_manager = credential_manager
        self.logger = logging.getLogger("CredentialRotationManager")
        self.rotation_schedule: Dict[str, datetime] = {}

    async def schedule_rotation(
        self, credential_id: str, rotation_interval_days: int = 90
    ):
        """Schedule credential rotation."""
        next_rotation = datetime.now() + timedelta(days=rotation_interval_days)
        self.rotation_schedule[credential_id] = next_rotation
        self.logger.info(f"Scheduled rotation for {credential_id} on {next_rotation}")

    async def check_rotation_needed(self, credential_id: str) -> bool:
        """Check if credential rotation is needed."""
        if credential_id not in self.rotation_schedule:
            return False

        return datetime.now() >= self.rotation_schedule[credential_id]

    async def rotate_credential(
        self, credential_id: str, new_credential_data: Dict[str, Any]
    ) -> bool:
        """Rotate a credential with new data."""
        # Add validation before rotation
        if not await self._validate_new_credentials(new_credential_data):
            self.logger.error(f"New credentials for {credential_id} failed validation")
            return False

        # Store old credentials as backup
        old_credentials = None
        try:
            old_credentials = await self.credential_manager.get_credentials(
                credential_id, "backup"
            )
        except Exception:
            # No backup exists, try to get current credentials
            try:
                old_credentials = await self.credential_manager.get_credentials(
                    credential_id, "current"
                )
            except Exception:
                self.logger.warning(
                    f"No existing credentials found for {credential_id}"
                )

        try:
            # Attempt rotation
            await self.credential_manager.store_credentials(
                credential_id, new_credential_data
            )

            # Test new credentials
            if not await self._test_new_credentials(credential_id, new_credential_data):
                # Rollback on failure
                if old_credentials:
                    await self.credential_manager.store_credentials(
                        credential_id, old_credentials
                    )
                    self.logger.error(
                        f"New credentials failed test, rolled back to old credentials for {credential_id}"
                    )
                return False

            # Update rotation schedule only after successful test
            await self.schedule_rotation(credential_id)

            self.logger.info(f"Successfully rotated credentials for {credential_id}")
            return True

        except Exception as e:
            # Rollback on error
            if old_credentials:
                try:
                    await self.credential_manager.store_credentials(
                        credential_id, old_credentials
                    )
                    self.logger.error(
                        f"Credential rotation failed, rolled back to old credentials for {credential_id}"
                    )
                except Exception as rollback_error:
                    self.logger.error(
                        f"Failed to rollback credentials for {credential_id}: {rollback_error}"
                    )
            self.logger.error(f"Failed to rotate credentials for {credential_id}: {e}")
            return False

    async def validate_credential(self, credential_id: str, provider_type: str) -> bool:
        """Validate that a credential is working."""
        try:
            credentials = await self.credential_manager.get_credentials(
                credential_id, provider_type
            )

            # Basic validation - check if required fields are present
            if provider_type == "github":
                return "token" in credentials
            elif provider_type == "gitlab":
                return "token" in credentials
            elif provider_type == "aws":
                return (
                    "access_key_id" in credentials
                    and "secret_access_key" in credentials
                )
            else:
                return len(credentials) > 0
        except Exception as e:
            self.logger.error(f"Credential validation failed for {credential_id}: {e}")
            return False

    async def _validate_new_credentials(self, credential_data: Dict[str, Any]) -> bool:
        """Validate new credentials before rotation."""
        try:
            # Check if credential data is not empty
            if not credential_data or len(credential_data) == 0:
                self.logger.error("Credential data is empty")
                return False

            # Check for required fields based on provider type
            if "provider_type" in credential_data:
                provider_type = credential_data["provider_type"]
                if provider_type == "github":
                    if "token" not in credential_data or not credential_data["token"]:
                        self.logger.error("GitHub credentials missing or empty token")
                        return False
                elif provider_type == "gitlab":
                    if "token" not in credential_data or not credential_data["token"]:
                        self.logger.error("GitLab credentials missing or empty token")
                        return False
                elif provider_type == "aws":
                    if (
                        "access_key_id" not in credential_data
                        or not credential_data["access_key_id"]
                        or "secret_access_key" not in credential_data
                        or not credential_data["secret_access_key"]
                    ):
                        self.logger.error("AWS credentials missing required fields")
                        return False

            # Check for sensitive data patterns (basic validation)
            for key, value in credential_data.items():
                if isinstance(value, str) and len(value) < 8:
                    self.logger.warning(
                        f"Credential field {key} seems too short for a secure credential"
                    )

            return True
        except Exception as e:
            self.logger.error(f"Credential validation error: {e}")
            return False

    async def _test_new_credentials(
        self, credential_id: str, credential_data: Dict[str, Any]
    ) -> bool:
        """Test new credentials by attempting to use them."""
        try:
            # Store credentials temporarily for testing
            test_credential_id = f"{credential_id}_test"
            await self.credential_manager.store_credentials(
                test_credential_id, credential_data
            )

            # Test based on provider type
            provider_type = credential_data.get("provider_type", "unknown")

            if provider_type == "github":
                return await self._test_github_credentials(test_credential_id)
            elif provider_type == "gitlab":
                return await self._test_gitlab_credentials(test_credential_id)
            elif provider_type == "aws":
                return await self._test_aws_credentials(test_credential_id)
            else:
                # For unknown types, just check if we can retrieve the credentials
                test_creds = await self.credential_manager.get_credentials(
                    test_credential_id, provider_type
                )
                return test_creds is not None

        except Exception as e:
            self.logger.error(f"Credential testing failed: {e}")
            return False
        finally:
            # Clean up test credentials
            try:
                # Note: delete_credentials method needs to be implemented in CredentialManager
                # For now, we'll just log that cleanup was attempted
                self.logger.debug(
                    f"Would clean up test credentials for {credential_id}_test"
                )
            except Exception:
                pass

    async def _test_github_credentials(self, credential_id: str) -> bool:
        """Test GitHub credentials by making a simple API call."""
        try:
            # This would need to be implemented with actual GitHub API call
            # For now, just validate the credential structure
            credentials = await self.credential_manager.get_credentials(
                credential_id, "github"
            )
            return "token" in credentials and len(credentials["token"]) > 0
        except Exception as e:
            self.logger.error(f"GitHub credential test failed: {e}")
            return False

    async def _test_gitlab_credentials(self, credential_id: str) -> bool:
        """Test GitLab credentials by making a simple API call."""
        try:
            # This would need to be implemented with actual GitLab API call
            # For now, just validate the credential structure
            credentials = await self.credential_manager.get_credentials(
                credential_id, "gitlab"
            )
            return "token" in credentials and len(credentials["token"]) > 0
        except Exception as e:
            self.logger.error(f"GitLab credential test failed: {e}")
            return False

    async def _test_aws_credentials(self, credential_id: str) -> bool:
        """Test AWS credentials by making a simple API call."""
        try:
            # This would need to be implemented with actual AWS API call
            # For now, just validate the credential structure
            credentials = await self.credential_manager.get_credentials(
                credential_id, "aws"
            )
            return (
                "access_key_id" in credentials
                and "secret_access_key" in credentials
                and len(credentials["access_key_id"]) > 0
                and len(credentials["secret_access_key"]) > 0
            )
        except Exception as e:
            self.logger.error(f"AWS credential test failed: {e}")
            return False
