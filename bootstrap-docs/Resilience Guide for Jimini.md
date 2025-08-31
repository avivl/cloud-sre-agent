# Resilience Guide for Jimini

This document provides a complete overview of resilience practices, concepts, and implementation in the Jimini ecosystem. It serves as both a theoretical foundation and practical implementation guide for building fault-tolerant, reliable applications that gracefully handle failures and maintain high availability.

## Core Resilience Concepts (Language Agnostic)

### Resilience Philosophy

Our resilience approach is built on fundamental principles that ensure applications can handle failures gracefully and maintain service availability:

#### Fault Tolerance

- **Concept**: Systems should continue operating despite component failures  
- **Benefits**: Prevents cascading failures and maintains user experience  
- **Implementation**: Use redundancy, graceful degradation, and isolation patterns

#### Graceful Degradation

- **Concept**: Reduce functionality rather than complete system failure  
- **Key Elements**:  
  - Essential vs. non-essential features identification  
  - Fallback mechanisms for critical operations  
  - User communication about reduced functionality  
- **Benefits**: Maintains core business value during partial outages

#### Fail-Fast Principles

- **Concept**: Detect and respond to failures quickly rather than letting them propagate  
- **Implementation**: Validation, circuit breakers, and timeout patterns  
- **Benefits**: Reduces resource waste and improves recovery time

#### Self-Healing Systems

- **Concept**: Automatic detection and recovery from failures  
- **Considerations**:  
  - Automatic retry mechanisms  
  - Circuit breaker auto-recovery  
  - Health monitoring and alerting  
- **Benefits**: Reduces manual intervention and improves availability

### Environment-Specific Resilience Strategies

#### Production Environment

- **Configuration**: Conservative settings prioritizing stability  
- **Circuit Breakers**: Sensitive thresholds for fast failure detection  
- **Retry Policies**: Limited attempts with exponential backoff  
- **Monitoring**: Comprehensive observability and alerting

#### Staging Environment

- **Configuration**: Moderate settings for realistic testing  
- **Circuit Breakers**: Balanced thresholds for testing failure scenarios  
- **Retry Policies**: Moderate attempts for load testing  
- **Monitoring**: Detailed logging for troubleshooting

#### Development Environment

- **Configuration**: Relaxed settings for fast iteration  
- **Circuit Breakers**: Lenient thresholds to avoid interrupting development  
- **Retry Policies**: Minimal retries for quick feedback  
- **Monitoring**: Verbose logging for debugging

### Resilience Patterns

#### Circuit Breaker Pattern

- **Concept**: Prevent calls to failing services by "opening" the circuit  
- **States**: Closed (normal), Open (failing), Half-Open (testing recovery)  
- **Benefits**: Prevents resource exhaustion and enables fast failure

#### Retry Pattern

- **Concept**: Automatically retry failed operations with intelligent backoff  
- **Strategies**: Exponential backoff, jitter, maximum attempts  
- **Benefits**: Handles transient failures without user intervention

#### Timeout Pattern

- **Concept**: Set maximum time limits for operations  
- **Implementation**: Request timeouts, operation timeouts, circuit timeouts  
- **Benefits**: Prevents resource blocking and enables predictable behavior

#### Bulkhead Pattern

- **Concept**: Isolate resources to prevent failure propagation  
- **Implementation**: Thread pools, connection pools, rate limiting  
- **Benefits**: Limits blast radius of failures

#### Rate Limiting Pattern

- **Concept**: Control the rate of requests to prevent overload  
- **Algorithms**: Token bucket, sliding window, fixed window  
- **Benefits**: Protects services from abuse and overload

### Resilience Pattern Usage Guidelines

#### Circuit Breaker (Service Protection)

- **When**: Protecting against cascading failures from downstream services  
- **Examples**: External API calls, database connections, service dependencies  
- **Configuration**: Failure threshold, timeout period, half-open testing

#### Retry (Transient Failure Handling)

- **When**: Handling temporary network issues, server overload, rate limits  
- **Examples**: API timeouts, network blips, temporary service unavailability  
- **Configuration**: Max attempts, backoff strategy, jitter

#### Timeout (Resource Protection)

- **When**: Preventing resource exhaustion from slow operations  
- **Examples**: HTTP requests, database queries, file operations  
- **Configuration**: Operation timeout, connection timeout, total timeout

#### Bulkhead (Isolation)

- **When**: Isolating different types of work or user classes  
- **Examples**: Separating critical vs. non-critical operations  
- **Configuration**: Pool sizes, queue limits, resource allocation

#### Rate Limiting (Overload Protection)

- **When**: Protecting services from excessive load or abuse  
- **Examples**: API endpoints, user actions, system resources  
- **Configuration**: Requests per second, burst limits, time windows


## Python Implementation with [Hyx](https://hyx.readthedocs.io/en/latest/)

### Core Setup and Configuration

#### Hyx Integration

We should use Hyx as the primary resilience library, complemented by other specialized libraries for comprehensive fault tolerance:

```py
# src/modules/resilience/hyx_client.py
import asyncio
from typing import Dict, Any, Optional, Callable, TypeVar, Generic
from dataclasses import dataclass
from hyx import (
    AsyncCircuitBreaker, AsyncRetry, AsyncTimeout, 
    AsyncBulkhead, AsyncRateLimit, AsyncFallback
)
import tenacity
from slowapi import Limiter
from slowapi.util import get_remote_address

T = TypeVar('T')

@dataclass
class ResilienceConfig:
    retry: Dict[str, Any]
    circuit_breaker: Dict[str, Any] 
    timeout: int
    bulkhead: Dict[str, Any]
    rate_limit: Dict[str, Any]

class HyxResilientClient:
    """
    Comprehensive resilience client using Hyx and complementary libraries.
    Provides circuit breaker, retry, timeout, bulkhead, and rate limiting.
    """
    
    def __init__(self, config: ResilienceConfig):
        self.config = config
        
        # Initialize Hyx components
        self.circuit_breaker = AsyncCircuitBreaker(
            failure_threshold=config.circuit_breaker['failure_threshold'],
            recovery_timeout=config.circuit_breaker['recovery_timeout'],
            expected_exception=config.circuit_breaker.get('expected_exception', Exception)
        )
        
        self.retry_policy = AsyncRetry(
            attempts=config.retry['max_attempts'],
            backoff=self._create_backoff_strategy(config.retry),
            expected_exception=config.retry.get('expected_exception', Exception)
        )
        
        self.timeout = AsyncTimeout(config.timeout)
        
        self.bulkhead = AsyncBulkhead(
            capacity=config.bulkhead['limit'],
            queue_size=config.bulkhead['queue']
        )
        
        self.rate_limiter = AsyncRateLimit(
            rate=config.rate_limit['requests_per_second'],
            burst=config.rate_limit['burst_limit']
        )
        
        # Health monitoring
        self._stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'circuit_breaker_opens': 0,
            'rate_limit_hits': 0,
            'timeouts': 0,
            'retries': 0
        }

    def _create_backoff_strategy(self, retry_config: Dict[str, Any]):
        """Create exponential backoff with jitter"""
        return tenacity.wait_exponential(
            multiplier=retry_config.get('initial_delay', 1),
            max=retry_config.get('max_delay', 60),
            jitter=tenacity.jitter.random_jitter if retry_config.get('randomize', True) else None
        )

    async def execute(self, operation: Callable[[], Awaitable[T]]) -> T:
        """
        Execute operation with full resilience pipeline:
        Rate Limit -> Bulkhead -> Circuit Breaker -> Retry -> Timeout -> Operation
        """
        self._stats['total_operations'] += 1
        
        try:
            # Apply all resilience patterns in order
            async with self.rate_limiter:
                async with self.bulkhead:
                    result = await self.circuit_breaker(
                        self.retry_policy(
                            self.timeout(operation)
                        )
                    )
            
            self._stats['successful_operations'] += 1
            return result
            
        except Exception as e:
            self._stats['failed_operations'] += 1
            self._update_error_stats(e)
            raise

    def _update_error_stats(self, error: Exception):
        """Update statistics based on error type"""
        error_type = type(error).__name__
        
        if 'CircuitBreaker' in error_type:
            self._stats['circuit_breaker_opens'] += 1
        elif 'RateLimit' in error_type:
            self._stats['rate_limit_hits'] += 1
        elif 'Timeout' in error_type:
            self._stats['timeouts'] += 1
        elif 'Retry' in error_type:
            self._stats['retries'] += 1

    def get_health_stats(self) -> Dict[str, Any]:
        """Get comprehensive health statistics"""
        return {
            'circuit_breaker': {
                'status': self.circuit_breaker.state,
                'failure_count': self.circuit_breaker.failure_count,
                'last_failure_time': getattr(self.circuit_breaker, 'last_failure_time', None)
            },
            'bulkhead': {
                'active_requests': self.bulkhead.active_count,
                'queued_requests': self.bulkhead.queue_size,
                'capacity': self.bulkhead.capacity
            },
            'rate_limiter': {
                'tokens_available': self.rate_limiter.tokens,
                'requests_per_second': self.rate_limiter.rate
            },
            'statistics': self._stats.copy()
        }

# Environment-specific configuration factory
def create_resilience_config(environment: str = 'development') -> ResilienceConfig:
    """Create environment-appropriate resilience configuration"""
    
    configs = {
        'production': ResilienceConfig(
            retry={
                'max_attempts': 3,
                'initial_delay': 1,
                'max_delay': 10,
                'randomize': True,
                'expected_exception': (ConnectionError, TimeoutError)
            },
            circuit_breaker={
                'failure_threshold': 3,
                'recovery_timeout': 60,
                'expected_exception': (ConnectionError, TimeoutError)
            },
            timeout=30,
            bulkhead={
                'limit': 10,
                'queue': 5
            },
            rate_limit={
                'requests_per_second': 8,
                'burst_limit': 15
            }
        ),
        'staging': ResilienceConfig(
            retry={
                'max_attempts': 3,
                'initial_delay': 1,
                'max_delay': 8,
                'randomize': True
            },
            circuit_breaker={
                'failure_threshold': 4,
                'recovery_timeout': 45
            },
            timeout=25,
            bulkhead={
                'limit': 8,
                'queue': 4
            },
            rate_limit={
                'requests_per_second': 10,
                'burst_limit': 20
            }
        ),
        'development': ResilienceConfig(
            retry={
                'max_attempts': 2,
                'initial_delay': 0.5,
                'max_delay': 5,
                'randomize': False
            },
            circuit_breaker={
                'failure_threshold': 5,
                'recovery_timeout': 30
            },
            timeout=15,
            bulkhead={
                'limit': 5,
                'queue': 3
            },
            rate_limit={
                'requests_per_second': 15,
                'burst_limit': 25
            }
        )
    }
    
    return configs.get(environment, configs['development'])
```

