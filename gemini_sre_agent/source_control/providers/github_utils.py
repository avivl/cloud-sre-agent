# gemini_sre_agent/source_control/providers/github_utils.py

"""
GitHub-specific utility functions for source control operations.

This module contains utility functions specific to GitHub operations
that help with common tasks and data transformations.
"""

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse


def parse_github_url(url: str) -> Tuple[str, str]:
    """
    Parse a GitHub URL to extract owner and repository name.

    Args:
        url: GitHub repository URL (e.g., 'owner/repo' or 'https://github.com/owner/repo')

    Returns:
        Tuple of (owner, repo_name)

    Raises:
        ValueError: If URL format is invalid
    """
    # Handle different URL formats
    if url.startswith(("http://", "https://")):
        # Full URL format
        parsed = urlparse(url)
        if "github.com" not in parsed.netloc:
            raise ValueError(f"Not a GitHub URL: {url}")

        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2:
            raise ValueError(f"Invalid GitHub URL format: {url}")

        owner, repo_name = path_parts[0], path_parts[1]
    else:
        # Owner/repo format
        if "/" not in url:
            raise ValueError(f"Invalid GitHub repository format: {url}")

        parts = url.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid GitHub repository format: {url}")

        owner, repo_name = parts[0], parts[1]

    # Validate owner and repo names
    if not owner or not repo_name:
        raise ValueError(f"Invalid GitHub repository format: {url}")

    # GitHub allows alphanumeric, hyphens, and underscores
    if not re.match(r"^[a-zA-Z0-9_-]+$", owner):
        raise ValueError(f"Invalid owner name: {owner}")

    if not re.match(r"^[a-zA-Z0-9_.-]+$", repo_name):
        raise ValueError(f"Invalid repository name: {repo_name}")

    return owner, repo_name


def sanitize_branch_name(name: str) -> str:
    """
    Sanitize a branch name to be valid for GitHub.

    Args:
        name: Branch name to sanitize

    Returns:
        Sanitized branch name
    """
    # Remove invalid characters
    sanitized = re.sub(r"[^a-zA-Z0-9._/-]", "-", name)

    # Remove consecutive dots, slashes, or hyphens
    sanitized = re.sub(r"[./-]{2,}", "-", sanitized)

    # Remove leading/trailing dots, slashes, or hyphens
    sanitized = sanitized.strip(".-/")

    # Ensure it doesn't start with a dot
    if sanitized.startswith("."):
        sanitized = "branch-" + sanitized

    # Ensure it's not empty
    if not sanitized:
        sanitized = "branch"

    # GitHub has a 255 character limit
    if len(sanitized) > 255:
        sanitized = sanitized[:255]

    return sanitized


def sanitize_commit_message(message: str) -> str:
    """
    Sanitize a commit message to be valid for GitHub.

    Args:
        message: Commit message to sanitize

    Returns:
        Sanitized commit message
    """
    # Remove control characters except newlines and tabs
    sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", message)

    # Ensure it's not empty
    if not sanitized.strip():
        sanitized = "SRE Fix: Automated remediation"

    # GitHub has a practical limit of 72 characters for the first line
    lines = sanitized.split("\n")
    if len(lines[0]) > 72:
        lines[0] = lines[0][:69] + "..."
        sanitized = "\n".join(lines)

    return sanitized


def format_pull_request_title(title: str, issue_id: Optional[str] = None) -> str:
    """
    Format a pull request title with optional issue ID.

    Args:
        title: Base title
        issue_id: Optional issue ID to include

    Returns:
        Formatted title
    """
    if issue_id:
        return f"[{issue_id}] {title}"
    return title


