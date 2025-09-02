# gemini_sre_agent/ml/specialized_generators/shared_patterns.py

"""
Shared code patterns for specialized generators.

This module contains common code patterns that can be used across
different specialized generators to reduce duplication and maintain
consistency in generated code.
"""

from ..code_generation_models import CodePattern, ValidationRule, ValidationSeverity


def get_common_patterns() -> dict[str, CodePattern]:
    """Get common code patterns used across generators"""
    return {
        "input_validation": CodePattern(
            pattern_id="common_input_validation",
            name="input_validation",
            description="Common input validation pattern",
            domain="common",
            pattern_type="validation",
            code_template="""def validate_input(input_data, schema):
    if not isinstance(input_data, dict):
        raise ValueError("Input must be a dictionary")
    
    try:
        validated_data = schema.validate(input_data)
        return validated_data
    except ValidationError as e:
        raise ValueError(f"Input validation failed: {e}")""",
            validation_rules=["validation_rule"],
            best_practices=["Always validate inputs", "Use clear error messages"],
            examples=["Schema validation", "Type checking"]
        ),
        "error_handling": CodePattern(
            pattern_id="common_error_handling",
            name="error_handling",
            description="Common error handling pattern",
            domain="common",
            pattern_type="error_handling",
            code_template="""def handle_operation(operation_func, *args, **kwargs):
    try:
        result = operation_func(*args, **kwargs)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        return {"success": False, "error": str(e)}""",
            validation_rules=["error_handling_rule"],
            best_practices=["Use try-catch blocks", "Log errors appropriately"],
            examples=["Error handling", "Logging"]
        ),
        "logging": CodePattern(
            pattern_id="common_logging",
            name="logging",
            description="Common logging pattern",
            domain="common",
            pattern_type="logging",
            code_template="""def log_operation(operation_name, details=None):
    log_data = {
        "operation": operation_name,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details or {}
    }
    logger.info(f"Operation: {operation_name}", extra=log_data)""",
            validation_rules=["logging_rule"],
            best_practices=["Log all operations", "Include relevant context"],
            examples=["Operation logging", "Context tracking"]
        )
    }


def get_common_validation_rules() -> dict[str, ValidationRule]:
    """Get common validation rules used across generators"""
    return {
        "input_validation": ValidationRule(
            rule_id="common_input_validation",
            name="input_validation",
            description="Validate all inputs",
            domain="common",
            rule_type="validation",
            severity=ValidationSeverity.HIGH,
            validation_function="validate_input",
            parameters={"check_type": True, "check_schema": True}
        ),
        "error_handling": ValidationRule(
            rule_id="common_error_handling",
            name="error_handling",
            description="Implement proper error handling",
            domain="common",
            rule_type="error_handling",
            severity=ValidationSeverity.MEDIUM,
            validation_function="validate_error_handling",
            parameters={"check_try_catch": True, "check_logging": True}
        ),
        "logging": ValidationRule(
            rule_id="common_logging",
            name="logging",
            description="Implement proper logging",
            domain="common",
            rule_type="logging",
            severity=ValidationSeverity.LOW,
            validation_function="validate_logging",
            parameters={"check_operation_logging": True, "check_error_logging": True}
        )
    }


def get_api_patterns() -> list[CodePattern]:
    """Get API-specific code patterns"""
    return [
        CodePattern(
            pattern_id="api_rate_limiting",
            name="rate_limiting",
            description="Implement rate limiting with exponential backoff",
            domain="api",
            pattern_type="rate_limiting",
            code_template="""def rate_limited_request(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RateLimitExceeded:
            time.sleep(backoff_time)
            return func(*args, **kwargs)
    return wrapper""",
            validation_rules=["rate_limiting_rule"],
            best_practices=["Use exponential backoff", "Implement proper error handling"],
            examples=["Rate limiting decorator", "Backoff strategy"]
        ),
        CodePattern(
            pattern_id="api_authentication",
            name="authentication_middleware",
            description="JWT authentication middleware for API requests",
            domain="api",
            pattern_type="authentication",
            code_template="""def authenticate_request(request):
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        raise AuthenticationError('Missing authentication token')
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        request.user = payload
        return request
    except jwt.InvalidTokenError:
        raise AuthenticationError('Invalid authentication token')""",
            validation_rules=["authentication_rule"],
            best_practices=["Use secure JWT", "Implement proper error handling"],
            examples=["JWT middleware", "Token validation"]
        )
    ]


def get_security_patterns() -> list[CodePattern]:
    """Get security-specific code patterns"""
    return [
        CodePattern(
            pattern_id="security_input_validation",
            name="input_validation",
            description="Secure input validation with sanitization",
            domain="security",
            pattern_type="input_validation",
            code_template="""def secure_input_validation(input_data, allowed_patterns):
    if not isinstance(input_data, str):
        raise SecurityError("Invalid input type")
    
    # Remove potentially dangerous characters
    sanitized = re.sub(r'[<>"\']', '', input_data)
    
    # Validate against allowed patterns
    if not re.match(allowed_patterns, sanitized):
        raise SecurityError("Input contains forbidden characters")
    
    return sanitized""",
            validation_rules=["input_validation_rule"],
            best_practices=["Always validate inputs", "Use whitelist approach"],
            examples=["Input sanitization", "Pattern validation"]
        ),
        CodePattern(
            pattern_id="security_authentication",
            name="secure_authentication",
            description="Secure authentication with proper session management",
            domain="security",
            pattern_type="authentication",
            code_template="""def secure_authentication(username, password):
    # Use constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(
        hash_password(password, salt),
        stored_hash
    ):
        raise AuthenticationError("Invalid credentials")
    
    # Generate secure session token
    session_token = secrets.token_urlsafe(32)
    session_data = {
        'user_id': user.id,
        'created_at': datetime.utcnow(),
        'expires_at': datetime.utcnow() + timedelta(hours=1)
    }
    
    return session_token, session_data""",
            validation_rules=["authentication_rule"],
            best_practices=["Use constant-time comparison", "Secure session tokens"],
            examples=["Password hashing", "Session management"]
        )
    ]
