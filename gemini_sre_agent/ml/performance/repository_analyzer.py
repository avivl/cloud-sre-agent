# gemini_sre_agent/ml/performance/repository_analyzer.py

"""
Performance-optimized repository analyzer.

This module provides fast repository analysis with intelligent caching,
async processing, and incremental updates to minimize analysis time.
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..caching import RepositoryContextCache
from ..prompt_context_models import RepositoryContext


class PerformanceRepositoryAnalyzer:
    """
    High-performance repository analyzer with caching and async processing.

    Features:
    - Intelligent caching of analysis results
    - Async file system operations
    - Incremental analysis updates
    - Parallel processing where possible
    - Configurable analysis depth
    """

    def __init__(self, cache: RepositoryContextCache, repo_path: str = "."):
        """
        Initialize the performance repository analyzer.

        Args:
            cache: Repository context cache instance
            repo_path: Path to repository to analyze
        """
        self.cache = cache
        self.repo_path = Path(repo_path).resolve()
        self.logger = logging.getLogger(__name__)

        # Analysis depth configurations
        self.analysis_configs = {
            "basic": {
                "max_files": 100,
                "max_depth": 2,
                "include_hidden": False,
                "parallel_workers": 2,
            },
            "standard": {
                "max_files": 500,
                "max_depth": 3,
                "include_hidden": False,
                "parallel_workers": 4,
            },
            "comprehensive": {
                "max_files": 2000,
                "max_depth": 5,
                "include_hidden": True,
                "parallel_workers": 8,
            },
        }

    async def analyze_repository(
        self, analysis_depth: str = "standard", force_refresh: bool = False
    ) -> RepositoryContext:
        """
        Analyze repository with performance optimizations.

        Args:
            analysis_depth: Level of analysis (basic, standard, comprehensive)
            force_refresh: Force refresh even if cached data exists

        Returns:
            Repository context with analysis results
        """
        start_time = time.time()

        try:
            # Check cache first (unless force refresh)
            if not force_refresh:
                cached_context = await self.cache.get_repository_context(
                    str(self.repo_path), analysis_depth
                )
                if cached_context:
                    self.logger.info(
                        f"Using cached repository context for {self.repo_path}"
                    )
                    return cached_context

            # Perform analysis
            self.logger.info(
                f"Starting {analysis_depth} repository analysis for {self.repo_path}"
            )

            config = self.analysis_configs[analysis_depth]

            # Parallel analysis tasks
            tasks = [
                self._analyze_file_structure(config),
                self._analyze_technology_stack(config),
                self._analyze_coding_standards(config),
                self._analyze_error_patterns(config),
                self._analyze_testing_patterns(config),
                self._analyze_dependency_structure(config),
            ]

            # Execute tasks in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and handle exceptions
            def safe_result(result, default):
                if isinstance(result, Exception):
                    self.logger.warning(f"Analysis task failed: {result}")
                    return default
                return result

            file_structure = safe_result(results[0], {})
            tech_stack = safe_result(results[1], {})
            coding_standards = safe_result(results[2], {})
            error_patterns = safe_result(results[3], [])
            testing_patterns = safe_result(results[4], [])
            dependencies = safe_result(results[5], {})

            # Type cast to ensure compatibility
            if not isinstance(file_structure, dict):
                file_structure = {}
            if not isinstance(tech_stack, dict):
                tech_stack = {}
            if not isinstance(coding_standards, dict):
                coding_standards = {}
            if not isinstance(error_patterns, list):
                error_patterns = []
            if not isinstance(testing_patterns, list):
                testing_patterns = []
            if not isinstance(dependencies, dict):
                dependencies = {}

            # Create repository context
            context = RepositoryContext(
                architecture_type=self._determine_architecture_type(file_structure),
                technology_stack=tech_stack,
                coding_standards=coding_standards,
                error_handling_patterns=error_patterns,
                testing_patterns=testing_patterns,
                dependency_structure=dependencies,
                recent_changes=await self._get_recent_changes(),
                historical_fixes=await self._get_historical_fixes(),
                code_quality_metrics=await self._calculate_quality_metrics(
                    file_structure
                ),
            )

            # Cache the result
            await self.cache.set_repository_context(
                str(self.repo_path), context, analysis_depth
            )

            analysis_time = time.time() - start_time
            self.logger.info(f"Repository analysis completed in {analysis_time:.2f}s")

            return context

        except Exception as e:
            self.logger.error(f"Repository analysis failed: {e}")
            # Return minimal context on failure
            return RepositoryContext(
                architecture_type="unknown",
                technology_stack={},
                coding_standards={},
                error_handling_patterns=[],
                testing_patterns=[],
                dependency_structure={},
                recent_changes=[],
                historical_fixes=[],
                code_quality_metrics={},
            )

    async def _analyze_file_structure(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze repository file structure asynchronously."""
        try:
            structure = {
                "total_files": 0,
                "total_directories": 0,
                "file_types": {},
                "directory_structure": {},
                "large_files": [],
                "recent_files": [],
            }

            # Use async file operations
            async for file_info in self._scan_files_async(config):
                structure["total_files"] += 1

                # Count file types
                ext = file_info["extension"]
                structure["file_types"][ext] = structure["file_types"].get(ext, 0) + 1

                # Track large files
                if file_info["size"] > 1024 * 1024:  # > 1MB
                    structure["large_files"].append(file_info)

                # Track recent files
                if file_info["modified"] > time.time() - 86400:  # Last 24h
                    structure["recent_files"].append(file_info)

                if structure["total_files"] >= config["max_files"]:
                    break

            return structure

        except Exception as e:
            self.logger.error(f"File structure analysis failed: {e}")
            return {}

    async def _analyze_technology_stack(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze technology stack from configuration files."""
        try:
            tech_stack = {}

            # Common configuration files to check
            config_files = [
                "package.json",
                "requirements.txt",
                "pyproject.toml",
                "Cargo.toml",
                "go.mod",
                "pom.xml",
                "build.gradle",
                "Gemfile",
                "composer.json",
            ]

            for config_file in config_files:
                file_path = self.repo_path / config_file
                if file_path.exists():
                    tech_stack.update(await self._parse_config_file(file_path))

            # Detect framework from file structure
            framework = await self._detect_framework()
            if framework:
                tech_stack["framework"] = framework

            return tech_stack

        except Exception as e:
            self.logger.error(f"Technology stack analysis failed: {e}")
            return {}

    async def _analyze_coding_standards(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze coding standards from configuration files."""
        try:
            standards = {}

            # Check for common linting and formatting tools
            linting_tools = [
                ".eslintrc",
                ".pylintrc",
                ".flake8",
                "pyproject.toml",
                "rustfmt.toml",
                ".clang-format",
                ".editorconfig",
            ]

            for tool in linting_tools:
                tool_path = self.repo_path / tool
                if tool_path.exists():
                    standards.update(await self._parse_standards_file(tool_path))

            return standards

        except Exception as e:
            self.logger.error(f"Coding standards analysis failed: {e}")
            return {}

    async def _analyze_error_patterns(self, config: Dict[str, Any]) -> List[str]:
        """Analyze error handling patterns in the codebase."""
        try:
            patterns = []

            # Common error handling patterns
            error_patterns = [
                "try:",
                "except:",
                "catch(",
                "throw",
                "raise",
                "error",
                "Error",
                "Exception",
                "fail",
                "Fail",
            ]

            # Scan for patterns in source files
            source_files = await self._find_source_files(config)

            for file_path in source_files[: config["max_files"] // 2]:
                try:
                    content = await self._read_file_async(file_path)
                    for pattern in error_patterns:
                        if pattern in content:
                            patterns.append(f"{pattern} in {file_path.name}")
                except Exception:
                    continue

            return list(set(patterns))  # Remove duplicates

        except Exception as e:
            self.logger.error(f"Error pattern analysis failed: {e}")
            return []

    async def _analyze_testing_patterns(self, config: Dict[str, Any]) -> List[str]:
        """Analyze testing patterns in the codebase."""
        try:
            patterns = []

            # Common testing patterns
            test_patterns = [
                "test_",
                "Test",
                "spec",
                "Spec",
                "describe",
                "it(",
                "assert",
                "expect",
                "should",
                "pytest",
                "unittest",
            ]

            # Find test files
            test_files = await self._find_test_files(config)

            for file_path in test_files[: config["max_files"] // 4]:
                try:
                    content = await self._read_file_async(file_path)
                    for pattern in test_patterns:
                        if pattern in content:
                            patterns.append(f"{pattern} in {file_path.name}")
                except Exception:
                    continue

            return list(set(patterns))

        except Exception as e:
            self.logger.error(f"Testing pattern analysis failed: {e}")
            return []

    async def _analyze_dependency_structure(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze dependency structure of the project."""
        try:
            dependencies = {}

            # Check for dependency files
            dep_files = [
                "package.json",
                "requirements.txt",
                "pyproject.toml",
                "Cargo.toml",
                "go.mod",
                "pom.xml",
            ]

            for dep_file in dep_files:
                file_path = self.repo_path / dep_file
                if file_path.exists():
                    deps = await self._parse_dependencies_file(file_path)
                    dependencies.update(deps)

            return dependencies

        except Exception as e:
            self.logger.error(f"Dependency analysis failed: {e}")
            return {}

    async def _scan_files_async(self, config: Dict[str, Any]):
        """Async file scanner with configurable depth and limits."""
        try:
            for root, dirs, files in os.walk(self.repo_path, topdown=True):
                # Limit depth
                depth = root.count(os.sep) - self.repo_path.parts.__len__()
                if depth > config["max_depth"]:
                    dirs.clear()
                    continue

                # Filter hidden directories
                if not config["include_hidden"]:
                    dirs[:] = [d for d in dirs if not d.startswith(".")]

                for file in files:
                    if not config["include_hidden"] and file.startswith("."):
                        continue

                    file_path = Path(root) / file
                    try:
                        stat = file_path.stat()
                        yield {
                            "path": str(file_path.relative_to(self.repo_path)),
                            "name": file,
                            "extension": file_path.suffix,
                            "size": stat.st_size,
                            "modified": stat.st_mtime,
                            "is_file": True,
                        }
                    except Exception:
                        continue

        except Exception as e:
            self.logger.error(f"File scanning failed: {e}")

    async def _find_source_files(self, config: Dict[str, Any]) -> List[Path]:
        """Find source code files in the repository."""
        source_extensions = {
            ".py",
            ".js",
            ".ts",
            ".java",
            ".cpp",
            ".c",
            ".go",
            ".rs",
            ".php",
        }
        source_files = []

        async for file_info in self._scan_files_async(config):
            if file_info["extension"] in source_extensions:
                source_files.append(self.repo_path / file_info["path"])

        return source_files

    async def _find_test_files(self, config: Dict[str, Any]) -> List[Path]:
        """Find test files in the repository."""
        test_patterns = ["test", "spec", "Test", "Spec"]
        test_files = []

        async for file_info in self._scan_files_async(config):
            if any(pattern in file_info["name"] for pattern in test_patterns):
                test_files.append(self.repo_path / file_info["path"])

        return test_files

    async def _read_file_async(self, file_path: Path) -> str:
        """Read file content asynchronously."""
        try:
            # Use asyncio to read file in thread pool
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(None, file_path.read_text, "utf-8")
            return content
        except Exception as e:
            self.logger.debug(f"Failed to read {file_path}: {e}")
            return ""

    def _determine_architecture_type(self, file_structure: Dict[str, Any]) -> str:
        """Determine architecture type from file structure."""
        if not file_structure:
            return "unknown"

        # Simple heuristics for architecture detection
        if "docker-compose.yml" in str(file_structure):
            return "microservices"
        elif "package.json" in str(file_structure) and "src" in str(file_structure):
            return "frontend"
        elif "requirements.txt" in str(file_structure) or "pyproject.toml" in str(
            file_structure
        ):
            return "python_backend"
        else:
            return "monolith"

    async def _detect_framework(self) -> Optional[str]:
        """Detect framework from configuration files."""
        framework_indicators = {
            "django": ["manage.py", "settings.py"],
            "flask": ["app.py", "flask"],
            "fastapi": ["main.py", "fastapi"],
            "react": ["package.json", "react"],
            "vue": ["package.json", "vue"],
            "angular": ["angular.json", "package.json"],
            "spring": ["pom.xml", "build.gradle"],
            "express": ["package.json", "express"],
        }

        for framework, indicators in framework_indicators.items():
            if all((self.repo_path / indicator).exists() for indicator in indicators):
                return framework

        return None

    async def _parse_config_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse configuration file to extract technology information."""
        try:
            content = await self._read_file_async(file_path)

            if file_path.name == "package.json":
                import json

                data = json.loads(content)
                return {
                    "node_version": data.get("engines", {}).get("node"),
                    "package_manager": (
                        "npm" if "package-lock.json" in str(self.repo_path) else "yarn"
                    ),
                }
            elif file_path.name == "requirements.txt":
                return {"python_packages": content.splitlines()}
            elif file_path.name == "pyproject.toml":
                return {"python_tool": "poetry"}

            return {}

        except Exception as e:
            self.logger.debug(f"Failed to parse config file {file_path}: {e}")
            return {}

    async def _parse_standards_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse standards configuration file."""
        try:
            await self._read_file_async(file_path)

            if file_path.name == ".eslintrc":
                return {"linting": "eslint"}
            elif file_path.name == ".pylintrc":
                return {"linting": "pylint"}
            elif file_path.name == ".flake8":
                return {"linting": "flake8"}

            return {}

        except Exception as e:
            self.logger.debug(f"Failed to parse standards file {file_path}: {e}")
            return {}

    async def _parse_dependencies_file(self, file_path: Path) -> Dict[str, Any]:
        """Parse dependencies file."""
        try:
            content = await self._read_file_async(file_path)

            if file_path.name == "package.json":
                import json

                data = json.loads(content)
                return {
                    "dependencies": list(data.get("dependencies", {}).keys()),
                    "dev_dependencies": list(data.get("devDependencies", {}).keys()),
                }
            elif file_path.name == "requirements.txt":
                return {"python_dependencies": content.splitlines()}

            return {}

        except Exception as e:
            self.logger.debug(f"Failed to parse dependencies file {file_path}: {e}")
            return {}

    async def _get_recent_changes(self) -> List[Dict[str, Any]]:
        """Get recent changes (placeholder for git integration)."""
        # This would integrate with git to get recent commits
        return []

    async def _get_historical_fixes(self) -> List[Dict[str, Any]]:
        """Get historical fixes (placeholder for git integration)."""
        # This would analyze git history for fix patterns
        return []

    async def _calculate_quality_metrics(
        self, file_structure: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate code quality metrics."""
        if not file_structure:
            return {}

        total_files = file_structure.get("total_files", 0)
        large_files = len(file_structure.get("large_files", []))
        recent_files = len(file_structure.get("recent_files", []))

        return {
            "total_files": total_files,
            "large_files_count": large_files,
            "recent_files_count": recent_files,
            "activity_score": min(recent_files / max(total_files, 1) * 100, 100),
        }