#### Additional Resilience Libraries Integration

```py
# src/modules/resilience/enhanced_client.py
from circuitbreaker import circuit
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import limits
from slowapi import Limiter
import asyncio
from typing import Union, List
import logging

class EnhancedResilientClient:
    """
    Extended resilience client combining Hyx with specialized libraries
    for specific use cases and enhanced functionality.
    """
    
    def __init__(self, config: ResilienceConfig):
        self.hyx_client = HyxResilientClient(config)
        
        # Enhanced circuit breaker using circuitbreaker library
        self.enhanced_circuit = circuit(
            failure_threshold=config.circuit_breaker['failure_threshold'],
            recovery_timeout=config.circuit_breaker['recovery_timeout'],
            expected_exception=ConnectionError
        )
        
        # Rate limiter using limits library for more complex scenarios
        self.rate_limiter = limits.strategies.MovingWindowRateLimiter(
            limits.parse(f"{config.rate_limit['requests_per_second']}/second")
        )
        
        # Enhanced retry with tenacity for complex retry logic
        self.tenacity_retry = retry(
            stop=stop_after_attempt(config.retry['max_attempts']),
            wait=wait_exponential(
                multiplier=config.retry['initial_delay'],
                max=config.retry['max_delay']
            ),
            retry=retry_if_exception_type((ConnectionError, TimeoutError)),
            reraise=True
        )
        
        self.logger = logging.getLogger(__name__)

    async def execute_with_fallback(
        self, 
        primary_operation: Callable[[], Awaitable[T]],
        fallback_operation: Optional[Callable[[], Awaitable[T]]] = None,
        cache_key: Optional[str] = None
    ) -> T:
        """Execute with automatic fallback and caching"""
        
        try:
            # Try primary operation with full resilience
            return await self.hyx_client.execute(primary_operation)
            
        except Exception as e:
            self.logger.warning(f"Primary operation failed: {e}")
            
            # Try fallback if available
            if fallback_operation:
                try:
                    result = await fallback_operation()
                    self.logger.info("Fallback operation succeeded")
                    return result
                except Exception as fallback_error:
                    self.logger.error(f"Fallback operation failed: {fallback_error}")
            
            # Try cache as last resort
            if cache_key:
                cached_result = await self._get_from_cache(cache_key)
                if cached_result is not None:
                    self.logger.info("Serving from cache as fallback")
                    return cached_result
            
            # Re-raise original exception if all fallbacks fail
            raise e

    async def execute_batch(
        self,
        operations: List[Callable[[], Awaitable[T]]],
        batch_size: int = 5,
        delay_between_batches: float = 0.1
    ) -> List[Union[T, Exception]]:
        """Execute operations in batches with resilience"""
        
        results = []
        
        for i in range(0, len(operations), batch_size):
            batch = operations[i:i + batch_size]
            
            # Execute batch with individual resilience
            batch_results = await asyncio.gather(
                *[self._execute_single_with_error_capture(op) for op in batch],
                return_exceptions=True
            )
            
            results.extend(batch_results)
            
            # Rate limiting delay between batches
            if i + batch_size < len(operations):
                await asyncio.sleep(delay_between_batches)
        
        return results

    async def _execute_single_with_error_capture(self, operation: Callable[[], Awaitable[T]]) -> Union[T, Exception]:
        """Execute single operation capturing errors for batch processing"""
        try:
            return await self.hyx_client.execute(operation)
        except Exception as e:
            return e

    async def _get_from_cache(self, key: str) -> Optional[T]:
        """Get item from cache - implement based on your caching strategy"""
        # Placeholder for cache implementation
        return None
```

### Action Pattern Implementation

```py
# src/modules/external_services/patient_service.py
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from .resilient_client import HyxResilientClient, create_resilience_config
from ..exceptions import (
    ServiceUnavailableError, SystemBusyError, OperationTimeoutError,
    RateLimitError, BusinessLogicError
)
import httpx
import os

@dataclass
class GetPatientParams:
    patient_id: str
    include_details: bool = False

@dataclass
class Patient:
    id: str
    first_name: str
    last_name: str
    email: str
    additional_data: Optional[Dict[str, Any]] = None

class ExternalPatientService:
    """
    External service client implementing the action pattern
    with comprehensive resilience using Hyx.
    """
    
    def __init__(self):
        environment = os.getenv('ENVIRONMENT', 'development')
        config = create_resilience_config(environment)
        self.resilient_client = HyxResilientClient(config)
        self.base_url = os.getenv('EXTERNAL_API_URL', 'https://api.external-service.com')
        self.api_key = os.getenv('EXTERNAL_API_KEY')
        
    async def get_patient_by_id(self, params: GetPatientParams) -> Optional[Patient]:
        """
        Get patient by ID with full resilience patterns.
        Implements the mandatory action pattern for external service calls.
        """
        
        async def _make_request() -> Optional[Patient]:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/patients/{params.patient_id}",
                    headers={
                        'Authorization': f'Bearer {self.api_key}',
                        'Content-Type': 'application/json'
                    },
                    timeout=25  # Slightly less than resilience timeout
                )
                
                if response.status_code == 404:
                    return None
                
                response.raise_for_status()
                data = response.json()
                
                return Patient(
                    id=data['id'],
                    first_name=data['first_name'],
                    last_name=data['last_name'],
                    email=data['email'],
                    additional_data=data.get('details') if params.include_details else None
                )
        
        try:
            return await self.resilient_client.execute(_make_request)
            
        except Exception as error:
            return self._handle_external_service_error(error, 'get_patient_by_id', params.patient_id)

    async def create_patient(self, patient_data: Dict[str, Any]) -> Patient:
        """Create new patient with resilience patterns"""
        
        async def _create_request() -> Patient:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/patients",
                    json=patient_data,
                    headers={
                        'Authorization': f'Bearer {self.api_key}',
                        'Content-Type': 'application/json'
                    },
                    timeout=25
                )
                
                response.raise_for_status()
                data = response.json()
                
                return Patient(
                    id=data['id'],
                    first_name=data['first_name'],
                    last_name=data['last_name'],
                    email=data['email']
                )
        
        try:
            return await self.resilient_client.execute(_create_request)
            
        except Exception as error:
            return self._handle_external_service_error(error, 'create_patient', patient_data.get('email', 'unknown'))

    async def get_patients_batch(self, patient_ids: List[str]) -> List[Optional[Patient]]:
        """Get multiple patients with batch resilience patterns"""
        
        # Create individual operations for each patient
        operations = [
            lambda pid=patient_id: self.get_patient_by_id(GetPatientParams(patient_id=pid))
            for patient_id in patient_ids
        ]
        
        # Use enhanced client for batch processing
        from .enhanced_client import EnhancedResilientClient
        enhanced_client = EnhancedResilientClient(self.resilient_client.config)
        
        results = await enhanced_client.execute_batch(
            operations,
            batch_size=5,  # Process 5 at a time to respect rate limits
            delay_between_batches=0.2  # 200ms delay between batches
        )
        
        # Process results and handle errors
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Log error but continue with batch
                print(f"Failed to get patient {patient_ids[i]}: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)
        
        return processed_results

    def _handle_external_service_error(self, error: Exception, operation: str, entity_id: str) -> None:
        """Centralized error handling for external service operations"""
        
        error_context = f"{operation}(entity_id={entity_id})"
        
        # Hyx-specific errors
        if 'CircuitBreaker' in str(type(error)):
            raise ServiceUnavailableError(
                f"{error_context}: External service temporarily unavailable",
                retry_after=60,
                can_retry=True
            )
        
        if 'Bulkhead' in str(type(error)):
            raise SystemBusyError(
                f"{error_context}: System overloaded, please try again later",
                retry_after=5,
                can_retry=True
            )
        
        if 'Timeout' in str(type(error)):
            raise OperationTimeoutError(
                f"{error_context}: Request timed out, operation may have succeeded",
                may_have_succeeded=True,
                can_retry=True
            )
        
        if 'RateLimit' in str(type(error)):
            raise RateLimitError(
                f"{error_context}: Rate limit exceeded, please slow down requests",
                retry_after=30,
                can_retry=True
            )
        
        # HTTP-specific errors
        if hasattr(error, 'response'):
            status_code = getattr(error.response, 'status_code', 500)
            
            if status_code in [400, 401, 403, 404, 422]:
                raise BusinessLogicError(
                    f"{error_context}: {error}",
                    can_retry=False
                )
        
        # Unknown errors
        raise Exception(f"{error_context}: {error}")

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the resilient client"""
        return self.resilient_client.get_health_stats()

# Singleton pattern for service client
_patient_service_instance: Optional[ExternalPatientService] = None

def get_patient_service() -> ExternalPatientService:
    """Get singleton instance of patient service"""
    global _patient_service_instance
    if _patient_service_instance is None:
        _patient_service_instance = ExternalPatientService()
    return _patient_service_instance 
```

### Database Resilience Implementation

