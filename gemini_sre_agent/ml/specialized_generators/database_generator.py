# gemini_sre_agent/ml/specialized_generators/database_generator.py


from ..base_code_generator import BaseCodeGenerator
from ..code_generation_models import CodePattern, ValidationRule, ValidationSeverity


class DatabaseCodeGenerator(BaseCodeGenerator):
    """Specialized generator for database-related issues"""

    def _get_domain(self) -> str:
        return "database"

    def _get_generator_type(self) -> str:
        return "database_code_generator"

    def _load_domain_specific_patterns(self):
        """Load database-specific patterns and best practices"""
        self.code_patterns = [
            CodePattern(
                pattern_id="db_connection_pool",
                name="Database Connection Pooling",
                description="Implement connection pooling for database connections",
                domain="database",
                pattern_type="connection_management",
                code_template="connection_pool = create_connection_pool()",
                validation_rules=["connection_pool_rule"],
                best_practices=[
                    "Use connection pooling to manage database connections",
                    "Set appropriate pool size based on application needs",
                    "Implement connection health checks",
                ],
                examples=[
                    "import psycopg2.pool\npool = psycopg2.pool.SimpleConnectionPool(1, 20, ...)"
                ],
            ),
            CodePattern(
                pattern_id="db_transaction_handling",
                name="Transaction Management",
                description="Proper transaction handling with rollback support",
                domain="database",
                pattern_type="transaction",
                code_template="try:\n    # Database operations\n    connection.commit()\nexcept:\n    connection.rollback()",
                validation_rules=["transaction_consistency_rule"],
                best_practices=[
                    "Always use transactions for multiple related operations",
                    "Implement proper rollback on errors",
                    "Set appropriate isolation levels",
                ],
                examples=[
                    "with connection.begin() as transaction:\n    # operations\n    pass"
                ],
            ),
            CodePattern(
                pattern_id="db_error_handling",
                name="Database Error Handling",
                description="Comprehensive error handling for database operations",
                domain="database",
                pattern_type="error_handling",
                code_template="try:\n    # Database operation\n    pass\nexcept DatabaseError as e:\n    logger.error(f'Database error: {e}')\n    raise",
                validation_rules=["error_handling_rule"],
                best_practices=[
                    "Catch specific database exceptions",
                    "Log errors with context",
                    "Implement retry logic for transient errors",
                ],
                examples=[
                    "except psycopg2.OperationalError as e:\n    if e.pgcode == '08000':\n        retry_connection()"
                ],
            ),
            CodePattern(
                pattern_id="db_query_optimization",
                name="Query Optimization",
                description="Optimize database queries for performance",
                domain="database",
                pattern_type="performance",
                code_template="# Use indexes, limit results, optimize joins",
                validation_rules=["performance_rule"],
                best_practices=[
                    "Use appropriate indexes",
                    "Limit result sets",
                    "Avoid N+1 query problems",
                    "Use query execution plans",
                ],
                examples=[
                    "SELECT * FROM users WHERE email = %s LIMIT 1",
                    "SELECT u.name, p.title FROM users u JOIN posts p ON u.id = p.user_id",
                ],
            ),
            CodePattern(
                pattern_id="db_connection_retry",
                name="Connection Retry Logic",
                description="Implement retry logic for database connections",
                domain="database",
                pattern_type="resilience",
                code_template="for attempt in range(max_retries):\n    try:\n        connection = create_connection()\n        break\n    except ConnectionError:\n        if attempt == max_retries - 1:\n            raise\n        time.sleep(backoff_factor ** attempt)",
                validation_rules=["retry_logic_rule"],
                best_practices=[
                    "Use exponential backoff",
                    "Set maximum retry attempts",
                    "Log retry attempts for monitoring",
                ],
                examples=[
                    "import tenacity\n@tenacity.retry(stop=tenacity.stop_after_attempt(3))"
                ],
            ),
        ]

    def _load_domain_specific_rules(self):
        """Load database-specific validation rules"""
        self.validation_rules = [
            ValidationRule(
                rule_id="db_syntax_rule",
                name="Database Syntax Validation",
                description="Validate database query syntax",
                domain="database",
                rule_type="syntax",
                severity=ValidationSeverity.CRITICAL,
                validation_function="validate_database_syntax",
                parameters={"strict_mode": True},
            ),
            ValidationRule(
                rule_id="db_connection_pool_rule",
                name="Connection Pool Validation",
                description="Validate connection pool configuration",
                domain="database",
                rule_type="configuration",
                severity=ValidationSeverity.HIGH,
                validation_function="validate_connection_pool",
                parameters={"min_pool_size": 1, "max_pool_size": 100},
            ),
            ValidationRule(
                rule_id="db_transaction_consistency_rule",
                name="Transaction Consistency",
                description="Ensure transaction consistency",
                domain="database",
                rule_type="consistency",
                severity=ValidationSeverity.HIGH,
                validation_function="validate_transaction_consistency",
                parameters={"check_rollback": True},
            ),
            ValidationRule(
                rule_id="db_error_handling_rule",
                name="Error Handling Validation",
                description="Validate error handling implementation",
                domain="database",
                rule_type="error_handling",
                severity=ValidationSeverity.MEDIUM,
                validation_function="validate_error_handling",
                parameters={"require_logging": True},
            ),
            ValidationRule(
                rule_id="db_performance_rule",
                name="Performance Validation",
                description="Validate performance characteristics",
                domain="database",
                rule_type="performance",
                severity=ValidationSeverity.MEDIUM,
                validation_function="validate_performance",
                parameters={"max_query_time": 1000},
            ),
            ValidationRule(
                rule_id="db_retry_logic_rule",
                name="Retry Logic Validation",
                description="Validate retry logic implementation",
                domain="database",
                rule_type="resilience",
                severity=ValidationSeverity.LOW,
                validation_function="validate_retry_logic",
                parameters={"max_retries": 3},
            ),
        ]

    async def _generate_tests(self, code_fix) -> str:
        """Generate database-specific tests"""
        return f"""# Database tests for {code_fix.file_path}
import pytest
from unittest.mock import Mock, patch

def test_database_connection():
    # Test database connection establishment
    pass

def test_transaction_rollback():
    # Test transaction rollback on error
    pass

def test_connection_pool():
    # Test connection pool functionality
    pass

def test_error_handling():
    # Test database error handling
    pass

def test_query_optimization():
    # Test query performance
    pass"""

    async def _generate_documentation(self, code_fix) -> str:
        """Generate database-specific documentation"""
        return f"""# Database Fix Documentation

## File: {code_fix.file_path}

### Issue Description
{code_fix.original_issue}

### Fix Description
{code_fix.fix_description}

### Database Patterns Applied
- Connection pooling for efficient connection management
- Transaction handling with proper rollback support
- Comprehensive error handling and logging
- Query optimization for performance
- Retry logic for resilience

### Best Practices Implemented
1. **Connection Management**: Uses connection pooling to avoid connection overhead
2. **Transaction Safety**: Implements proper transaction boundaries with rollback
3. **Error Handling**: Catches specific database exceptions and logs appropriately
4. **Performance**: Optimizes queries and uses appropriate indexes
5. **Resilience**: Implements retry logic for transient failures

### Testing Requirements
- Test connection establishment and cleanup
- Test transaction rollback scenarios
- Test error handling paths
- Test performance characteristics
- Test retry logic under failure conditions

### Deployment Notes
- Ensure database connection parameters are properly configured
- Monitor connection pool metrics
- Set up appropriate logging for database operations
- Configure retry parameters based on environment"""