def format_pull_request_body(
    description: str,
    issue_id: Optional[str] = None,
    additional_info: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Format a pull request body with structured information.

    Args:
        description: Base description
        issue_id: Optional issue ID
        additional_info: Optional additional information

    Returns:
        Formatted body
    """
    body_parts = []

    if issue_id:
        body_parts.append(f"**Issue ID:** {issue_id}")
        body_parts.append("")

    body_parts.append("**Description:**")
    body_parts.append(description)

    if additional_info:
        body_parts.append("")
        body_parts.append("**Additional Information:**")
        for key, value in additional_info.items():
            body_parts.append(f"- **{key}:** {value}")

    body_parts.append("")
    body_parts.append("---")
    body_parts.append("*This PR was created automatically by the SRE Agent*")

    return "\n".join(body_parts)


def parse_github_error(error_message: str) -> Dict[str, Any]:
    """
    Parse GitHub error message to extract useful information.

    Args:
        error_message: Error message from GitHub API

    Returns:
        Dictionary with parsed error information
    """
    error_info = {
        "message": error_message,
        "type": "unknown",
        "retryable": False,
        "status_code": None,
    }

    # Check for rate limiting
    if "rate limit exceeded" in error_message.lower():
        error_info["type"] = "rate_limit"
        error_info["retryable"] = True

    # Check for authentication errors
    elif (
        "unauthorized" in error_message.lower() or "forbidden" in error_message.lower()
    ):
        error_info["type"] = "authentication"
        error_info["retryable"] = False

    # Check for not found errors
    elif "not found" in error_message.lower():
        error_info["type"] = "not_found"
        error_info["retryable"] = False

    # Check for validation errors
    elif "validation failed" in error_message.lower():
        error_info["type"] = "validation"
        error_info["retryable"] = False

    # Check for server errors
    elif (
        "server error" in error_message.lower()
        or "internal error" in error_message.lower()
    ):
        error_info["type"] = "server_error"
        error_info["retryable"] = True

    return error_info


def extract_github_links(text: str) -> List[Dict[str, str]]:
    """
    Extract GitHub links from text.

    Args:
        text: Text to search for GitHub links

    Returns:
        List of dictionaries with link information
    """
    # Pattern to match GitHub URLs
    pattern = r"https://github\.com/([^/\s]+)/([^/\s]+)(?:/(?:issues|pulls|commit|tree|blob)/([^\s]+))?"

    links = []
    for match in re.finditer(pattern, text):
        owner = match.group(1)
        repo = match.group(2)
        path = match.group(3) or ""

        links.append(
            {
                "owner": owner,
                "repo": repo,
                "path": path,
                "url": match.group(0),
                "type": (
                    "issue"
                    if "issues" in path
                    else (
                        "pull"
                        if "pulls" in path
                        else "commit" if "commit" in path else "repo"
                    )
                ),
            }
        )

    return links


def validate_github_webhook_signature(
    payload: str, signature: str, secret: str
) -> bool:
    """
    Validate GitHub webhook signature.

    Args:
        payload: Webhook payload
        signature: Signature header value
        secret: Webhook secret

    Returns:
        True if signature is valid
    """
    import hashlib
    import hmac

    if not signature.startswith("sha256="):
        return False

    expected_signature = hmac.new(
        secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected_signature}", signature)


def get_github_emoji_for_status(status: str) -> str:
    """
    Get appropriate emoji for GitHub status.

    Args:
        status: Status string

    Returns:
        Emoji string
    """
    status_emojis = {
        "success": "✅",
        "failure": "❌",
        "error": "💥",
        "pending": "⏳",
        "cancelled": "🚫",
        "skipped": "⏭️",
        "in_progress": "🔄",
        "completed": "✅",
        "open": "🔓",
        "closed": "🔒",
        "merged": "🔀",
        "draft": "📝",
    }

    return status_emojis.get(status.lower(), "❓")


def format_github_markdown_table(data: List[Dict[str, Any]], headers: List[str]) -> str:
    """
    Format data as GitHub markdown table.

    Args:
        data: List of dictionaries with data
        headers: List of header names

    Returns:
        Markdown table string
    """
    if not data or not headers:
        return ""

    # Create header row
    table = ["| " + " | ".join(headers) + " |"]
    table.append("| " + " | ".join(["---"] * len(headers)) + " |")

    # Add data rows
    for row in data:
        values = []
        for header in headers:
            value = row.get(header, "")
            # Escape pipe characters in values
            value = str(value).replace("|", "\\|")
            values.append(value)
        table.append("| " + " | ".join(values) + " |")

    return "\n".join(table)