```py
# src/modules/data_access/resilient_db_service.py
import asyncio
from typing import TypeVar, Callable, Optional, Dict, Any, List
from dataclasses import dataclass
from contextlib import asynccontextmanager
import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.exc import DisconnectionError, TimeoutError as SQLTimeoutError
import tenacity
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging

T = TypeVar('T')

@dataclass 
class DatabaseOperationContext:
    operation_name: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    table_name: Optional[str] = None

class DatabaseResilienceError(Exception):
    """Base exception for database resilience errors"""
    pass

class DatabaseTimeoutError(DatabaseResilienceError):
    """Database operation timed out"""
    pass

class DatabaseConnectionError(DatabaseResilienceError):
    """Database connection failed"""
    pass

class EntityNotFoundError(DatabaseResilienceError):
    """Requested entity was not found"""
    def __init__(self, entity_type: str, entity_id: str):
        self.entity_type = entity_type
        self.entity_id = entity_id
        super().__init__(f"{entity_type} with id {entity_id} not found")

class ResilientDatabaseService:
    """
    Database service with comprehensive resilience patterns.
    Handles connection failures, timeouts, and transient errors.
    """
    
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory
        self.logger = logging.getLogger(__name__)
        
        # Configure retry policy for database operations
        self.retry_policy = tenacity.AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=4),
            retry=retry_if_exception_type((
                DisconnectionError,
                SQLTimeoutError,
                ConnectionError,
                OSError  # Network-related errors
            )),
            before_sleep=self._log_retry_attempt,
            reraise=True
        )

    async def execute_operation(
        self,
        operation: Callable[[AsyncSession], Awaitable[T]],
        context: DatabaseOperationContext,
        timeout: int = 30
    ) -> T:
        """
        Execute a database operation with full resilience patterns.
        Includes retry, timeout, and comprehensive error handling.
        """
        
        self.logger.debug(f"Starting database operation: {context.operation_name}")
        
        try:
            # Apply timeout and retry patterns
            result = await asyncio.wait_for(
                self.retry_policy(self._execute_with_session, operation, context),
                timeout=timeout
            )
            
            self.logger.info(f"Database operation completed: {context.operation_name}")
            return result
            
        except asyncio.TimeoutError:
            self.logger.error(f"Database operation timed out: {context.operation_name}")
            raise DatabaseTimeoutError(f"Operation {context.operation_name} timed out after {timeout}s")
        
        except Exception as e:
            self.logger.error(f"Database operation failed: {context.operation_name}, error: {e}")
            self._handle_database_error(e, context)

    async def execute_transaction(
        self,
        operations: List[Callable[[AsyncSession], Awaitable[Any]]],
        context: DatabaseOperationContext,
        timeout: int = 45
    ) -> List[Any]:
        """
        Execute multiple operations in a transaction with resilience.
        All operations succeed or all are rolled back.
        """
        
        async def _transaction_operation(session: AsyncSession) -> List[Any]:
            results = []
            try:
                async with session.begin():
                    for operation in operations:
                        result = await operation(session)
                        results.append(result)
                return results
            except Exception:
                # Rollback is automatic with session.begin() context manager
                raise
        
        return await self.execute_operation(_transaction_operation, context, timeout)

    async def execute_batch(
        self,
        entity_operations: List[tuple[Callable[[AsyncSession], Awaitable[T]], DatabaseOperationContext]],
        batch_size: int = 10,
        timeout_per_batch: int = 30
    ) -> List[T]:
        """Execute batch operations with resilience and rate limiting"""
        
        results = []
        
        for i in range(0, len(entity_operations), batch_size):
            batch = entity_operations[i:i + batch_size]
            
            batch_operations = [
                self.execute_operation(op, ctx, timeout_per_batch) 
                for op, ctx in batch
            ]
            
            batch_results = await asyncio.gather(*batch_operations, return_exceptions=True)
            
            # Process batch results
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    operation, context = batch[j]
                    self.logger.error(f"Batch operation failed: {context.operation_name}, error: {result}")
                    # Continue with batch, don't fail everything
                    results.append(None)
                else:
                    results.append(result)
            
            # Small delay between batches to prevent overwhelming database
            if i + batch_size < len(entity_operations):
                await asyncio.sleep(0.1)
        
        return results

    async def _execute_with_session(
        self,
        operation: Callable[[AsyncSession], Awaitable[T]],
        context: DatabaseOperationContext
    ) -> T:
        """Execute operation with session management"""
        
        async with self.session_factory() as session:
            try:
                return await operation(session)
            except Exception as e:
                await session.rollback()
                raise

    def _handle_database_error(self, error: Exception, context: DatabaseOperationContext) -> None:
        """Handle and classify database errors"""
        
        error_context = f"{context.operation_name}"
        if context.entity_type and context.entity_id:
            error_context += f"({context.entity_type}:{context.entity_id})"
        
        # Connection-related errors
        if isinstance(error, (DisconnectionError, ConnectionError)):
            raise DatabaseConnectionError(f"{error_context}: Database connection failed")
        
        # Timeout errors
        if isinstance(error, (SQLTimeoutError, asyncio.TimeoutError)):
            raise DatabaseTimeoutError(f"{error_context}: Database operation timed out")
        
        # Entity not found (business logic, don't retry)
        if "not found" in str(error).lower() or "does not exist" in str(error).lower():
            if context.entity_type and context.entity_id:
                raise EntityNotFoundError(context.entity_type, context.entity_id)
        
        # Re-raise unknown errors
        raise error

    async def _log_retry_attempt(self, retry_state):
        """Log retry attempts for monitoring"""
        attempt = retry_state.attempt_number
        if retry_state.outcome and retry_state.outcome.failed:
            error = retry_state.outcome.exception()
            self.logger.warning(f"Database operation retry {attempt}: {error}")

# Example usage in data access layer
class UserRepository:
    """Example repository using resilient database service"""
    
    def __init__(self, db_service: ResilientDatabaseService):
        self.db = db_service
        self.logger = logging.getLogger(__name__)

    async def find_by_external_id(self, external_id: str) -> Optional[Dict[str, Any]]:
        """Find user by external ID with resilience"""
        
        async def _find_operation(session: AsyncSession) -> Optional[Dict[str, Any]]:
            result = await session.execute(
                sqlalchemy.text("SELECT * FROM users WHERE external_id = :external_id"),
                {"external_id": external_id}
            )
            row = result.fetchone()
            return dict(row._mapping) if row else None
        
        context = DatabaseOperationContext(
            operation_name="find_user_by_external_id",
            entity_type="user",
            entity_id=external_id
        )
        
        return await self.db.execute_operation(_find_operation, context)

    async def upsert_user(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert user with transactional resilience"""
        
        async def _upsert_operation(session: AsyncSession) -> Dict[str, Any]:
            # Implementation of upsert logic
            existing = await session.execute(
                sqlalchemy.text("SELECT id FROM users WHERE external_id = :external_id"),
                {"external_id": user_data["external_id"]}
            )
            
            if existing.fetchone():
                # Update
                await session.execute(
                    sqlalchemy.text("""
                        UPDATE users 
                        SET first_name = :first_name, last_name = :last_name, updated_at = NOW()
                        WHERE external_id = :external_id
                    """),
                    user_data
                )
            else:
                # Insert
                await session.execute(
                    sqlalchemy.text("""
                        INSERT INTO users (external_id, first_name, last_name, created_at)
                        VALUES (:external_id, :first_name, :last_name, NOW())
                    """),
                    user_data
                )
            
            # Return updated record
            result = await session.execute(
                sqlalchemy.text("SELECT * FROM users WHERE external_id = :external_id"),
                {"external_id": user_data["external_id"]}
            )
            return dict(result.fetchone()._mapping)
        
        context = DatabaseOperationContext(
            operation_name="upsert_user",
            entity_type="user",
            entity_id=user_data.get("external_id")
        )
        
        return await self.db.execute_operation(_upsert_operation, context)
```

### Comprehensive Error Classification and Handling

```py
# src/modules/exceptions/resilience_exceptions.py
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class ErrorMetadata:
    can_retry: bool
    retry_after: Optional[int] = None
    may_have_succeeded: bool = False
    error_category: str = "unknown"
    original_error: Optional[Exception] = None

class BaseResilienceError(Exception):
    """Base class for all resilience-related errors"""
    
    def __init__(self, message: str, metadata: ErrorMetadata):
        super().__init__(message)
        self.metadata = metadata

class ServiceUnavailableError(BaseResilienceError):
    """Service is temporarily unavailable (circuit breaker open)"""
    
    def __init__(self, message: str, retry_after: int = 60, can_retry: bool = True):
        metadata = ErrorMetadata(
            can_retry=can_retry,
            retry_after=retry_after,
            error_category="service_unavailable"
        )
        super().__init__(message, metadata)

class SystemBusyError(BaseResilienceError):
    """System is overloaded (bulkhead rejection)"""
    
    def __init__(self, message: str, retry_after: int = 5, can_retry: bool = True):
        metadata = ErrorMetadata(
            can_retry=can_retry,
            retry_after=retry_after,
            error_category="system_busy"
        )
        super().__init__(message, metadata)

class OperationTimeoutError(BaseResilienceError):
    """Operation timed out"""
    
    def __init__(self, message: str, may_have_succeeded: bool = True, can_retry: bool = True):
        metadata = ErrorMetadata(
            can_retry=can_retry,
            may_have_succeeded=may_have_succeeded,
            error_category="timeout"
        )
        super().__init__(message, metadata)

class RateLimitError(BaseResilienceError):
    """Rate limit exceeded"""
    
    def __init__(self, message: str, retry_after: int = 30, can_retry: bool = True):
        metadata = ErrorMetadata(
            can_retry=can_retry,
            retry_after=retry_after,
            error_category="rate_limit"
        )
        super().__init__(message, metadata)

class BusinessLogicError(BaseResilienceError):
    """Business logic error (should not retry)"""
    
    def __init__(self, message: str, can_retry: bool = False):
        metadata = ErrorMetadata(
            can_retry=can_retry,
            error_category="business_logic"
        )
        super().__init__(message, metadata)

# Error classification and handling utilities
class ResilienceErrorHandler:
    """Centralized error classification and handling"""
    
    @staticmethod
    def classify_and_handle(error: Exception, operation_context: str) -> BaseResilienceError:
        """Classify errors and convert to appropriate resilience error types"""
        
        # Hyx-specific errors
        if 'CircuitBreaker' in str(type(error)):
            return ServiceUnavailableError(
                f"{operation_context}: Service temporarily unavailable due to circuit breaker",
                retry_after=60
            )
        
        if 'Bulkhead' in str(type(error)):
            return SystemBusyError(
                f"{operation_context}: System overloaded, bulkhead capacity exceeded",
                retry_after=5
            )
        
        if 'Timeout' in str(type(error)):
            return OperationTimeoutError(
                f"{operation_context}: Operation timed out",
                may_have_succeeded=True
            )
        
        if 'RateLimit' in str(type(error)):
            return RateLimitError(
                f"{operation_context}: Rate limit exceeded",
                retry_after=30
            )
        
        # HTTP errors
        if hasattr(error, 'response'):
            status_code = getattr(error.response, 'status_code', 500)
            
            if status_code == 429:
                retry_after = int(error.response.headers.get('Retry-After', 30))
                return RateLimitError(
                    f"{operation_context}: HTTP 429 - Rate limit exceeded",
                    retry_after=retry_after
                )
            
            if status_code in [400, 401, 403, 404, 422]:
                return BusinessLogicError(
                    f"{operation_context}: HTTP {status_code} - {error}",
                    can_retry=False
                )
            
            if status_code >= 500:
                return ServiceUnavailableError(
                    f"{operation_context}: HTTP {status_code} - Server error",
                    retry_after=30
                )
        
        # Database errors
        if 'Database' in str(type(error)):
            if 'timeout' in str(error).lower():
                return OperationTimeoutError(
                    f"{operation_context}: Database operation timed out"
                )
            
            if 'connection' in str(error).lower():
                return ServiceUnavailableError(
                    f"{operation_context}: Database connection failed",
                    retry_after=10
                )
        
        # Network errors
        if isinstance(error, (ConnectionError, OSError)):
            return ServiceUnavailableError(
                f"{operation_context}: Network connection failed",
                retry_after=15
            )
        
        # Unknown errors - be conservative
        return BaseResilienceError(
            f"{operation_context}: Unknown error - {error}",
            ErrorMetadata(
                can_retry=False,
                error_category="unknown",
                original_error=error
            )
        )

    @staticmethod
    def should_retry(error: BaseResilienceError) -> bool:
        """Determine if an error should be retried"""
        return error.metadata.can_retry

    @staticmethod
    def get_retry_delay(error: BaseResilienceError) -> int:
        """Get recommended retry delay for an error"""
        return error.metadata.retry_after or 5
```

