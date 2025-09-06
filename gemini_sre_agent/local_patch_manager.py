"""
Local Patch Manager for SRE Agent

This module provides a local patch management system that can be used when
GitHub integration is not available or when working in a local development environment.
"""

import json
import logging
import os
from datetime import datetime
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
        logger.info(f"[LOCAL_PATCH] Initialized LocalPatchManager with directory: {self.patch_dir}")

    def create_patch(
        self,
        issue_id: str,
        file_path: str,
        patch_content: str,
        description: str = "",
        severity: str = "medium"
    ) -> str:
        """
        Create a local patch file.

        Args:
            issue_id (str): Unique identifier for the issue
            file_path (str): Target file path for the patch
            patch_content (str): The patch content (code changes)
            description (str): Description of the patch
            severity (str): Severity level of the issue

        Returns:
            str: Path to the created patch file
        """
        timestamp = datetime.now().isoformat()
        # Sanitize issue_id to remove invalid filename characters
        sanitized_issue_id = issue_id.replace('/', '_').replace(':', '_').replace('\\', '_')
        patch_filename = f"{sanitized_issue_id}_{timestamp.replace(':', '-')}.patch"
        patch_file_path = self.patch_dir / patch_filename

        # Create patch metadata
        patch_metadata = {
            "issue_id": issue_id,
            "file_path": file_path,
            "description": description,
            "severity": severity,
            "created_at": timestamp,
            "patch_type": "local"
        }

        # Create the patch file content
        patch_content_formatted = f"""# Local Patch File
# Issue ID: {issue_id}
# File: {file_path}
# Created: {timestamp}
# Severity: {severity}
# Description: {description}

{'-' * 80}
# PATCH CONTENT
{'-' * 80}

{patch_content}

{'-' * 80}
# METADATA
{'-' * 80}

{json.dumps(patch_metadata, indent=2)}
"""

        # Write the patch file
        patch_file_path.write_text(patch_content_formatted, encoding='utf-8')
        
        logger.info(f"[LOCAL_PATCH] Created patch file: {patch_file_path}")
        return str(patch_file_path)

    def list_patches(self) -> List[Dict]:
        """
        List all available patch files.

        Returns:
            List[Dict]: List of patch metadata
        """
        patches = []
        for patch_file in self.patch_dir.glob("*.patch"):
            try:
                content = patch_file.read_text(encoding='utf-8')
                # Extract metadata from the patch file
                if "# METADATA" in content:
                    metadata_section = content.split("# METADATA")[-1].strip()
                    metadata = json.loads(metadata_section)
                    metadata["patch_file"] = str(patch_file)
                    patches.append(metadata)
            except Exception as e:
                logger.warning(f"[LOCAL_PATCH] Failed to read patch file {patch_file}: {e}")
        
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
                return patch_path.read_text(encoding='utf-8')
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
                    logger.info(f"[LOCAL_PATCH] Cleaned up old patch file: {patch_file}")
            except Exception as e:
                logger.warning(f"[LOCAL_PATCH] Failed to clean up patch file {patch_file}: {e}")
        
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
            "patch_directory": str(self.patch_dir)
        }
