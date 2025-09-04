"""Data filtering and privacy controls for sensitive information."""

import logging
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SensitiveDataType(str, Enum):
    """Types of sensitive data to filter."""

    API_KEY = "api_key"
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    PASSWORD = "password"
    TOKEN = "token"
    SECRET = "secret"
    CUSTOM = "custom"


class FilterRule(BaseModel):
    """Rule for filtering sensitive data."""

    data_type: SensitiveDataType = Field(..., description="Type of sensitive data")
    pattern: str = Field(..., description="Regex pattern to match")
    replacement: str = Field(default="[REDACTED]", description="Replacement text")
    case_sensitive: bool = Field(
        default=False, description="Whether pattern is case sensitive"
    )
    enabled: bool = Field(default=True, description="Whether rule is enabled")


class DataFilter:
    """Filter for removing or masking sensitive data."""

    def __init__(self, custom_rules: Optional[List[FilterRule]] = None):
        """Initialize the data filter.

        Args:
            custom_rules: Custom filtering rules to add
        """
        self.rules: List[FilterRule] = []
        self._initialize_default_rules()

        if custom_rules:
            self.rules.extend(custom_rules)

        # Compile regex patterns for performance
        self._compiled_patterns: Dict[str, re.Pattern] = {}
        self._compile_patterns()

    def _initialize_default_rules(self) -> None:
        """Initialize default filtering rules."""
        default_rules = [
            # API Keys
            FilterRule(
                data_type=SensitiveDataType.API_KEY,
                pattern=r'(?i)(api[_-]?key|apikey|access[_-]?key|secret[_-]?key)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
                replacement=r"\1=[REDACTED]",
            ),
            FilterRule(
                data_type=SensitiveDataType.API_KEY,
                pattern=r"(?i)(sk-[a-zA-Z0-9]{20,})",
                replacement="[REDACTED_API_KEY]",
            ),
            FilterRule(
                data_type=SensitiveDataType.API_KEY,
                pattern=r"(?i)(AIza[0-9A-Za-z\-_]{35})",
                replacement="[REDACTED_GOOGLE_KEY]",
            ),
            # Email addresses
            FilterRule(
                data_type=SensitiveDataType.EMAIL,
                pattern=r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                replacement="[REDACTED_EMAIL]",
            ),
            # Phone numbers
            FilterRule(
                data_type=SensitiveDataType.PHONE,
                pattern=r"(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})",
                replacement="[REDACTED_PHONE]",
            ),
            # Social Security Numbers
            FilterRule(
                data_type=SensitiveDataType.SSN,
                pattern=r"\b\d{3}-?\d{2}-?\d{4}\b",
                replacement="[REDACTED_SSN]",
            ),
            # Credit card numbers
            FilterRule(
                data_type=SensitiveDataType.CREDIT_CARD,
                pattern=r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
                replacement="[REDACTED_CC]",
            ),
            # IP addresses
            FilterRule(
                data_type=SensitiveDataType.IP_ADDRESS,
                pattern=r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
                replacement="[REDACTED_IP]",
            ),
            FilterRule(
                data_type=SensitiveDataType.IP_ADDRESS,
                pattern=r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b",
                replacement="[REDACTED_IPV6]",
            ),
            # Passwords
            FilterRule(
                data_type=SensitiveDataType.PASSWORD,
                pattern=r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?([^"\'\s]{3,})["\']?',
                replacement=r"\1=[REDACTED]",
            ),
            # JWT tokens
            FilterRule(
                data_type=SensitiveDataType.TOKEN,
                pattern=r"eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*",
                replacement="[REDACTED_JWT]",
            ),
            # Bearer tokens
            FilterRule(
                data_type=SensitiveDataType.TOKEN,
                pattern=r"(?i)bearer\s+([a-zA-Z0-9_\-\.]+)",
                replacement="Bearer [REDACTED_TOKEN]",
            ),
        ]

        self.rules.extend(default_rules)

    def _compile_patterns(self) -> None:
        """Compile regex patterns for performance."""
        for rule in self.rules:
            if rule.enabled:
                try:
                    flags = 0 if rule.case_sensitive else re.IGNORECASE
                    self._compiled_patterns[rule.pattern] = re.compile(
                        rule.pattern, flags
                    )
                except re.error as e:
                    logger.warning(
                        f"Invalid regex pattern for rule {rule.data_type}: {e}"
                    )

    def add_rule(self, rule: FilterRule) -> None:
        """Add a new filtering rule."""
        self.rules.append(rule)
        if rule.enabled:
            try:
                flags = 0 if rule.case_sensitive else re.IGNORECASE
                self._compiled_patterns[rule.pattern] = re.compile(rule.pattern, flags)
            except re.error as e:
                logger.warning(f"Invalid regex pattern for new rule: {e}")

    def remove_rule(self, data_type: SensitiveDataType, pattern: str) -> bool:
        """Remove a filtering rule."""
        for i, rule in enumerate(self.rules):
            if rule.data_type == data_type and rule.pattern == pattern:
                del self.rules[i]
                if pattern in self._compiled_patterns:
                    del self._compiled_patterns[pattern]
                return True
        return False

    def enable_rule(self, data_type: SensitiveDataType, pattern: str) -> bool:
        """Enable a filtering rule."""
        for rule in self.rules:
            if rule.data_type == data_type and rule.pattern == pattern:
                rule.enabled = True
                try:
                    flags = 0 if rule.case_sensitive else re.IGNORECASE
                    self._compiled_patterns[rule.pattern] = re.compile(
                        rule.pattern, flags
                    )
                except re.error as e:
                    logger.warning(f"Invalid regex pattern when enabling rule: {e}")
                return True
        return False

    def disable_rule(self, data_type: SensitiveDataType, pattern: str) -> bool:
        """Disable a filtering rule."""
        for rule in self.rules:
            if rule.data_type == data_type and rule.pattern == pattern:
                rule.enabled = False
                if rule.pattern in self._compiled_patterns:
                    del self._compiled_patterns[rule.pattern]
                return True
        return False

    def filter_text(self, text: str) -> str:
        """Filter sensitive data from text.

        Args:
            text: Text to filter

        Returns:
            Filtered text with sensitive data replaced
        """
        if not text:
            return text

        filtered_text = text

        for rule in self.rules:
            if not rule.enabled:
                continue

            pattern = self._compiled_patterns.get(rule.pattern)
            if pattern:
                try:
                    filtered_text = pattern.sub(rule.replacement, filtered_text)
                except Exception as e:
                    logger.warning(f"Error applying filter rule {rule.data_type}: {e}")

        return filtered_text

    def filter_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter sensitive data from a dictionary.

        Args:
            data: Dictionary to filter

        Returns:
            Filtered dictionary with sensitive data replaced
        """
        if not data:
            return data

        filtered_data = {}

        for key, value in data.items():
            # Check if key itself contains sensitive data
            filtered_key = self.filter_text(str(key))

            # Filter the value
            if isinstance(value, str):
                filtered_value = self.filter_text(value)
            elif isinstance(value, dict):
                filtered_value = self.filter_dict(value)
            elif isinstance(value, list):
                filtered_value = self.filter_list(value)
            else:
                filtered_value = value

            filtered_data[filtered_key] = filtered_value

        return filtered_data

    def filter_list(self, data: List[Any]) -> List[Any]:
        """Filter sensitive data from a list.

        Args:
            data: List to filter

        Returns:
            Filtered list with sensitive data replaced
        """
        if not data:
            return data

        filtered_list = []

        for item in data:
            if isinstance(item, str):
                filtered_item = self.filter_text(item)
            elif isinstance(item, dict):
                filtered_item = self.filter_dict(item)
            elif isinstance(item, list):
                filtered_item = self.filter_list(item)
            else:
                filtered_item = item

            filtered_list.append(filtered_item)

        return filtered_list

    def filter_any(self, data: Any) -> Any:
        """Filter sensitive data from any data type.

        Args:
            data: Data to filter

        Returns:
            Filtered data with sensitive data replaced
        """
        if isinstance(data, str):
            return self.filter_text(data)
        elif isinstance(data, dict):
            return self.filter_dict(data)
        elif isinstance(data, list):
            return self.filter_list(data)
        else:
            return data

    def contains_sensitive_data(self, text: str) -> bool:
        """Check if text contains sensitive data.

        Args:
            text: Text to check

        Returns:
            True if sensitive data is detected
        """
        if not text:
            return False

        for rule in self.rules:
            if not rule.enabled:
                continue

            pattern = self._compiled_patterns.get(rule.pattern)
            if pattern and pattern.search(text):
                return True

        return False

    def get_sensitive_data_types(self, text: str) -> Set[SensitiveDataType]:
        """Get the types of sensitive data found in text.

        Args:
            text: Text to analyze

        Returns:
            Set of sensitive data types found
        """
        if not text:
            return set()

        found_types = set()

        for rule in self.rules:
            if not rule.enabled:
                continue

            pattern = self._compiled_patterns.get(rule.pattern)
            if pattern and pattern.search(text):
                found_types.add(rule.data_type)

        return found_types

    def get_rules_by_type(self, data_type: SensitiveDataType) -> List[FilterRule]:
        """Get all rules for a specific data type."""
        return [rule for rule in self.rules if rule.data_type == data_type]

    def get_enabled_rules(self) -> List[FilterRule]:
        """Get all enabled rules."""
        return [rule for rule in self.rules if rule.enabled]

    def get_disabled_rules(self) -> List[FilterRule]:
        """Get all disabled rules."""
        return [rule for rule in self.rules if not rule.enabled]

    def validate_rules(self) -> List[str]:
        """Validate all rules and return any errors."""
        errors = []

        for rule in self.rules:
            try:
                flags = 0 if rule.case_sensitive else re.IGNORECASE
                re.compile(rule.pattern, flags)
            except re.error as e:
                errors.append(f"Invalid regex pattern for {rule.data_type}: {e}")

        return errors