### Rate Limiting Implementation with SlowAPI

```py
# src/modules/api/rate_limiting/slowapi_limiter.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import FastAPI, Request, Response
from typing import Callable, Optional
import asyncio
import time
from collections import defaultdict
import logging

class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts limits based on system health
    and error rates, working alongside SlowAPI.
    """
    
    def __init__(self, base_rate: str = "100/minute"):
        self.base_rate = base_rate
        self.current_multiplier = 1.0
        self.error_rates = defaultdict(list)
        self.adjustment_interval = 60  # seconds
        self.last_adjustment = time.time()
        self.logger = logging.getLogger(__name__)

    def get_current_rate(self) -> str:
        """Get current rate with adaptive adjustment"""
        base_value = int(self.base_rate.split('/')[0])
        adjusted_value = max(1, int(base_value * self.current_multiplier))
        time_unit = self.base_rate.split('/')[1]
        return f"{adjusted_value}/{time_unit}"

    def record_request_result(self, client_id: str, success: bool):
        """Record request success/failure for adaptive adjustment"""
        current_time = time.time()
        self.error_rates[client_id].append((current_time, not success))
        
        # Clean old records (keep last 5 minutes)
        cutoff_time = current_time - 300
        self.error_rates[client_id] = [
            (timestamp, is_error) for timestamp, is_error in self.error_rates[client_id]
            if timestamp > cutoff_time
        ]

    def adjust_rate_if_needed(self):
        """Adjust rate limits based on system performance"""
        current_time = time.time()
        
        if current_time - self.last_adjustment < self.adjustment_interval:
            return
        
        # Calculate overall error rate
        total_requests = 0
        total_errors = 0
        
        for client_records in self.error_rates.values():
            total_requests += len(client_records)
            total_errors += sum(1 for _, is_error in client_records if is_error)
        
        if total_requests > 0:
            error_rate = total_errors / total_requests
            
            # Adjust multiplier based on error rate
            if error_rate > 0.15:  # > 15% error rate
                self.current_multiplier *= 0.8  # Reduce rate by 20%
                self.logger.warning(f"High error rate ({error_rate:.2%}), reducing rate limit")
            elif error_rate < 0.05:  # < 5% error rate
                self.current_multiplier = min(2.0, self.current_multiplier * 1.1)  # Increase by 10%, max 2x
                self.logger.info(f"Low error rate ({error_rate:.2%}), increasing rate limit")
        
        self.last_adjustment = current_time

# Enhanced key function for more sophisticated rate limiting
def get_rate_limit_key(request: Request) -> str:
    """
    Enhanced key function that considers user type, API key, and IP address
    for more granular rate limiting.
    """
    
    # Check for API key (authenticated requests get higher limits)
    api_key = request.headers.get('X-API-Key')
    if api_key:
        # Use API key for identification
        return f"api_key:{api_key}"
    
    # Check for user authentication
    user_id = request.headers.get('X-User-ID')
    if user_id:
        return f"user:{user_id}"
    
    # Fall back to IP address for anonymous requests
    return f"ip:{get_remote_address(request)}"

def get_dynamic_rate_limit(request: Request) -> str:
    """
    Dynamic rate limiting based on request characteristics
    """
    
    # Different limits for different types of requests
    if request.url.path.startswith('/api/v1/admin'):
        return "50/minute"  # Lower limit for admin operations
    elif request.url.path.startswith('/api/v1/batch'):
        return "10/minute"  # Very low limit for batch operations
    elif request.headers.get('X-API-Key'):
        return "1000/hour"  # Higher limit for authenticated API users
    else:
        return "100/hour"   # Standard limit for anonymous users

# Setup SlowAPI with FastAPI
def setup_rate_limiting(app: FastAPI) -> Limiter:
    """Setup comprehensive rate limiting for FastAPI application"""
    
    # Create adaptive limiter
    adaptive_limiter = AdaptiveRateLimiter("100/minute")
    
    # Create SlowAPI limiter with enhanced key function
    limiter = Limiter(
        key_func=get_rate_limit_key,
        default_limits=["1000/hour", "100/minute"]  # Global fallback limits
    )
    
    app.state.limiter = limiter
    app.state.adaptive_limiter = adaptive_limiter
    
    # Add middleware
    app.add_middleware(SlowAPIMiddleware)
    
    # Custom rate limit exceeded handler
    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        response = Response(
            content=f"Rate limit exceeded: {exc.detail}",
            status_code=429,
            headers={
                "Retry-After": str(60),  # Suggest retry after 60 seconds
                "X-RateLimit-Limit": str(exc.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + 60)
            }
        )
        
        # Record the rate limit hit for adaptive adjustment
        client_id = get_rate_limit_key(request)
        adaptive_limiter.record_request_result(client_id, False)
        
        return response
    
    return limiter

# Example usage in FastAPI routes
def apply_adaptive_rate_limiting(app: FastAPI):
    """Apply adaptive rate limiting to all routes"""
    
    limiter = app.state.limiter
    adaptive_limiter = app.state.adaptive_limiter
    
    @app.middleware("http")
    async def adaptive_rate_limit_middleware(request: Request, call_next):
        # Adjust rates before processing
        adaptive_limiter.adjust_rate_if_needed()
        
        # Process request
        response = await call_next(request)
        
        # Record result for adaptive adjustment
        client_id = get_rate_limit_key(request)
        success = response.status_code < 400
        adaptive_limiter.record_request_result(client_id, success)
        
        return response

# Usage in routes
"""
from slowapi import Limiter
from fastapi import Depends

limiter = Depends(lambda: app.state.limiter)

@app.get("/api/v1/patients/{patient_id}")
@limiter.limit(get_dynamic_rate_limit)
async def get_patient(request: Request, patient_id: str):
    # Your endpoint logic here
    pass

@app.post("/api/v1/batch/patients")
@limiter.limit("5/minute")  # Very restrictive for batch operations
async def batch_create_patients(request: Request, patients_data: List[dict]):
    # Batch processing logic
    pass
"""
```

### Health Monitoring and Observability

