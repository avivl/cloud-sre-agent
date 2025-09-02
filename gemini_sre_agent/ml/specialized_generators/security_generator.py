# gemini_sre_agent/ml/specialized_generators/security_generator.py

"""
Security Code Generator for security-related issues.

This module provides specialized code generation capabilities for security issues,
including input validation, authentication, authorization, and secure coding practices.
"""

from ..base_code_generator import BaseCodeGenerator
from ..code_generation_models import CodePattern, ValidationRule, ValidationSeverity


class SecurityCodeGenerator(BaseCodeGenerator):
    """Specialized code generator for security-related issues"""

    def _get_domain(self) -> str:
        return "security"

    def _get_generator_type(self) -> str:
        return "security_code_generator"

    def _load_domain_specific_patterns(self):
        """Load security-specific code patterns"""
        self.code_patterns = [
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
                examples=["Input sanitization", "Pattern validation"],
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
                best_practices=[
                    "Use constant-time comparison",
                    "Secure session tokens",
                ],
                examples=["Password hashing", "Session management"],
            ),
            CodePattern(
                pattern_id="security_authorization",
                name="authorization_check",
                description="Role-based access control implementation",
                domain="security",
                pattern_type="authorization",
                code_template="""def check_authorization(user, resource, action):
    # Check if user has permission for the action on the resource
    if not user.is_authenticated:
        raise AuthorizationError("User not authenticated")
    
    # Check role-based permissions
    required_permission = f"{resource}:{action}"
    if required_permission not in user.permissions:
        raise AuthorizationError("Insufficient permissions")
    
    # Check resource ownership if applicable
    if hasattr(resource, 'owner_id') and resource.owner_id != user.id:
        if not user.has_role('admin'):
            raise AuthorizationError("Access denied to resource")
    
    return True""",
                validation_rules=["authorization_rule"],
                best_practices=["Check authentication first", "Verify permissions"],
                examples=["RBAC implementation", "Resource ownership"],
            ),
            CodePattern(
                pattern_id="security_encryption",
                name="data_encryption",
                description="Secure data encryption and decryption",
                domain="security",
                pattern_type="encryption",
                code_template="""def encrypt_sensitive_data(data, key):
    # Generate a random IV for each encryption
    iv = os.urandom(16)
    
    # Create cipher with AES-256-GCM
    cipher = AES.new(key, AES.MODE_GCM, iv)
    
    # Encrypt the data
    ciphertext, tag = cipher.encrypt_and_digest(data.encode())
    
    # Return IV, ciphertext, and authentication tag
    return {
        'iv': base64.b64encode(iv).decode(),
        'ciphertext': base64.b64encode(ciphertext).decode(),
        'tag': base64.b64encode(tag).decode()
    }

def decrypt_sensitive_data(encrypted_data, key):
    # Decode the encrypted components
    iv = base64.b64decode(encrypted_data['iv'])
    ciphertext = base64.b64decode(encrypted_data['ciphertext'])
    tag = base64.b64decode(encrypted_data['tag'])
    
    # Create cipher and decrypt
    cipher = AES.new(key, AES.MODE_GCM, iv)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    
    return plaintext.decode()""",
                validation_rules=["encryption_rule"],
                best_practices=["Use strong algorithms", "Generate random IVs"],
                examples=["AES encryption", "Secure key management"],
            ),
            CodePattern(
                pattern_id="security_logging",
                name="security_logging",
                description="Secure logging without sensitive data exposure",
                domain="security",
                pattern_type="logging",
                code_template="""def secure_log_event(event_type, user_id, details):
    # Sanitize sensitive information
    sanitized_details = {
        k: v for k, v in details.items() 
        if k not in ['password', 'token', 'credit_card', 'ssn']
    }
    
    # Log security event
    logger.warning(
        f"Security Event: {event_type}",
        extra={
            'event_type': event_type,
            'user_id': user_id,
            'timestamp': datetime.utcnow().isoformat(),
            'ip_address': get_client_ip(),
            'details': sanitized_details
        }
    )
    
    # Alert security team for critical events
    if event_type in ['failed_login', 'unauthorized_access', 'data_breach']:
        alert_security_team(event_type, user_id, sanitized_details)""",
                validation_rules=["logging_rule"],
                best_practices=["Sanitize sensitive data", "Alert on critical events"],
                examples=["Security logging", "Event monitoring"],
            ),
        ]

    def _load_domain_specific_rules(self):
        """Load security-specific validation rules"""
        self.validation_rules = [
            ValidationRule(
                rule_id="security_input_validation",
                name="input_validation",
                description="Validate and sanitize all inputs",
                domain="security",
                rule_type="input_validation",
                severity=ValidationSeverity.CRITICAL,
                validation_function="validate_input_security",
                parameters={"check_sanitization": True, "check_validation": True},
            ),
            ValidationRule(
                rule_id="security_authentication",
                name="secure_authentication",
                description="Implement secure authentication",
                domain="security",
                rule_type="authentication",
                severity=ValidationSeverity.CRITICAL,
                validation_function="validate_authentication_security",
                parameters={"check_password_hash": True, "check_session": True},
            ),
            ValidationRule(
                rule_id="security_authorization",
                name="proper_authorization",
                description="Implement proper authorization checks",
                domain="security",
                rule_type="authorization",
                severity=ValidationSeverity.HIGH,
                validation_function="validate_authorization",
                parameters={"check_permissions": True, "check_ownership": True},
            ),
            ValidationRule(
                rule_id="security_encryption",
                name="data_encryption",
                description="Encrypt sensitive data at rest and in transit",
                domain="security",
                rule_type="encryption",
                severity=ValidationSeverity.HIGH,
                validation_function="validate_encryption",
                parameters={"check_algorithm": True, "check_key_management": True},
            ),
            ValidationRule(
                rule_id="security_logging",
                name="secure_logging",
                description="Implement secure logging practices",
                domain="security",
                rule_type="logging",
                severity=ValidationSeverity.MEDIUM,
                validation_function="validate_logging_security",
                parameters={"check_sanitization": True, "check_access_control": True},
            ),
            ValidationRule(
                rule_id="security_dependencies",
                name="dependency_security",
                description="Use secure dependencies and keep them updated",
                domain="security",
                rule_type="dependencies",
                severity=ValidationSeverity.MEDIUM,
                validation_function="validate_dependencies",
                parameters={"check_vulnerabilities": True, "check_updates": True},
            ),
        ]

    async def _generate_tests(self, code_fix) -> str:
        """Generate security-specific tests"""
        return f"""# Security Tests for {code_fix.file_path}

import pytest
from unittest.mock import Mock, patch
from your_module import {code_fix.fix_description.split()[0]}

class TestSecurityFunctionality:
    def test_input_validation_success(self):
        '''Test successful input validation'''
        # Test implementation here
        pass
    
    def test_input_validation_malicious_input(self):
        '''Test input validation with malicious input'''
        # Test implementation here
        pass
    
    def test_authentication_success(self):
        '''Test successful authentication'''
        # Test implementation here
        pass
    
    def test_authentication_failure(self):
        '''Test authentication failure handling'''
        # Test implementation here
        pass
    
    def test_authorization_check(self):
        '''Test authorization checks'''
        # Test implementation here
        pass
    
    def test_encryption_decryption(self):
        '''Test encryption and decryption'''
        # Test implementation here
        pass

# Security-specific tests
class TestSecurityVulnerabilities:
    def test_sql_injection_prevention(self):
        '''Test SQL injection prevention'''
        # Test implementation here
        pass
    
    def test_xss_prevention(self):
        '''Test XSS prevention'''
        # Test implementation here
        pass
    
    def test_csrf_protection(self):
        '''Test CSRF protection'''
        # Test implementation here
        pass
    
    def test_timing_attack_prevention(self):
        '''Test timing attack prevention'''
        # Test implementation here
        pass"""

    async def _generate_documentation(self, code_fix) -> str:
        """Generate security-specific documentation"""
        return f"""# Security Documentation

## {code_fix.fix_description}

### Overview
This fix addresses the security issue: {code_fix.original_issue}

### Security Considerations
{code_fix.fix_description}

### Implementation Details
- Input validation and sanitization
- Secure authentication and authorization
- Data encryption and secure storage
- Secure logging and monitoring
- Vulnerability prevention

### Security Best Practices
1. **Input Validation**: Always validate and sanitize user inputs
2. **Authentication**: Use secure password hashing and session management
3. **Authorization**: Implement proper access control and permission checks
4. **Encryption**: Encrypt sensitive data at rest and in transit
5. **Logging**: Log security events without exposing sensitive data
6. **Dependencies**: Keep dependencies updated and scan for vulnerabilities

### Threat Model
- **SQL Injection**: Prevented through parameterized queries
- **XSS Attacks**: Prevented through input sanitization
- **CSRF Attacks**: Prevented through token validation
- **Session Hijacking**: Prevented through secure session management
- **Data Breaches**: Prevented through encryption and access control

### Security Testing
- Automated security testing with tools like Bandit
- Manual penetration testing
- Code security reviews
- Dependency vulnerability scanning
- Security compliance audits

### Incident Response
- Monitor security logs for suspicious activity
- Implement automated alerts for security events
- Have incident response procedures in place
- Regular security training for development team"""
