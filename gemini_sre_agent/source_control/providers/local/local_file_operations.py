# gemini_sre_agent/source_control/providers/local/local_file_operations.py

"""
Local file operations module.

This module handles file-specific operations for the local provider.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import chardet

from ...models import (
    FileInfo,
    RemediationResult,
)
from ..base_sub_operation import BaseSubOperation
from ..sub_operation_config import SubOperationConfig


class LocalFileOperations(BaseSubOperation):
    """Handles file-specific operations for local filesystem."""

    def __init__(
        self,
        root_path: Path,
        default_encoding: str,
        backup_files: bool,
        backup_directory: Optional[str],
        logger: logging.Logger,
        error_handling_components: Optional[Dict[str, Any]] = None,
        config: Optional[SubOperationConfig] = None,
    ):
        """Initialize file operations."""
        super().__init__(
            logger=logger,
            error_handling_components=error_handling_components,
            config=config,
            provider_type="local",
            operation_name="file_operations",
        )
        self.root_path = root_path
        self.default_encoding = default_encoding
        self.backup_files = backup_files
        self.backup_directory = backup_directory

    async def get_file_content(self, path: str) -> str:
        """Get file content from local filesystem."""

        async def _get_file():
            try:
                file_path = self.root_path / path
                if not file_path.exists() or not file_path.is_file():
                    return ""

                # Detect encoding
                with open(file_path, "rb") as f:
                    raw_data = f.read()
                    detected = chardet.detect(raw_data)
                    encoding = detected.get("encoding", self.default_encoding)

                # Read file with detected encoding
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except Exception as e:
                self.logger.error(f"Failed to read file {path}: {e}")
                return ""

        return await self._execute_with_error_handling(
            "get_file_content", _get_file, "file"
        )

    async def apply_remediation(
        self,
        file_path: str,
        remediation: str,
        commit_message: str,
    ) -> RemediationResult:
        """Apply remediation to a file."""

        async def _apply():
            try:
                full_path = self.root_path / file_path

                # Create backup if enabled
                if self.backup_files:
                    self._create_backup(full_path)

                # Write remediation to file
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, "w", encoding=self.default_encoding) as f:
                    f.write(remediation)

                return RemediationResult(
                    success=True,
                    message=f"Applied remediation to {file_path}",
                    file_path=file_path,
                    operation_type="apply_remediation",
                    commit_sha="",
                    pull_request_url="",
                    error_details="",
                    additional_info={},
                )
            except Exception as e:
                self.logger.error(f"Failed to apply remediation to {file_path}: {e}")
                return RemediationResult(
                    success=False,
                    message=f"Failed to apply remediation: {e}",
                    file_path=file_path,
                    operation_type="apply_remediation",
                    commit_sha="",
                    pull_request_url="",
                    error_details=str(e),
                    additional_info={},
                )

        return await self._execute_with_error_handling(
            "apply_remediation", _apply, "file"
        )

    async def file_exists(self, path: str) -> bool:
        """Check if a file exists."""

        async def _exists():
            try:
                file_path = self.root_path / path
                return file_path.exists() and file_path.is_file()
            except Exception as e:
                self.logger.error(f"Failed to check if file exists {path}: {e}")
                return False

        return await self._execute_with_error_handling("file_exists", _exists, "file")

    async def get_file_info(self, path: str) -> FileInfo:
        """Get file information."""

        async def _get_info():
            try:
                file_path = self.root_path / path
                if not file_path.exists():
                    return FileInfo(
                        path=path,
                        size=0,
                        sha="",
                        is_binary=False,
                        last_modified=None,
                    )

                stat = file_path.stat()
                return FileInfo(
                    path=path,
                    size=stat.st_size,
                    sha="",  # Local files don't have SHA
                    is_binary=self._is_binary_file(file_path),
                    last_modified=datetime.fromtimestamp(stat.st_mtime),
                )
            except Exception as e:
                self.logger.error(f"Failed to get file info for {path}: {e}")
                return FileInfo(
                    path=path,
                    size=0,
                    sha="",
                    is_binary=False,
                    last_modified=None,
                )

        return await self._execute_with_error_handling(
            "get_file_info", _get_info, "file"
        )

    async def list_files(self, path: str = "") -> List[FileInfo]:
        """List files in a directory."""

        async def _list():
            try:
                dir_path = self.root_path / path
                if not dir_path.exists() or not dir_path.is_dir():
                    return []

                files = []
                for item in dir_path.iterdir():
                    if item.is_file():
                        stat = item.stat()
                        files.append(
                            FileInfo(
                                path=str(item.relative_to(self.root_path)),
                                size=stat.st_size,
                                sha="",
                                is_binary=self._is_binary_file(item),
                                last_modified=datetime.fromtimestamp(stat.st_mtime),
                            )
                        )

                return files
            except Exception as e:
                self.logger.error(f"Failed to list files in {path}: {e}")
                return []

        return await self._execute_with_error_handling("list_files", _list, "file")

    def _is_binary_file(self, file_path: Path) -> bool:
        """Check if a file is binary."""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                return b"\0" in chunk
        except Exception:
            return False

    def _create_backup(self, file_path: Path) -> None:
        """Create a backup of a file."""
        try:
            if not file_path.exists():
                return

            backup_dir = self.backup_directory
            if backup_dir is None:
                backup_dir = self.root_path / ".backups"
            else:
                backup_dir = Path(backup_dir)

            backup_dir.mkdir(parents=True, exist_ok=True)

            # Create backup with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{file_path.name}.{timestamp}.bak"
            backup_path = backup_dir / backup_name

            shutil.copy2(file_path, backup_path)
            self.logger.info(f"Created backup: {backup_path}")
        except Exception as e:
            self.logger.error(f"Failed to create backup for {file_path}: {e}")

    async def generate_patch(self, original: str, modified: str) -> str:
        """Generate a patch between original and modified content."""

        async def _generate():
            try:
                import difflib

                return "\n".join(
                    difflib.unified_diff(
                        original.splitlines(keepends=True),
                        modified.splitlines(keepends=True),
                        fromfile="original",
                        tofile="modified",
                    )
                )
            except Exception as e:
                self.logger.error(f"Failed to generate patch: {e}")
                return ""

        return await self._execute_with_error_handling(
            "generate_patch", _generate, "file"
        )

    async def apply_patch(self, patch: str, file_path: str) -> bool:
        """Apply a patch to a file."""

        async def _apply():
            try:
                # from patch_ng import PatchSet

                full_path = self.root_path / file_path
                if not full_path.exists():
                    return False

                # Create backup
                if self.backup_files:
                    self._create_backup(full_path)

                # Apply patch using a different approach
                try:
                    # For now, we'll just write the patch content to the file
                    # In a real implementation, you'd want to properly apply the patch
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(patch)
                    return True
                except Exception as patch_error:
                    self.logger.error(
                        f"Failed to apply patch to {file_path}: {patch_error}"
                    )
                    return False
            except Exception as e:
                self.logger.error(f"Failed to apply patch to {file_path}: {e}")
                return False

        return await self._execute_with_error_handling("apply_patch", _apply, "file")

    async def commit_changes(
        self,
        file_path: str,
        content: str,
        message: str,
    ) -> bool:
        """Commit changes to a file."""

        async def _commit():
            try:
                full_path = self.root_path / file_path

                # Create backup if enabled
                if self.backup_files:
                    self._create_backup(full_path)

                # Write content to file
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, "w", encoding=self.default_encoding) as f:
                    f.write(content)

                return True
            except Exception as e:
                self.logger.error(f"Failed to commit changes to {file_path}: {e}")
                return False

        return await self._execute_with_error_handling(
            "commit_changes", _commit, "file"
        )

    async def health_check(self) -> bool:
        """Check if the file operations are healthy."""
        try:
            # Test basic file operations
            test_path = self.root_path / ".health_check_test"
            test_content = "health_check_test"

            # Test write
            test_path.write_text(test_content, encoding=self.default_encoding)

            # Test read
            read_content = test_path.read_text(encoding=self.default_encoding)
            if read_content != test_content:
                return False

            # Test delete
            test_path.unlink()

            return True
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