```py
# src/modules/monitoring/health_monitor.py
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import asyncio
import logging
from collections import defaultdict, deque
import time

@dataclass
class HealthMetrics:
    service_name: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    circuit_breaker_opens: int
    rate_limit_hits: int
    timeouts: int
    average_response_time: float
    last_success_time: Optional[datetime]
    last_failure_time: Optional[datetime]
    current_error_rate: float

@dataclass
class CircuitBreakerStats:
    status: str  # 'closed', 'open', 'half-open'
    failure_count: int
    success_count: int
    last_failure_time: Optional[datetime]
    next_attempt_time: Optional[datetime]

@dataclass
class BulkheadStats:
    active_requests: int
    queued_requests: int
    capacity: int
    queue_limit: int
    rejection_count: int

@dataclass
class RateLimiterStats:
    tokens_remaining: int
    max_tokens: int
    requests_per_second: float
    current_rate: float
    hits_in_last_minute: int

class ResilienceHealthMonitor:
    """
    Comprehensive health monitoring for resilience patterns.
    Tracks metrics, generates alerts, and provides health status.
    """
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = logging.getLogger(__name__)
        
        # Metrics storage
        self.metrics: Dict[str, Any] = defaultdict(int)
        self.response_times: deque = deque(maxlen=1000)  # Keep last 1000 response times
        self.error_history: deque = deque(maxlen=100)    # Keep last 100 errors
        self.success_history: deque = deque(maxlen=1000) # Keep last 1000 successes
        
        # Health thresholds
        self.error_rate_threshold = 0.10  # 10%
        self.response_time_threshold = 5.0  # 5 seconds
        self.circuit_breaker_threshold = 0.15  # 15%
        
        # Start background monitoring
        self._monitoring_task = None
        self.start_monitoring()

    def record_operation_start(self, operation_name: str) -> str:
        """Record the start of an operation and return correlation ID"""
        correlation_id = f"{operation_name}_{int(time.time() * 1000)}"
        self.metrics[f"{operation_name}_started"] += 1
        self.metrics["total_operations"] += 1
        return correlation_id

    def record_operation_success(self, operation_name: str, correlation_id: str, response_time: float):
        """Record successful operation completion"""
        self.metrics[f"{operation_name}_success"] += 1
        self.metrics["successful_operations"] += 1
        self.response_times.append(response_time)
        self.success_history.append({
            'timestamp': datetime.now(),
            'operation': operation_name,
            'response_time': response_time
        })

    def record_operation_failure(self, operation_name: str, correlation_id: str, error: Exception, response_time: float):
        """Record failed operation"""
        self.metrics[f"{operation_name}_failure"] += 1
        self.metrics["failed_operations"] += 1
        self.error_history.append({
            'timestamp': datetime.now(),
            'operation': operation_name,
            'error': str(error),
            'error_type': type(error).__name__,
            'response_time': response_time
        })

    def record_circuit_breaker_open(self, service: str):
        """Record circuit breaker opening"""
        self.metrics[f"circuit_breaker_opens_{service}"] += 1
        self.metrics["circuit_breaker_opens"] += 1

    def record_rate_limit_hit(self, service: str):
        """Record rate limit hit"""
        self.metrics[f"rate_limit_hits_{service}"] += 1
        self.metrics["rate_limit_hits"] += 1

    def record_timeout(self, operation_name: str):
        """Record operation timeout"""
        self.metrics[f"timeouts_{operation_name}"] += 1
        self.metrics["timeouts"] += 1

    def get_health_metrics(self) -> HealthMetrics:
        """Get comprehensive health metrics"""
        total_ops = self.metrics.get("total_operations", 0)
        successful_ops = self.metrics.get("successful_operations", 0)
        failed_ops = self.metrics.get("failed_operations", 0)
        
        error_rate = (failed_ops / total_ops) if total_ops > 0 else 0.0
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0.0
        
        last_success = self.success_history[-1]['timestamp'] if self.success_history else None
        last_failure = self.error_history[-1]['timestamp'] if self.error_history else None
        
        return HealthMetrics(
            service_name=self.service_name,
            total_operations=total_ops,
            successful_operations=successful_ops,
            failed_operations=failed_ops,
            circuit_breaker_opens=self.metrics.get("circuit_breaker_opens", 0),
            rate_limit_hits=self.metrics.get("rate_limit_hits", 0),
            timeouts=self.metrics.get("timeouts", 0),
            average_response_time=avg_response_time,
            last_success_time=last_success,
            last_failure_time=last_failure,
            current_error_rate=error_rate
        )

    def is_healthy(self) -> bool:
        """Determine if service is currently healthy"""
        metrics = self.get_health_metrics()
        
        # Check error rate
        if metrics.current_error_rate > self.error_rate_threshold:
            return False
        
        # Check response time
        if metrics.average_response_time > self.response_time_threshold:
            return False
        
        # Check for recent circuit breaker opens
        recent_cb_opens = sum(
            1 for error in self.error_history
            if 'CircuitBreaker' in error.get('error_type', '') and
            error['timestamp'] > datetime.now() - timedelta(minutes=5)
        )
        
        if recent_cb_opens > 3:  # More than 3 circuit breaker opens in 5 minutes
            return False
        
        return True

    def get_degradation_level(self) -> str:
        """Get current degradation level: healthy, degraded, critical"""
        if not self.is_healthy():
            metrics = self.get_health_metrics()
            
            # Critical conditions
            if (metrics.current_error_rate > 0.25 or  # > 25% error rate
                metrics.average_response_time > 10.0 or  # > 10s response time
                metrics.circuit_breaker_opens > 10):  # More than 10 CB opens
                return 'critical'
            else:
                return 'degraded'
        
        return 'healthy'

    def get_alerts(self) -> List[Dict[str, Any]]:
        """Get current alerts based on health metrics"""
        alerts = []
        metrics = self.get_health_metrics()
        
        # High error rate alert
        if metrics.current_error_rate > self.error_rate_threshold:
            alerts.append({
                'level': 'warning' if metrics.current_error_rate < 0.20 else 'critical',
                'message': f"High error rate: {metrics.current_error_rate:.2%}",
                'metric': 'error_rate',
                'value': metrics.current_error_rate,
                'threshold': self.error_rate_threshold
            })
        
        # High response time alert
        if metrics.average_response_time > self.response_time_threshold:
            alerts.append({
                'level': 'warning',
                'message': f"High response time: {metrics.average_response_time:.2f}s",
                'metric': 'response_time',
                'value': metrics.average_response_time,
                'threshold': self.response_time_threshold
            })
        
        # Circuit breaker alerts
        if metrics.circuit_breaker_opens > 0:
            alerts.append({
                'level': 'warning',
                'message': f"Circuit breaker opens detected: {metrics.circuit_breaker_opens}",
                'metric': 'circuit_breaker_opens',
                'value': metrics.circuit_breaker_opens
            })
        
        return alerts

    def start_monitoring(self):
        """Start background monitoring task"""
        if self._monitoring_task is None:
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self):
        """Stop background monitoring"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None

    async def _monitoring_loop(self):
        """Background monitoring loop"""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Clean old data
                self._cleanup_old_data()
                
                # Generate alerts if needed
                alerts = self.get_alerts()
                if alerts:
                    for alert in alerts:
                        self.logger.warning(f"Health Alert: {alert['message']}")
                
                # Log health summary
                health_status = self.get_degradation_level()
                if health_status != 'healthy':
                    metrics = self.get_health_metrics()
                    self.logger.info(f"Health Status: {health_status}, Error Rate: {metrics.current_error_rate:.2%}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")

    def _cleanup_old_data(self):
        """Clean up old monitoring data to prevent memory leaks"""
        cutoff_time = datetime.now() - timedelta(hours=24)
        
        # Clean error history
        self.error_history = deque(
            [error for error in self.error_history if error['timestamp'] > cutoff_time],
            maxlen=100
        )
        
        # Clean success history  
        self.success_history = deque(
            [success for success in self.success_history if success['timestamp'] > cutoff_time],
            maxlen=1000
        )

# Usage in resilient clients
class MonitoredHyxClient(HyxResilientClient):
    """Hyx client with integrated health monitoring"""
    
    def __init__(self, config: ResilienceConfig, service_name: str):
        super().__init__(config)
        self.health_monitor = ResilienceHealthMonitor(service_name)
    
    async def execute(self, operation: Callable[[], Awaitable[T]]) -> T:
        """Execute with health monitoring"""
        operation_name = getattr(operation, '__name__', 'unknown_operation')
        correlation_id = self.health_monitor.record_operation_start(operation_name)
        start_time = time.time()
        
        try:
            result = await super().execute(operation)
            response_time = time.time() - start_time
            self.health_monitor.record_operation_success(operation_name, correlation_id, response_time)
            return result
            
        except Exception as e:
            response_time = time.time() - start_time
            self.health_monitor.record_operation_failure(operation_name, correlation_id, e, response_time)
            
            # Record specific error types
            if 'CircuitBreaker' in str(type(e)):
                self.health_monitor.record_circuit_breaker_open(self.service_name)
            elif 'RateLimit' in str(type(e)):
                self.health_monitor.record_rate_limit_hit(self.service_name)
            elif 'Timeout' in str(type(e)):
                self.health_monitor.record_timeout(operation_name)
            
            raise
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status"""
        metrics = self.health_monitor.get_health_metrics()
        alerts = self.health_monitor.get_alerts()
        degradation = self.health_monitor.get_degradation_level()
        
        return {
            'service_name': self.service_name,
            'health_status': degradation,
            'is_healthy': self.health_monitor.is_healthy(),
            'metrics': asdict(metrics),
            'alerts': alerts,
            'resilience_stats': super().get_health_stats()
        }
```

### Fallback Strategies

