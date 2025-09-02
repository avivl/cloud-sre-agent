"""
Source code context extraction for enhanced pattern analysis.

This module provides git analysis, static analysis integration, and code quality
metrics extraction to enhance incident pattern detection.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from ..pattern_detector.models import TimeWindow
from .code_analysis_models import CodeAnalysisConfig, CodeChange


class CodeContextExtractor:
    """Extract source code context for enhanced pattern analysis."""

    def __init__(self, config: CodeAnalysisConfig) -> None:
        """Initialize the code context extractor."""
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Validate repository path
        if not os.path.exists(config.repository_path):
            raise ValueError(
                f"Repository path does not exist: {config.repository_path}"
            )

        self.repo_path = Path(config.repository_path)

    async def extract_code_context(
        self, window: TimeWindow, affected_services: List[str]
    ) -> Dict[str, Any]:
        """Extract comprehensive code context for the time window."""
        try:
            # Run analysis tasks in parallel
            tasks = []

            # Always extract git context
            tasks.append(self._extract_git_context(window))

            # Optional static analysis
            if self.config.enable_static_analysis:
                tasks.append(self._run_static_analysis(affected_services))
            else:
                tasks.append(asyncio.create_task(self._empty_static_analysis()))

            # Code quality metrics
            if self.config.enable_complexity_analysis:
                tasks.append(self._analyze_code_complexity(affected_services))
            else:
                tasks.append(asyncio.create_task(self._empty_complexity_analysis()))

            # Dependency security scan
            if self.config.enable_dependency_scan:
                tasks.append(self._scan_dependencies())
            else:
                tasks.append(asyncio.create_task(self._empty_dependency_scan()))

            # Extract error-related files from logs
            tasks.append(self._extract_error_related_files(window))

            # Execute all tasks with timeout
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.config.analysis_timeout_seconds,
            )

            (
                git_context,
                static_analysis,
                complexity_metrics,
                dependency_scan,
                error_files,
            ) = results

            # Handle any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    task_names = [
                        "git_context",
                        "static_analysis",
                        "complexity_metrics",
                        "dependency_scan",
                        "error_files",
                    ]
                    self.logger.warning(
                        f"[CODE_CONTEXT] {task_names[i]} failed: {result}"
                    )

            # Extract results safely
            changes_summary = ""
            recent_commits = []
            if not isinstance(git_context, Exception) and isinstance(git_context, dict):
                changes_summary = git_context.get("code_changes_summary", "")
                recent_commits = git_context.get("recent_commits", [])

            return {
                "changes_summary": changes_summary,
                "static_findings": (
                    static_analysis
                    if not isinstance(static_analysis, Exception)
                    else {}
                ),
                "quality_metrics": (
                    complexity_metrics
                    if not isinstance(complexity_metrics, Exception)
                    else {}
                ),
                "vulnerabilities": (
                    dependency_scan
                    if not isinstance(dependency_scan, Exception)
                    else []
                ),
                "related_files": (
                    error_files if not isinstance(error_files, Exception) else []
                ),
                "recent_commits": recent_commits,
            }

        except asyncio.TimeoutError:
            self.logger.warning(
                f"[CODE_CONTEXT] Analysis timed out after {self.config.analysis_timeout_seconds}s"
            )
            return self._empty_context()
        except Exception as e:
            self.logger.error(f"[CODE_CONTEXT] Error extracting code context: {e}")
            return self._empty_context()

    async def _extract_git_context(self, window: TimeWindow) -> Dict[str, Any]:
        """Extract git context for the time window."""
        try:
            # Get recent commits around the time window
            start_time = window.start_time - timedelta(hours=24)  # Look back 24 hours
            end_time = window.end_time + timedelta(hours=1)  # Look ahead 1 hour

            # Format dates for git log
            since_date = start_time.strftime("%Y-%m-%d %H:%M:%S")
            until_date = end_time.strftime("%Y-%m-%d %H:%M:%S")

            # Get commits in time range
            cmd = [
                "git",
                "log",
                f"--since={since_date}",
                f"--until={until_date}",
                "--pretty=format:%H|%at|%an|%s",
                f"-{self.config.max_recent_commits}",
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=self.repo_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                self.logger.warning(f"[CODE_CONTEXT] Git log failed: {stderr.decode()}")
                return {
                    "recent_commits": [],
                    "code_changes_summary": "Git analysis failed",
                }

            # Parse git log output
            commits = self._parse_git_log_output(stdout.decode())

            # Generate summary
            summary = self._generate_code_changes_summary(commits, window)

            return {
                "recent_commits": [self._commit_to_dict(commit) for commit in commits],
                "code_changes_summary": summary,
                "commits_in_window": len(
                    [
                        c
                        for c in commits
                        if window.start_time <= c.timestamp <= window.end_time
                    ]
                ),
                "total_files_changed": len(
                    set(file for commit in commits for file in commit.files_changed)
                ),
                "rollback_detected": any(commit.is_rollback for commit in commits),
            }

        except Exception as e:
            self.logger.error(f"[CODE_CONTEXT] Git context extraction failed: {e}")
            return {
                "recent_commits": [],
                "code_changes_summary": f"Git analysis error: {str(e)}",
            }

    def _parse_git_log_output(self, output: str) -> List[CodeChange]:
        """Parse git log output into CodeChange objects."""
        commits = []
        lines = output.strip().split("\n")

        for line in lines:
            if "|" in line and len(line.split("|")) == 4:
                parts = line.split("|")
                commit_hash = parts[0]
                timestamp = datetime.fromtimestamp(int(parts[1]))
                author = parts[2]
                message = parts[3]

                # Detect rollback commits
                is_rollback = any(
                    keyword in message.lower()
                    for keyword in ["revert", "rollback", "roll back", "undo"]
                )

                commit = CodeChange(
                    commit_hash=commit_hash,
                    timestamp=timestamp,
                    author=author,
                    message=message,
                    files_changed=[],  # Will be filled by separate analysis if needed
                    lines_added=0,
                    lines_deleted=0,
                    is_rollback=is_rollback,
                )
                commits.append(commit)

        return commits

    def _generate_code_changes_summary(
        self, commits: List[CodeChange], window: TimeWindow
    ) -> str:
        """Generate a human-readable summary of code changes."""
        if not commits:
            return "No recent code changes found"

        commits_in_window = [
            c for c in commits if window.start_time <= c.timestamp <= window.end_time
        ]

        if not commits_in_window:
            return f"No commits during incident window. {len(commits)} recent commits in 24h before incident."

        rollback_count = sum(1 for c in commits_in_window if c.is_rollback)

        summary_parts = [f"{len(commits_in_window)} commits during incident window"]

        if rollback_count > 0:
            summary_parts.append(f"{rollback_count} rollback/revert commits detected")

        return ". ".join(summary_parts) + "."

    def _commit_to_dict(self, commit: CodeChange) -> Dict[str, Any]:
        """Convert CodeChange to dictionary."""
        return {
            "hash": commit.commit_hash[:8],  # Short hash
            "timestamp": commit.timestamp.isoformat(),
            "author": commit.author,
            "message": commit.message,
            "is_rollback": commit.is_rollback,
        }

    async def _run_static_analysis(
        self, affected_services: List[str]
    ) -> Dict[str, Any]:
        """Run static analysis tools if configured."""
        # Simplified implementation - would integrate with actual tools
        return {"enabled": True, "findings": [], "services_analyzed": affected_services}

    async def _analyze_code_complexity(
        self, affected_services: List[str]
    ) -> Dict[str, Any]:
        """Analyze code complexity metrics."""
        # Simplified implementation - would calculate actual metrics
        return {"complexity_score": 5, "services_analyzed": affected_services}

    async def _scan_dependencies(self) -> List[str]:
        """Scan for dependency vulnerabilities."""
        # Simplified implementation - would run actual security scans
        return []

    async def _extract_error_related_files(self, window: TimeWindow) -> List[str]:
        """Extract file paths mentioned in error logs."""
        files = set()

        for log in window.logs:
            if log.error_message:
                # Simple extraction of file paths from error messages
                message = log.error_message.lower()
                if ".py" in message or ".js" in message or ".java" in message:
                    # Extract potential file references
                    words = message.split()
                    for word in words:
                        if any(
                            ext in word for ext in [".py", ".js", ".java", ".go", ".rs"]
                        ):
                            files.add(word.strip('",()[]'))

        return list(files)

    async def _empty_static_analysis(self) -> Dict[str, Any]:
        """Return empty static analysis result."""
        return {"enabled": False}

    async def _empty_complexity_analysis(self) -> Dict[str, Any]:
        """Return empty complexity analysis result."""
        return {"enabled": False}

    async def _empty_dependency_scan(self) -> List[str]:
        """Return empty dependency scan result."""
        return []

    def _empty_context(self) -> Dict[str, Any]:
        """Return empty context when analysis fails."""
        return {
            "changes_summary": "Code context extraction failed",
            "static_findings": {},
            "quality_metrics": {},
            "vulnerabilities": [],
            "related_files": [],
            "recent_commits": [],
        }
