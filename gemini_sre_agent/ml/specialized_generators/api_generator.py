# gemini_sre_agent/ml/specialized_generators/api_generator.py

"""
API Code Generator for API-related issues.

This module provides specialized code generation capabilities for API errors,
including authentication, rate limiting, validation, and error handling.
"""

from ..base_code_generator import BaseCodeGenerator
from ..code_generation_models import ValidationRule, ValidationSeverity
from .shared_patterns import (
    get_api_patterns,
    get_common_patterns,
    get_common_validation_rules,
)


class APICodeGenerator(BaseCodeGenerator):
    """Specialized code generator for API-related issues"""

    def _get_domain(self) -> str:
        return "api"

    def _get_generator_type(self) -> str:
        return "api_code_generator"

    def _load_domain_specific_patterns(self):
        """Load API-specific code patterns"""
        # Get API-specific patterns
        api_patterns = get_api_patterns()

        # Get common patterns
        common_patterns = get_common_patterns()

        # Combine patterns
        self.code_patterns = api_patterns + list(common_patterns.values())

    def _load_domain_specific_rules(self):
        """Load API-specific validation rules"""
        # Get common validation rules
        common_rules = get_common_validation_rules()

        # API-specific rules
        api_rules = [
            ValidationRule(
                rule_id="api_auth_required",
                name="authentication_required",
                description="Ensure authentication is properly implemented",
                domain="api",
                rule_type="security",
                severity=ValidationSeverity.CRITICAL,
                validation_function="validate_authentication",
                parameters={"check_jwt": True, "check_user_context": True},
            ),
            ValidationRule(
                rule_id="api_rate_limiting",
                name="rate_limiting",
                description="Implement rate limiting to prevent abuse",
                domain="api",
                rule_type="performance",
                severity=ValidationSeverity.MEDIUM,
                validation_function="validate_rate_limiting",
                parameters={"check_implementation": True, "check_thresholds": True},
            ),
        ]

        # Combine rules
        self.validation_rules = list(common_rules.values()) + api_rules

    async def _generate_tests(self, code_fix) -> str:
        """Generate API-specific tests"""
        return f"""# API Tests for {code_fix.file_path}

import pytest
from unittest.mock import Mock, patch
from your_module import {code_fix.fix_description.split()[0]}

class TestAPIFunctionality:
    def test_authentication_success(self):
        '''Test successful authentication'''
        # Test implementation here
        pass
    
    def test_authentication_failure(self):
        '''Test authentication failure handling'''
        # Test implementation here
        pass
    
    def test_input_validation(self):
        '''Test input validation'''
        # Test implementation here
        pass
    
    def test_error_handling(self):
        '''Test error handling'''
        # Test implementation here
        pass
    
    def test_rate_limiting(self):
        '''Test rate limiting functionality'''
        # Test implementation here
        pass

# Integration tests
@pytest.mark.integration
class TestAPIIntegration:
    def test_end_to_end_flow(self):
        '''Test complete API flow'''
        # Test implementation here
        pass"""

    async def _generate_documentation(self, code_fix) -> str:
        """Generate API-specific documentation"""
        return f"""# API Documentation

## {code_fix.fix_description}

### Overview
This fix addresses the API issue: {code_fix.original_issue}

### Implementation Details
{code_fix.fix_description}

### Usage Example
```python
# Example usage of the fixed API functionality
from your_module import fixed_function

try:
    result = fixed_function(valid_input)
    print(f"Success: {{result}}")
except APIError as e:
    print(f"API Error: {{e.message}}")
```

### Configuration
- Authentication: JWT-based with configurable secret
- Rate Limiting: Configurable thresholds and backoff
- Validation: Schema-based input validation
- Logging: Structured logging with request tracking

### Error Codes
- 400: Bad Request (validation errors)
- 401: Unauthorized (authentication required)
- 429: Too Many Requests (rate limit exceeded)
- 500: Internal Server Error (server issues)

### Monitoring
- Request/response logging
- Performance metrics
- Error rate tracking
- Rate limit usage monitoring"""