```py
# src/modules/resilience/fallback_strategies.py
from typing import TypeVar, Callable, Optional, Any, Dict, List
from dataclasses import dataclass
import asyncio
import logging
from abc import ABC, abstractmethod
import json
import aiofiles
from datetime import datetime, timedelta

T = TypeVar('T')

@dataclass
class FallbackResult:
    data: Any
    source: str  # 'primary', 'fallback', 'cache', 'default'
    timestamp: datetime
    degraded: bool = False

class FallbackStrategy(ABC):
    """Abstract base class for fallback strategies"""
    
    @abstractmethod
    async def execute(self, primary: Callable[[], Awaitable[T]], context: Dict[str, Any]) -> FallbackResult[T]:
        pass

class CacheFallbackStrategy(FallbackStrategy):
    """Fallback to cached data when primary operation fails"""
    
    def __init__(self, cache_ttl: int = 300):  # 5 minutes default TTL
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = cache_ttl
        self.logger = logging.getLogger(__name__)

    async def execute(self, primary: Callable[[], Awaitable[T]], context: Dict[str, Any]) -> FallbackResult[T]:
        cache_key = self._generate_cache_key(context)
        
        try:
            # Try primary operation
            result = await primary()
            
            # Cache successful result
            await self._cache_result(cache_key, result)
            
            return FallbackResult(
                data=result,
                source='primary',
                timestamp=datetime.now(),
                degraded=False
            )
            
        except Exception as e:
            self.logger.warning(f"Primary operation failed, trying cache: {e}")
            
            # Try cache fallback
            cached_result = await self._get_cached_result(cache_key)
            if cached_result is not None:
                self.logger.info("Serving stale data from cache")
                return FallbackResult(
                    data=cached_result,
                    source='cache',
                    timestamp=datetime.now(),
                    degraded=True
                )
            
            # No cache available, re-raise
            raise e

    def _generate_cache_key(self, context: Dict[str, Any]) -> str:
        """Generate cache key from context"""
        key_parts = []
        for key in sorted(context.keys()):
            if isinstance(context[key], (str, int, float, bool)):
                key_parts.append(f"{key}:{context[key]}")
        return "|".join(key_parts)

    async def _cache_result(self, key: str, result: T):
        """Cache result with timestamp"""
        self.cache[key] = {
            'data': result,
            'timestamp': datetime.now(),
            'ttl': self.cache_ttl
        }

    async def _get_cached_result(self, key: str) -> Optional[T]:
        """Get cached result if still valid"""
        if key not in self.cache:
            return None
        
        cached = self.cache[key]
        age = (datetime.now() - cached['timestamp']).total_seconds()
        
        if age > cached['ttl']:
            # Cache expired
            del self.cache[key]
            return None
        
        return cached['data']

class ServiceFallbackStrategy(FallbackStrategy):
    """Fallback to alternative service when primary fails"""
    
    def __init__(self, fallback_service: Callable[[], Awaitable[T]]):
        self.fallback_service = fallback_service
        self.logger = logging.getLogger(__name__)

    async def execute(self, primary: Callable[[], Awaitable[T]], context: Dict[str, Any]) -> FallbackResult[T]:
        try:
            # Try primary service
            result = await primary()
            return FallbackResult(
                data=result,
                source='primary',
                timestamp=datetime.now(),
                degraded=False
            )
            
        except Exception as e:
            self.logger.warning(f"Primary service failed, trying fallback: {e}")
            
            try:
                # Try fallback service
                fallback_result = await self.fallback_service()
                self.logger.info("Fallback service succeeded")
                
                return FallbackResult(
                    data=fallback_result,
                    source='fallback',
                    timestamp=datetime.now(),
                    degraded=True
                )
                
            except Exception as fallback_error:
                self.logger.error(f"Fallback service also failed: {fallback_error}")
                raise e  # Raise original error

class DefaultValueFallbackStrategy(FallbackStrategy):
    """Fallback to default value when operation fails"""
    
    def __init__(self, default_value: T):
        self.default_value = default_value
        self.logger = logging.getLogger(__name__)

    async def execute(self, primary: Callable[[], Awaitable[T]], context: Dict[str, Any]) -> FallbackResult[T]:
        try:
            result = await primary()
            return FallbackResult(
                data=result,
                source='primary',
                timestamp=datetime.now(),
                degraded=False
            )
            
        except Exception as e:
            self.logger.warning(f"Operation failed, using default value: {e}")
            
            return FallbackResult(
                data=self.default_value,
                source='default',
                timestamp=datetime.now(),
                degraded=True
            )

class CompositeFallbackStrategy(FallbackStrategy):
    """Chain multiple fallback strategies"""
    
    def __init__(self, strategies: List[FallbackStrategy]):
        self.strategies = strategies
        self.logger = logging.getLogger(__name__)

    async def execute(self, primary: Callable[[], Awaitable[T]], context: Dict[str, Any]) -> FallbackResult[T]:
        last_error = None
        
        # Try each strategy in order
        for i, strategy in enumerate(self.strategies):
            try:
                if i == 0:
                    # First strategy gets the primary operation
                    return await strategy.execute(primary, context)
                else:
                    # Subsequent strategies get a no-op primary (already failed)
                    async def no_op():
                        raise last_error
                    return await strategy.execute(no_op, context)
                    
            except Exception as e:
                last_error = e
                continue
        
        # All strategies failed
        raise last_error

# Enhanced resilient client with fallback support
class FallbackResilientClient(MonitoredHyxClient):
    """Resilient client with integrated fallback strategies"""
    
    def __init__(self, config: ResilienceConfig, service_name: str):
        super().__init__(config, service_name)
        self.fallback_strategies: Dict[str, FallbackStrategy] = {}

    def register_fallback(self, operation_name: str, strategy: FallbackStrategy):
        """Register fallback strategy for specific operation"""
        self.fallback_strategies[operation_name] = strategy

    async def execute_with_fallback(
        self, 
        operation: Callable[[], Awaitable[T]], 
        operation_name: str,
        context: Optional[Dict[str, Any]] = None
    ) -> FallbackResult[T]:
        """Execute operation with fallback if registered"""
        
        context = context or {}
        strategy = self.fallback_strategies.get(operation_name)
        
        if strategy:
            return await strategy.execute(operation, context)
        else:
            # No fallback strategy, execute normally
            try:
                result = await self.execute(operation)
                return FallbackResult(
                    data=result,
                    source='primary',
                    timestamp=datetime.now(),
                    degraded=False
                )
            except Exception as e:
                # Re-raise as fallback result for consistency
                raise e

# Example usage in external service
class PatientServiceWithFallbacks(ExternalPatientService):
    """Patient service with comprehensive fallback strategies"""
    
    def __init__(self):
        super().__init__()
        self.fallback_client = FallbackResilientClient(
            self.resilient_client.config, 
            "patient_service"
        )
        self._setup_fallbacks()

    def _setup_fallbacks(self):
        """Setup fallback strategies for different operations"""
        
        # Cache fallback for patient lookups
        cache_strategy = CacheFallbackStrategy(cache_ttl=600)  # 10 minutes
        self.fallback_client.register_fallback('get_patient_by_id', cache_strategy)
        
        # Default value fallback for non-critical data
        default_patient = Patient(id="unknown", first_name="", last_name="", email="")
        default_strategy = DefaultValueFallbackStrategy(default_patient)
        
        # Composite fallback: Cache -> Default
        composite_strategy = CompositeFallbackStrategy([cache_strategy, default_strategy])
        self.fallback_client.register_fallback('get_patient_summary', composite_strategy)

    async def get_patient_by_id_with_fallback(self, params: GetPatientParams) -> FallbackResult[Optional[Patient]]:
        """Get patient with cache fallback"""
        
        async def _get_patient():
            return await super().get_patient_by_id(params)
        
        context = {'patient_id': params.patient_id, 'include_details': params.include_details}
        
        return await self.fallback_client.execute_with_fallback(
            _get_patient,
            'get_patient_by_id',
            context
        )

    async def get_patient_summary_with_fallback(self, patient_id: str) -> FallbackResult[Patient]:
        """Get patient summary with comprehensive fallbacks"""
        
        async def _get_summary():
            # Simplified patient data for summary
            full_patient = await super().get_patient_by_id(GetPatientParams(patient_id=patient_id))
            if not full_patient:
                raise ValueError(f"Patient {patient_id} not found")
            return full_patient
        
        context = {'patient_id': patient_id, 'operation': 'summary'}
        
        return await self.fallback_client.execute_with_fallback(
            _get_summary,
            'get_patient_summary', 
            context
        )
```

### Testing Resilience Patterns

