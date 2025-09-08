"""
Local Patch Manager for SRE Agent

This module provides a local patch management system that can be used when
GitHub integration is not available or when working in a local development environment.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class LocalPatchManager:
    """
    Manages local patch files when GitHub integration is not available.
    """

    def __init__(self, patch_dir: str = "/tmp/real_patches"):
        """
        Initialize the LocalPatchManager.

        Args:
            patch_dir (str): Directory to store patch files
        """
        self.patch_dir = Path(patch_dir)
        self.patch_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"[LOCAL_PATCH] Initialized LocalPatchManager with directory: {self.patch_dir}"
        )

    def create_patch(
        self,
        issue_id: str,
        file_path: str,
        patch_content: str,
        description: str = "",
        severity: str = "medium",
    ) -> str:
        """
        Create a local patch file in proper Git patch format.

        Args:
            issue_id (str): Unique identifier for the issue
            file_path (str): Target file path for the patch
            patch_content (str): The patch content (code changes)
            description (str): Description of the patch
            severity (str): Severity level of the issue

        Returns:
            str: Path to the created patch file
        """
        timestamp = datetime.now(timezone.utc)
        # Sanitize issue_id to remove invalid filename characters
        sanitized_issue_id = (
            issue_id.replace("/", "_").replace(":", "_").replace("\\", "_")
        )
        patch_filename = (
            f"{sanitized_issue_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.patch"
        )
        patch_file_path = self.patch_dir / patch_filename

        # Generate proper Git patch format
        git_patch = self._generate_git_patch(
            issue_id=issue_id,
            file_path=file_path,
            patch_content=patch_content,
            description=description,
            severity=severity,
            timestamp=timestamp,
        )

        # Write the patch file
        patch_file_path.write_text(git_patch, encoding="utf-8")

        logger.info(f"[LOCAL_PATCH] Created Git patch file: {patch_file_path}")
        return str(patch_file_path)

    def _generate_git_patch(
        self,
        issue_id: str,
        file_path: str,
        patch_content: str,
        description: str,
        severity: str,
        timestamp: datetime,
    ) -> str:
        """
        Generate a proper Git patch format.

        Args:
            issue_id (str): Unique identifier for the issue
            file_path (str): Target file path for the patch
            patch_content (str): The patch content (code changes)
            description (str): Description of the patch
            severity (str): Severity level of the issue
            timestamp (datetime): Timestamp for the patch

        Returns:
            str: Git patch format content
        """
        # Generate commit hash (simplified)
        commit_hash = f"{hash(issue_id + str(timestamp)):016x}"

        # Format timestamp for Git
        git_timestamp = timestamp.strftime("%a %b %d %H:%M:%S %Y %z")

        # Create commit message
        commit_subject = (
            f"Fix: {description[:50]}{'...' if len(description) > 50 else ''}"
        )
        commit_body = f"""Root Cause Analysis:
{description}

Severity: {severity}
Issue ID: {issue_id}

This patch addresses the issue identified by the SRE Agent.
"""

        # Generate the Git patch header
        git_patch = f"""From {commit_hash} Mon Sep 17 00:00:00 2001
From: SRE Agent <sre-agent@example.com>
Date: {git_timestamp}
Subject: [PATCH] {commit_subject}

{commit_body}
---
diff --git a/{file_path} b/{file_path}
index 0000000..0000000 100644
--- a/{file_path}
+++ b/{file_path}
"""

        # Process the patch content to ensure proper Git diff format
        if patch_content.strip():
            # If the patch content doesn't start with @@, assume it's raw code and create a diff
            if not patch_content.strip().startswith("@@"):
                git_patch += self._create_git_diff(patch_content, file_path)
            else:
                # Use the provided patch content as-is
                git_patch += patch_content
        else:
            # Create a minimal diff if no content provided
            git_patch += """@@ -1,0 +1,1 @@
+# Fix for {issue_id}
"""

        return git_patch

    def _create_git_diff(self, code_content: str, file_path: str) -> str:
        """
        Create a Git diff from code content.

        Args:
            code_content (str): The code content to create a diff for
            file_path (str): The target file path

        Returns:
            str: Git diff format
        """
        lines = code_content.strip().split("\n")

        # Create a simple diff that adds the code
        diff_lines = []
        for _i, line in enumerate(lines, 1):
            diff_lines.append(f"+{line}")

        # Add context lines
        context_lines = [
            "@@ -1,0 +1,{} @@".format(len(lines)),
            "# Generated by SRE Agent",
        ]

        return "\n".join(context_lines + diff_lines)

    def list_patches(self) -> List[Dict]:
        """
        List all available patch files.

        Returns:
            List[Dict]: List of patch metadata
        """
        patches = []
        for patch_file in self.patch_dir.glob("*.patch"):
            try:
                content = patch_file.read_text(encoding="utf-8")
                # Extract metadata from the patch file
                if "# METADATA" in content:
                    metadata_section = content.split("# METADATA")[-1].strip()
                    metadata = json.loads(metadata_section)
                    metadata["patch_file"] = str(patch_file)
                    patches.append(metadata)
            except Exception as e:
                logger.warning(
                    f"[LOCAL_PATCH] Failed to read patch file {patch_file}: {e}"
                )

        return sorted(patches, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_patch_content(self, patch_file: str) -> Optional[str]:
        """
        Get the content of a specific patch file.

        Args:
            patch_file (str): Path to the patch file

        Returns:
            Optional[str]: Patch content or None if not found
        """
        try:
            patch_path = Path(patch_file)
            if patch_path.exists():
                return patch_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"[LOCAL_PATCH] Failed to read patch file {patch_file}: {e}")

        return None

    def clean_old_patches(self, max_age_hours: int = 24) -> int:
        """
        Clean up old patch files.

        Args:
            max_age_hours (int): Maximum age of patch files in hours

        Returns:
            int: Number of files cleaned up
        """
        cleaned_count = 0
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)

        for patch_file in self.patch_dir.glob("*.patch"):
            try:
                if patch_file.stat().st_mtime < cutoff_time:
                    patch_file.unlink()
                    cleaned_count += 1
                    logger.info(
                        f"[LOCAL_PATCH] Cleaned up old patch file: {patch_file}"
                    )
            except Exception as e:
                logger.warning(
                    f"[LOCAL_PATCH] Failed to clean up patch file {patch_file}: {e}"
                )

        return cleaned_count

    def get_patch_stats(self) -> Dict:
        """
        Get statistics about patch files.

        Returns:
            Dict: Patch statistics
        """
        patches = self.list_patches()
        total_patches = len(patches)

        severity_counts = {}
        for patch in patches:
            severity = patch.get("severity", "unknown")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        return {
            "total_patches": total_patches,
            "severity_counts": severity_counts,
            "patch_directory": str(self.patch_dir),
        }
