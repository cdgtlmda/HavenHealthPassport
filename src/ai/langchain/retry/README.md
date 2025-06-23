# LangChain Retry Logic Module

## Overview

This module provides comprehensive retry logic for LangChain agents in the Haven Health Passport system. It includes:

- **Exponential backoff** with configurable strategies
- **Circuit breaker pattern** to prevent cascading failures
- **Medical-specific retry policies** based on urgency levels
- **Comprehensive metrics and monitoring**

## Quick Start

### Basic Usage

```python
from haven_health_passport.ai.langchain.retry import retry_with_backoff, RetryConfig

# Simple retry with defaults
@retry_with_backoff(max_attempts=3)
async def fetch_medical_data():
    # Your code here
    pass

# Custom configuration
config = RetryConfig(
    max_attempts=5,
    initial_delay=0.5,
    max_delay=30.0,
    exponential_base=2.0
)

@retry_with_backoff(config)
async def process_health_record():
    # Your code here
    pass
```

### Medical-Specific Retry

```python
from haven_health_passport.ai.langchain.retry import medical_retry

# Retry based on urgency level
@medical_retry(urgency_level=5)  # Emergency
async def emergency_response():
    # Critical operation
    pass

@medical_retry(urgency_level=2)  # Routine
async def routine_checkup():
    # Non-critical operation
    pass
```

### Using Retry Manager

```python
from haven_health_passport.ai.langchain.retry import retry_manager, RetryStrategy

# Get predefined strategy
decorator = retry_manager.get_retry_decorator(RetryStrategy.MEDICAL_CRITICAL)

@decorator
async def critical_operation():
    # Your code here
    pass

# Check circuit breaker status
status = retry_manager.get_circuit_breaker_status()
print(status)
```

## Retry Strategies

### Predefined Strategies

1. **AGGRESSIVE**: Many retries, short delays
   - Max attempts: 5
   - Initial delay: 0.5s
   - Use for: Non-critical, idempotent operations

2. **STANDARD**: Balanced approach
   - Max attempts: 3
   - Initial delay: 1.0s
   - Use for: General operations

3. **CONSERVATIVE**: Few retries, long delays
   - Max attempts: 2
   - Initial delay: 2.0s
   - Use for: Expensive operations

4. **MEDICAL_CRITICAL**: Optimized for medical operations
   - Max attempts: 4
   - Initial delay: 0.5s
   - No jitter for predictability
   - Use for: Critical medical operations

### Urgency-Based Medical Retry

| Urgency Level | Max Attempts | Initial Delay | Max Delay | Jitter |
|---------------|--------------|---------------|-----------|--------|
| 5 (Emergency) | 5            | 0.1s          | 2.0s      | No     |
| 3-4 (Critical)| 4            | 0.5s          | 10.0s     | Yes    |
| 1-2 (Routine) | 3            | 1.0s          | 30.0s     | Yes    |

## Circuit Breaker

The circuit breaker prevents cascading failures:

```python
from haven_health_passport.ai.langchain.retry import CircuitBreaker, CircuitBreakerConfig

# Configure circuit breaker
config = CircuitBreakerConfig(
    failure_threshold=5,      # Open after 5 failures
    success_threshold=2,      # Close after 2 successes in half-open
    timeout=60.0,            # Try half-open after 60s
    half_open_requests=1     # Allow 1 request in half-open state
)

circuit_breaker = CircuitBreaker(config)

# Use with retry decorator
@retry_with_backoff(circuit_breaker=circuit_breaker)
async def protected_operation():
    # Your code here
    pass
```

### Circuit Breaker States

- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Too many failures, requests blocked
- **HALF_OPEN**: Testing recovery, limited requests allowed

## Integration with Agents

The retry logic is automatically integrated into all Haven Health Passport agents:

```python
from haven_health_passport.ai.langchain.agents import MedicalContext

# Agents automatically use retry based on context
context = MedicalContext(
    urgency_level=4,  # High urgency = aggressive retry
    language="en"
)

# Agent will retry with appropriate strategy
result = await agent.process(query, context)
```

## Error Handling

### Retryable Exceptions

By default, these exceptions trigger retry:
- `ConnectionError`
- `TimeoutError`
- Network-related errors

### Non-Retryable Exceptions

These exceptions do NOT trigger retry:
- `ValueError` (bad data)
- `PermissionError` (HIPAA violations)
- Business logic errors

### Custom Exception Handling

```python
@retry_with_backoff(
    retry_on=(ConnectionError, TimeoutError, CustomError),
    exclude=(ValueError, PermissionError)
)
async def custom_operation():
    # Your code here
    pass
```

## Monitoring and Metrics

### Getting Metrics

```python
# Get retry metrics
metrics = retry_manager.get_metrics()
print(metrics)

# Output:
{
    "operations": {
        "fetch_data": {
            "attempts": 15,
            "successes": 12,
            "failures": 3,
            "total_retry_time": 45.2
        }
    },
    "circuit_breakers": {
        "standard": {
            "current_state": "closed",
            "total_requests": 100,
            "failed_requests": 5,
            "successful_requests": 95
        }
    }
}
```

### Logging

All retry attempts are logged with appropriate levels:
- **INFO**: Successful operations
- **WARNING**: Retry attempts
- **ERROR**: Final failures

Medical operations include additional context:
```python
logger.warning(
    "Medical operation retry",
    extra={
        "operation": "emergency_response",
        "urgency": 5,
        "attempt": 2,
        "alert_type": "medical_retry"
    }
)
```

## Best Practices

1. **Choose appropriate strategy**: Use urgency levels for medical operations
2. **Monitor circuit breakers**: Reset manually if needed
3. **Handle non-retryable errors**: Don't retry on data validation errors
4. **Set reasonable timeouts**: Avoid excessive delays in emergencies
5. **Test retry logic**: Ensure it works under failure conditions

## Configuration Examples

### Emergency Medical Operation
```python
@medical_retry(urgency_level=5, operation_type="emergency")
async def emergency_procedure():
    # Fast retries, no jitter
    pass
```

### Batch Processing
```python
@retry_with_backoff(
    max_attempts=3,
    initial_delay=5.0,
    backoff_strategy=BackoffStrategy.LINEAR
)
async def batch_process():
    # Linear backoff for predictable timing
    pass
```

### External API Call
```python
@retry_with_backoff(
    max_attempts=5,
    initial_delay=1.0,
    max_delay=60.0,
    jitter=True
)
async def call_external_api():
    # Exponential backoff with jitter
    pass
```

## Testing

Run retry tests:
```bash
pytest src/ai/langchain/retry/tests/
```

Test specific scenarios:
```python
# Test retry behavior
with pytest.raises(RetryException):
    failing_function()

# Test circuit breaker
circuit_breaker.record_failure()
assert circuit_breaker.state == CircuitBreakerState.OPEN
```