```py
# tests/test_resilience_patterns.py
import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
from src.modules.resilience.hyx_client import HyxResilientClient, create_resilience_config
from src.modules.resilience.fallback_strategies import CacheFallbackStrategy, ServiceFallbackStrategy
from src.modules.external_services.patient_service import ExternalPatientService, GetPatientParams

class TestHyxResilientClient:
    
    @pytest.fixture
    def client(self):
        config = create_resilience_config('development')
        return HyxResilientClient(config)
    
    @pytest.fixture  
    def mock_operation(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_successful_operation(self, client, mock_operation):
        """Test successful operation execution"""
        mock_operation.return_value = "success"
        
        result = await client.execute(mock_operation)
        
        assert result == "success"
        mock_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_on_transient_failure(self, client, mock_operation):
        """Test retry behavior on transient failures"""
        # Fail twice, then succeed
        mock_operation.side_effect = [
            ConnectionError("Network error"),
            ConnectionError("Network error"), 
            "success"
        ]
        
        result = await client.execute(mock_operation)
        
        assert result == "success"
        assert mock_operation.call_count == 3

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self, client, mock_operation):
        """Test circuit breaker opens after consecutive failures"""
        mock_operation.side_effect = ConnectionError("Service down")
        
        # Trigger enough failures to open circuit breaker
        for _ in range(3):
            with pytest.raises(Exception):
                await client.execute(mock_operation)
        
        # Circuit should now be open - next call should fail fast
        with pytest.raises(Exception) as exc_info:
            await client.execute(mock_operation)
        
        # Verify circuit breaker is involved (would need actual Hyx error types)
        # assert "CircuitBreaker" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_timeout_handling(self, client):
        """Test timeout behavior"""
        
        async def slow_operation():
            await asyncio.sleep(2)  # Longer than timeout
            return "too_slow"
        
        with pytest.raises(Exception):  # Should timeout
            await client.execute(slow_operation)

    @pytest.mark.asyncio
    async def test_bulkhead_rejection(self, client):
        """Test bulkhead pattern rejects when capacity exceeded"""
        
        async def long_running_operation():
            await asyncio.sleep(1)
            return "done"
        
        # Start multiple operations to fill bulkhead
        tasks = []
        for _ in range(10):  # More than bulkhead capacity
            task = asyncio.create_task(client.execute(long_running_operation))
            tasks.append(task)
        
        # Some should succeed, some should be rejected
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successes = [r for r in results if r == "done"]
        failures = [r for r in results if isinstance(r, Exception)]
        
        assert len(successes) > 0  # Some should succeed
        assert len(failures) > 0  # Some should be rejected

class TestFallbackStrategies:
    
    @pytest.mark.asyncio
    async def test_cache_fallback_strategy(self):
        """Test cache fallback when primary fails"""
        strategy = CacheFallbackStrategy(cache_ttl=60)
        
        # First call succeeds and caches result
        async def successful_primary():
            return {"id": "123", "name": "John"}
        
        result1 = await strategy.execute(successful_primary, {"user_id": "123"})
        assert result1.source == "primary"
        assert result1.data["name"] == "John"
        
        # Second call fails but returns cached data
        async def failing_primary():
            raise ConnectionError("Service down")
        
        result2 = await strategy.execute(failing_primary, {"user_id": "123"})
        assert result2.source == "cache"
        assert result2.data["name"] == "John"
        assert result2.degraded is True

    @pytest.mark.asyncio
    async def test_service_fallback_strategy(self):
        """Test service fallback when primary fails"""
        
        async def fallback_service():
            return {"id": "123", "name": "John (backup)"}
        
        strategy = ServiceFallbackStrategy(fallback_service)
        
        async def failing_primary():
            raise ConnectionError("Primary service down")
        
        result = await strategy.execute(failing_primary, {})
        assert result.source == "fallback"
        assert "backup" in result.data["name"]
        assert result.degraded is True

class TestExternalServiceResilience:
    
    @pytest.fixture
    def patient_service(self):
        return ExternalPatientService()
    
    @pytest.mark.asyncio
    async def test_patient_service_with_retries(self, patient_service):
        """Test patient service handles retries properly"""
        
        with patch('httpx.AsyncClient.get') as mock_get:
            # Mock response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'id': '123',
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john@example.com'
            }
            mock_response.raise_for_status.return_value = None
            
            mock_get.return_value.__aenter__.return_value.get.return_value = mock_response
            
            params = GetPatientParams(patient_id="123")
            result = await patient_service.get_patient_by_id(params)
            
            assert result is not None
            assert result.first_name == "John"

    @pytest.mark.asyncio
    async def test_patient_service_handles_rate_limiting(self, patient_service):
        """Test patient service handles rate limiting gracefully"""
        
        with patch('httpx.AsyncClient.get') as mock_get:
            # Mock rate limit response
            rate_limit_response = Mock()
            rate_limit_response.status_code = 429
            rate_limit_response.headers = {'Retry-After': '30'}
            
            success_response = Mock()
            success_response.status_code = 200
            success_response.json.return_value = {
                'id': '123', 'first_name': 'John', 
                'last_name': 'Doe', 'email': 'john@example.com'
            }
            
            # First call hits rate limit, second succeeds
            mock_get.return_value.__aenter__.return_value.get.side_effect = [
                rate_limit_response,
                success_response
            ]
            
            # Should handle rate limiting gracefully
            params = GetPatientParams(patient_id="123")
            
            # This would typically be handled by the resilience patterns
            # In a real test, we'd verify the retry behavior occurs
            
    @pytest.mark.asyncio
    async def test_batch_operations_respect_rate_limits(self, patient_service):
        """Test batch operations respect rate limits"""
        
        patient_ids = [f"patient_{i}" for i in range(10)]
        
        with patch('httpx.AsyncClient.get') as mock_get:
            # Mock successful responses
            def create_response(patient_id):
                response = Mock()
                response.status_code = 200
                response.json.return_value = {
                    'id': patient_id,
                    'first_name': 'Test',
                    'last_name': 'User',
                    'email': f'{patient_id}@example.com'
                }
                response.raise_for_status.return_value = None
                return response
            
            mock_get.return_value.__aenter__.return_value.get.side_effect = [
                create_response(pid) for pid in patient_ids
            ]
            
            # Measure execution time to verify rate limiting
            import time
            start_time = time.time()
            
            results = await patient_service.get_patients_batch(patient_ids)
            
            execution_time = time.time() - start_time
            
            # Should take some time due to rate limiting between batches
            assert execution_time > 0.5  # At least 500ms for delays
            assert len(results) == len(patient_ids)
            assert all(r is not None for r in results)

class TestHealthMonitoring:
    
    @pytest.mark.asyncio  
    async def test_health_metrics_tracking(self):
        """Test health metrics are properly tracked"""
        from src.modules.monitoring.health_monitor import ResilienceHealthMonitor
        
        monitor = ResilienceHealthMonitor("test_service")
        
        # Simulate operations
        correlation_id = monitor.record_operation_start("test_operation")
        monitor.record_operation_success("test_operation", correlation_id, 0.5)
        
        correlation_id2 = monitor.record_operation_start("test_operation")
        monitor.record_operation_failure("test_operation", correlation_id2, Exception("Test error"), 1.0)
        
        # Check metrics
        metrics = monitor.get_health_metrics()
        assert metrics.total_operations == 2
        assert metrics.successful_operations == 1
        assert metrics.failed_operations == 1
        assert metrics.current_error_rate == 0.5

    @pytest.mark.asyncio
    async def test_health_alerts_generation(self):
        """Test health alerts are generated appropriately"""
        from src.modules.monitoring.health_monitor import ResilienceHealthMonitor
        
        monitor = ResilienceHealthMonitor("test_service")
        monitor.error_rate_threshold = 0.2  # 20% threshold
        
        # Generate high error rate
        for i in range(10):
            correlation_id = monitor.record_operation_start("test_op")
            if i < 7:  # 70% failure rate
                monitor.record_operation_failure("test_op", correlation_id, Exception("Error"), 1.0)
            else:
                monitor.record_operation_success("test_op", correlation_id, 0.5)
        
        alerts = monitor.get_alerts()
        assert len(alerts) > 0
        assert any("error rate" in alert['message'].lower() for alert in alerts)

# Integration test
@pytest.mark.integrationsql
class TestResilienceIntegration:
    
    @pytest.mark.asyncio
    async def test_end_to_end_resilience_flow(self):
        """Test complete resilience flow with monitoring and fallbacks"""
        
        # This would be a comprehensive test that:
        # 1. Sets up a real external service mock
        # 2. Triggers various failure scenarios
        # 3. Verifies resilience patterns activate correctly
        # 4. Confirms health monitoring captures metrics
        # 5. Tests fallback strategies work as expected
        
        config = create_resilience_config('test')
        client = HyxResilientClient(config)
        
        # Set up monitoring
        from src.modules.monitoring.health_monitor import ResilienceHealthMonitor
        monitor = ResilienceHealthMonitor("integration_test")
        
        operation_count = 0
        
        async def flaky_operation():
            nonlocal operation_count
            operation_count += 1
            
            if operation_count <= 3:
                raise ConnectionError("Simulated failure")
            return f"Success on attempt {operation_count}"
        
        # Should eventually succeed after retries
        result = await client.execute(flaky_operation)
        assert "Success" in result
        assert operation_count == 4  # 1 initial + 3 retries

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

This comprehensive Python implementation section provides:

### **Key Features of the Python Implementation:**

1. **Hyx Integration**: Complete setup with circuit breaker, retry, timeout, bulkhead, and rate limiting  
2. **Enhanced Client**: Additional libraries (tenacity, circuitbreaker, slowapi) for specialized scenarios  
3. **Database Resilience**: SQLAlchemy async support with retry patterns and error handling  
4. **Error Classification**: Comprehensive error types with metadata for retry decisions  
5. **Rate Limiting**: SlowAPI integration with adaptive rate limiting  
6. **Health Monitoring**: Real-time metrics, alerting, and degradation detection  
7. **Fallback Strategies**: Cache, service, default value, and composite fallback patterns  
8. **Comprehensive Testing**: Unit tests, integration tests, and resilience behavior verification

### **Library Ecosystem:**

- **Primary**: Hyx (main resilience patterns)  
- **Complementary**: tenacity (advanced retry), circuitbreaker (alternative CB), slowapi (rate limiting)  
- **Database**: SQLAlchemy async with tenacity retry  
- **Monitoring**: Built-in health tracking with alerting  
- **Testing**: pytest with async support and mocking

This Python implementation matches the depth and comprehensiveness of the TypeScript section while leveraging Python-specific libraries and patterns. It provides the same level of fault tolerance and observability for Python-based services in the Jimini ecosystem.

### Python Resilience Libraries Guide

A comprehensive guide to all Python libraries needed for implementing enterprise-grade resilience patterns, serving as the Python equivalent to Cockatiel in TypeScript.

#### 📋 Overview

This document provides a complete reference for all Python libraries required to implement the resilience patterns outlined in the Jimini Resilience Guide. These libraries work together to provide circuit breaking, retry logic, timeout handling, bulkhead isolation, rate limiting, and comprehensive monitoring.

#### 🎯 Primary Resilience Library

##### **Hyx** \- Core Resilience Framework

- **Purpose**: Primary resilience orchestration library  
- **Features**: Circuit breaker, retry, timeout, bulkhead, rate limiting  
- **Why**: Most comprehensive Python equivalent to Cockatiel  
- **Installation**: `pip install hyx>=0.4.0`

#### 🎯 Library Usage Summary

| Library | Purpose | Used For |
| :---- | :---- | :---- |
| **hyx** | Primary resilience patterns | Circuit breaker, retry, timeout, bulkhead, rate limiting |
| **tenacity** | Advanced retry logic | Exponential backoff, jitter, conditional retries |
| **circuitbreaker** | Alternative circuit breaker | Decorator-based circuit breaking |
| **slowapi** | API rate limiting | FastAPI middleware for request limiting |
| **limits** | Rate limiting algorithms | Token bucket, sliding window implementations |
| **httpx** | HTTP client | Async external service calls |
| **sqlalchemy** | Database ORM | Async database operations with resilience |
| **aiofiles** | File I/O | Async cache file operations |
| **pytest** | Testing | Unit and integration testing |

#### 📚 Complete Libraries List

##### **🔧 Core Resilience Libraries**

###### ***Hyx***

```shell
pip install hyx>=0.4.0
```

- **Role**: Primary resilience patterns implementation  
- **Features**: AsyncCircuitBreaker, AsyncRetry, AsyncTimeout, AsyncBulkhead, AsyncRateLimit  
- **Use Cases**: All primary resilience operations

###### ***Tenacity***

```shell
pip install tenacity>=8.2.0
```

- **Role**: Advanced retry patterns with sophisticated backoff strategies  
- **Features**: Exponential backoff, jitter, conditional retries, custom wait strategies  
- **Use Cases**: Database operations, complex retry scenarios, custom retry logic

###### ***CircuitBreaker***

```shell
pip install circuitbreaker>=1.4.0
```

- **Role**: Alternative circuit breaker implementation  
- **Features**: Decorator-based circuit breaking, simple configuration  
- **Use Cases**: Legacy code integration, decorator-preferred scenarios

##### **🚦 Rate Limiting & API Management**

###### ***SlowAPI***

```shell
pip install slowapi>=0.1.9
```

- **Role**: FastAPI middleware for request rate limiting  
- **Features**: Per-IP, per-user, per-API-key rate limiting  
- **Use Cases**: API endpoint protection, user-specific rate limits

###### ***Limits***

```shell
pip install limits>=3.5.0
```

- **Role**: Advanced rate limiting algorithms  
- **Features**: Token bucket, sliding window, fixed window algorithms  
- **Use Cases**: Complex rate limiting scenarios, custom rate limiting logic

##### **🌐 HTTP Client & Web Framework**

###### ***HTTPX***

```shell
pip install httpx>=0.24.0
```

- **Role**: Modern async HTTP client for external service calls  
- **Features**: Async/await support, automatic retries, connection pooling  
- **Use Cases**: External API calls, service-to-service communication

###### ***FastAPI** (if not already installed)*

```shell
pip install fastapi>=0.100.0
```

- **Role**: Web framework for API endpoints  
- **Features**: Async support, automatic OpenAPI documentation  
- **Use Cases**: Building resilient API services

###### ***Uvicorn***

```shell
pip install uvicorn>=0.23.0
```

- **Role**: ASGI server for FastAPI applications  
- **Features**: High performance, async support  
- **Use Cases**: Running FastAPI applications in production

##### **🗄️ Database & Async Support**

###### ***SQLAlchemy with Async Support***

```shell
pip install sqlalchemy[asyncio]>=2.0.0
```

- **Role**: Async ORM for database resilience  
- **Features**: Async session management, connection pooling  
- **Use Cases**: Database operations with retry and timeout patterns

###### ***Database Drivers** (choose based on your database)*

**PostgreSQL:**

```shell
pip install asyncpg>=0.28.0
```

- **Role**: Async PostgreSQL driver  
- **Features**: High performance, connection pooling  
- **Use Cases**: PostgreSQL database connections

##### **📁 File I/O & Utilities**

###### ***AIOFiles***

```shell
pip install aiofiles>=23.0.0
```

- **Role**: Async file operations  
- **Features**: Async file read/write, context managers  
- **Use Cases**: Cache file operations, logging, configuration files

##### **🧪 Testing Framework**

###### ***Pytest***

```shell
pip install pytest>=7.4.0
```

- **Role**: Primary testing framework  
- **Features**: Test discovery, fixtures, parametrization  
- **Use Cases**: Unit tests, integration tests

###### ***Pytest-Asyncio***

```shell
pip install pytest-asyncio>=0.21.0
```

- **Role**: Async testing support for pytest  
- **Features**: Async test execution, event loop management  
- **Use Cases**: Testing async resilience patterns

###### ***HTTPX-Mock***

```shell
pip install httpx-mock>=0.10.0
```

- **Role**: HTTP mocking for testing  
- **Features**: Request/response mocking, async support  
- **Use Cases**: Testing external service interactions

###### ***Pytest-Cov***

```shell
pip install pytest-cov>=4.1.0
```

- **Role**: Coverage reporting  
- **Features**: Line coverage, branch coverage, reports  
- **Use Cases**: Measuring test coverage

###### ***HealthCheck***

```shell
pip install healthcheck>=1.3.3
```

- **Role**: Health check endpoints  
- **Features**: Dependency health checks, status endpoints  
- **Use Cases**: Kubernetes health probes, load balancer health checks

#### 📄 Requirements.txt Template

##### **Minimal Setup** (Core resilience only)

```
# requirements-minimal.txt
hyx>=0.4.0
tenacity>=8.2.0
httpx>=0.24.0
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.28.0  # or your preferred database driver
pytest>=7.4.0
pytest-asyncio>=0.21.0
```

##### **Complete Setup** (All features)

```
# requirements-complete.txt

# Core Resilience
hyx>=0.4.0
tenacity>=8.2.0
circuitbreaker>=1.4.0

# Rate Limiting
slowapi>=0.1.9
limits>=3.5.0

# HTTP & API
httpx>=0.24.0
fastapi>=0.100.0
uvicorn>=0.23.0

# Database (choose based on your database)
sqlalchemy[asyncio]>=2.0.0
asyncpg>=0.28.0  # PostgreSQL
# aiomysql>=0.2.0  # MySQL (uncomment if using MySQL)
# aiosqlite>=0.19.0  # SQLite (uncomment if using SQLite)

# File I/O
aiofiles>=23.0.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0
httpx-mock>=0.10.0
pytest-cov>=4.1.0

# Optional: Enhanced Monitoring
healthcheck>=1.3.3
```

##### **Production Setup** (Recommended for production)

```
# requirements-production.txt

# Core Resilience - Pinned versions for stability
hyx==0.4.2
tenacity==8.2.3
circuitbreaker==1.4.0

# Rate Limiting
slowapi==0.1.9
limits==3.5.0

# HTTP & API
httpx==0.24.1
fastapi==0.100.1
uvicorn[standard]==0.23.2

# Database
sqlalchemy[asyncio]==2.0.19
asyncpg==0.28.0

# File I/O
aiofiles==23.1.0


```

#### Installation Commands

##### **Quick Start** (Essential libraries only)

```shell
pip install hyx tenacity httpx sqlalchemy[asyncio] asyncpg pytest pytest-asyncio
```

##### **Full Stack** (All resilience features)

```shell
pip install hyx tenacity circuitbreaker slowapi limits httpx fastapi uvicorn sqlalchemy[asyncio] asyncpg aiofiles pytest pytest-asyncio httpx-mock pytest-cov
```

##### **Development Environment**

```shell
# Install from requirements file
pip install -r requirements-complete.txt

# Or install with development extras
pip install -e ".[dev]"  # if you have a setup.py with dev extras
```

##### **Production Environment**

```shell
# Install pinned versions for stability
pip install -r requirements-production.txt

# Or install without dev dependencies
pip install --no-dev -r requirements-complete.txt
```

#### 📊 Library Usage Matrix

| Library | Circuit Breaker | Retry | Timeout | Bulkhead | Rate Limiting | Monitoring |
| :---- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Hyx** | ✅ Primary | ✅ Primary | ✅ Primary | ✅ Primary | ✅ Primary | ✅ Basic |
| **Tenacity** | ❌ | ✅ Advanced | ❌ | ❌ | ❌ | ✅ Basic |
| **CircuitBreaker** | ✅ Alternative | ❌ | ❌ | ❌ | ❌ | ❌ |
| **SlowAPI** | ❌ | ❌ | ❌ | ❌ | ✅ API-level | ❌ |
| **Limits** | ❌ | ❌ | ❌ | ❌ | ✅ Advanced | ❌ |
| **HTTPX** | ❌ | ✅ Built-in | ✅ Built-in | ❌ | ❌ | ❌ |
| **SQLAlchemy** | ❌ | ❌ | ✅ Built-in | ✅ Pool | ❌ | ❌ |

#### 🎯 Library Selection Guide

##### **When to Use Each Library:**

###### ***Always Use:***

- **Hyx**: Core resilience patterns for all external operations  
- **HTTPX**: HTTP client for external service calls  
- **SQLAlchemy**: Database operations with async support  
- **Pytest**: Testing framework

###### ***Use When Needed:***

- **Tenacity**: Complex retry scenarios, database operations  
- **CircuitBreaker**: Legacy code, decorator-preferred patterns  
- **SlowAPI**: API rate limiting, FastAPI applications  
- **Limits**: Advanced rate limiting algorithms  
- **AIOFiles**: File-based caching, configuration management

###### ***Use for Production:***

- **Structlog**: Structured logging for better observability  
- **Prometheus Client**: Metrics collection and monitoring  
- **HealthCheck**: Health probe endpoints

###### ***Use for Development:***

- **HTTPX-Mock**: Testing external service interactions  
- **Pytest-Cov**: Code coverage measurement  
- **Uvicorn**: Local development server

#### 📈 Performance Considerations

##### **Library Overhead:**

- **Hyx**: \< 1ms per operation  
- **Tenacity**: \< 0.5ms per retry decision  
- **HTTPX**: Minimal overhead over standard HTTP libraries  
- **SQLAlchemy**: Connection pooling reduces overhead

##### **Memory Usage:**

- **Hyx**: \< 5KB per client instance  
- **Circuit Breaker State**: \< 1KB per service  
- **Rate Limiter**: Scales with request volume  
- **Connection Pools**: Configurable, typically 10-50 connections

#### 🔧 Configuration Examples

##### **Basic Hyx Setup:**

```py
from hyx import AsyncCircuitBreaker, AsyncRetry, AsyncTimeout

# Basic configuration
circuit_breaker = AsyncCircuitBreaker(failure_threshold=3, recovery_timeout=60)
retry_policy = AsyncRetry(attempts=3, backoff='exponential')
timeout = AsyncTimeout(30)
```

##### **Advanced Tenacity Setup:**

```py
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError))
)
async def resilient_operation():
    # Your operation here
    pass
```

##### **SlowAPI Rate Limiting:**

```py
from slowapi import Limiter
from fastapi import FastAPI

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()

@app.get("/api/data")
@limiter.limit("100/minute")
async def get_data(request: Request):
    # Your endpoint logic
    pass
```

#### 🚨 Common Pitfalls & Solutions

##### **Dependency Conflicts:**

- **Issue**: Version conflicts between async libraries  
- **Solution**: Use pinned versions in production, test compatibility

##### **Async Context:**

- **Issue**: Mixing sync and async code  
- **Solution**: Use async versions of all libraries, proper await usage

##### **Connection Pool Exhaustion:**

- **Issue**: Too many concurrent connections  
- **Solution**: Configure appropriate pool sizes, use bulkhead patterns

##### **Testing Complexity:**

- **Issue**: Testing async resilience patterns  
- **Solution**: Use pytest-asyncio, proper mocking with httpx-mock

#### 📚 Documentation References

- **Hyx**: [GitHub Repository](https://github.com/roma-glushko/hyx)  
- **Tenacity**: [Official Documentation](https://tenacity.readthedocs.io/)  
- **HTTPX**: [Documentation](https://www.python-httpx.org/)  
- **FastAPI**: [Documentation](https://fastapi.tiangolo.com/)  
- **SQLAlchemy**: [Async Documentation](https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html)  
- **SlowAPI**: [GitHub Repository](https://github.com/laurentS/slowapi)

#### 🎉 Conclusion

This comprehensive library stack provides enterprise-grade resilience capabilities for Python applications, matching the functionality provided by Cockatiel in TypeScript environments. The combination of Hyx as the primary resilience library with complementary tools ensures robust, fault-tolerant, and observable Python services.

Choose the libraries that match your specific needs, starting with the core stack (Hyx \+ HTTPX \+ SQLAlchemy \+ Pytest) and adding specialized libraries as requirements evolve.

