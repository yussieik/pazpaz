"""
Retry policy and circuit breaker for AI operations.

This module provides configurable retry logic with exponential backoff and
circuit breaker patterns to handle transient failures in external AI services.

Features:
- Exponential backoff with jitter to avoid thundering herd
- Per-operation retry configuration
- Circuit breaker to prevent cascading failures
- Prometheus metrics for observability
- Comprehensive logging

References:
- Tenacity: https://tenacity.readthedocs.io/
- Circuit Breaker Pattern: https://martinfowler.com/bliki/CircuitBreaker.html
"""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
)
from tenacity.wait import wait_base

from pazpaz.core.logging import get_logger

logger = get_logger(__name__)

# Import metrics (lazy import to avoid circular dependencies)
_metrics_imported = False
_ai_retries_total = None
_ai_circuit_breaker_state_changes_total = None


def _get_metrics():
    """Lazy import metrics to avoid circular dependencies."""
    global _metrics_imported, _ai_retries_total, _ai_circuit_breaker_state_changes_total
    if not _metrics_imported:
        try:
            from pazpaz.ai.metrics import (
                ai_circuit_breaker_state_changes_total,
                ai_retries_total,
            )

            _ai_retries_total = ai_retries_total
            _ai_circuit_breaker_state_changes_total = (
                ai_circuit_breaker_state_changes_total
            )
            _metrics_imported = True
        except ImportError:
            # Metrics not available (e.g., in tests without prometheus_client)
            pass
    return _ai_retries_total, _ai_circuit_breaker_state_changes_total


class WaitExponentialJitter(wait_base):
    """
    Exponential backoff with jitter to avoid thundering herd problem.

    Formula: min(max_delay, base_delay * (exponential_base ** attempt) * (1 + jitter))
    where jitter is random value in [0, jitter_factor]

    Args:
        multiplier: Base delay multiplier (default: 1.0)
        max: Maximum delay in seconds (default: 60)
        exp_base: Exponential base (default: 2)
        jitter_factor: Max jitter as fraction of delay (default: 0.1 = 10%)

    Example:
        >>> wait = WaitExponentialJitter(multiplier=1.0, max=32, exp_base=2, jitter_factor=0.1)
        >>> # Attempt 1: ~1s ± 10%
        >>> # Attempt 2: ~2s ± 10%
        >>> # Attempt 3: ~4s ± 10%
        >>> # Attempt 4: ~8s ± 10%
        >>> # Attempt 5: ~16s ± 10%
        >>> # Attempt 6: ~32s (capped) ± 10%
    """

    def __init__(
        self,
        multiplier: float = 1.0,
        max: float = 60.0,
        exp_base: int = 2,
        jitter_factor: float = 0.1,
    ):
        self.multiplier = multiplier
        self.max = max
        self.exp_base = exp_base
        self.jitter_factor = jitter_factor

    def __call__(self, retry_state):
        """Calculate wait time with exponential backoff and jitter."""
        try:
            attempt_number = retry_state.attempt_number
        except AttributeError:
            attempt_number = 1

        # Exponential backoff: multiplier * (exp_base ** attempt)
        exp_delay = self.multiplier * (self.exp_base ** (attempt_number - 1))

        # Cap at max delay
        delay = min(exp_delay, self.max)

        # Add jitter: random value in [0, jitter_factor * delay]
        jitter = random.uniform(0, self.jitter_factor * delay)

        return delay + jitter


class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open."""

    pass


class CircuitBreaker:
    """
    Circuit breaker to prevent cascading failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, requests immediately fail
    - HALF_OPEN: Testing if service recovered, limited requests pass through

    Transitions:
    - CLOSED → OPEN: After threshold consecutive failures
    - OPEN → HALF_OPEN: After cooldown period
    - HALF_OPEN → CLOSED: After successful request
    - HALF_OPEN → OPEN: After any failure

    Args:
        failure_threshold: Number of consecutive failures to open circuit (default: 5)
        recovery_timeout: Seconds to wait before testing recovery (default: 60)
        name: Circuit breaker name for logging

    Example:
        >>> cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60, name="cohere_api")
        >>> if cb.is_open:
        ...     raise CircuitBreakerError("Circuit breaker is open")
        >>> try:
        ...     result = await external_call()
        ...     cb.record_success()
        ... except Exception as e:
        ...     cb.record_failure()
        ...     raise
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        name: str = "circuit_breaker",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name

        # State tracking
        self._failure_count = 0
        self._state = "closed"  # closed, open, half_open
        self._last_failure_time: float | None = None

    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open (blocking requests)."""
        import time

        if self._state == "open":
            # Check if recovery timeout has passed
            if (
                self._last_failure_time is not None
                and time.time() - self._last_failure_time > self.recovery_timeout
            ):
                # Transition to half-open to test recovery
                old_state = self._state
                self._state = "half_open"

                # Emit state change metric
                _, circuit_breaker_metrics = _get_metrics()
                if circuit_breaker_metrics:
                    circuit_breaker_metrics.labels(
                        circuit_breaker=self.name,
                        from_state=old_state,
                        to_state="half_open",
                    ).inc()

                logger.info(
                    "circuit_breaker_half_open",
                    name=self.name,
                    failure_count=self._failure_count,
                    message="Circuit breaker entering half-open state for testing",
                )
                return False

            return True

        return False

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        return self._state

    def record_success(self) -> None:
        """Record successful operation."""
        if self._state == "half_open":
            # Success in half-open → close circuit
            old_state = self._state
            self._state = "closed"
            self._failure_count = 0
            self._last_failure_time = None

            # Emit state change metric
            _, circuit_breaker_metrics = _get_metrics()
            if circuit_breaker_metrics:
                circuit_breaker_metrics.labels(
                    circuit_breaker=self.name,
                    from_state=old_state,
                    to_state="closed",
                ).inc()

            logger.info(
                "circuit_breaker_closed",
                name=self.name,
                message="Circuit breaker closed after successful recovery test",
            )
        elif self._state == "closed":
            # Reset failure count on success
            if self._failure_count > 0:
                self._failure_count = 0
                logger.debug(
                    "circuit_breaker_success",
                    name=self.name,
                    message="Failure count reset after success",
                )

    def record_failure(self) -> None:
        """Record failed operation."""
        import time

        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._state == "half_open":
            # Failure in half-open → reopen circuit
            old_state = self._state
            self._state = "open"

            # Emit state change metric
            _, circuit_breaker_metrics = _get_metrics()
            if circuit_breaker_metrics:
                circuit_breaker_metrics.labels(
                    circuit_breaker=self.name,
                    from_state=old_state,
                    to_state="open",
                ).inc()

            logger.warning(
                "circuit_breaker_reopened",
                name=self.name,
                failure_count=self._failure_count,
                message="Circuit breaker reopened after failed recovery test",
            )
        elif self._state == "closed" and self._failure_count >= self.failure_threshold:
            # Too many failures → open circuit
            old_state = self._state
            self._state = "open"

            # Emit state change metric
            _, circuit_breaker_metrics = _get_metrics()
            if circuit_breaker_metrics:
                circuit_breaker_metrics.labels(
                    circuit_breaker=self.name,
                    from_state=old_state,
                    to_state="open",
                ).inc()

            logger.error(
                "circuit_breaker_opened",
                name=self.name,
                failure_count=self._failure_count,
                failure_threshold=self.failure_threshold,
                message="Circuit breaker opened due to consecutive failures",
            )

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        self._state = "closed"
        self._failure_count = 0
        self._last_failure_time = None
        logger.info(
            "circuit_breaker_reset",
            name=self.name,
            message="Circuit breaker manually reset",
        )


# Global circuit breakers for AI operations
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """
    Get or create a circuit breaker by name.

    Args:
        name: Circuit breaker name (e.g., "cohere_embed", "cohere_chat")
        **kwargs: CircuitBreaker initialization arguments

    Returns:
        CircuitBreaker instance

    Example:
        >>> cb = get_circuit_breaker("cohere_embed", failure_threshold=5, recovery_timeout=60)
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name=name, **kwargs)
    return _circuit_breakers[name]


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: int = 2,
    jitter_factor: float = 0.1,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
    circuit_breaker_name: str | None = None,
    circuit_breaker_threshold: int = 5,
    circuit_breaker_timeout: float = 60.0,
) -> Callable:
    """
    Decorator for async functions with retry logic and circuit breaker.

    This decorator provides:
    - Exponential backoff with jitter
    - Configurable retry attempts
    - Circuit breaker pattern
    - Comprehensive logging
    - Prometheus metrics (when integrated)

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Base delay for exponential backoff in seconds (default: 1.0)
        max_delay: Maximum delay between retries in seconds (default: 60.0)
        exponential_base: Base for exponential backoff (default: 2)
        jitter_factor: Jitter factor as fraction of delay (default: 0.1 = 10%)
        retryable_exceptions: Tuple of exception types to retry (default: (Exception,))
        circuit_breaker_name: Name for circuit breaker (if None, no circuit breaker)
        circuit_breaker_threshold: Failures before opening circuit (default: 5)
        circuit_breaker_timeout: Seconds before testing recovery (default: 60)

    Returns:
        Decorated async function with retry logic

    Example:
        >>> @retry_with_backoff(
        ...     max_retries=3,
        ...     base_delay=1.0,
        ...     max_delay=32.0,
        ...     retryable_exceptions=(ApiError, httpx.HTTPStatusError),
        ...     circuit_breaker_name="cohere_embed",
        ... )
        ... async def embed_text(text: str) -> list[float]:
        ...     return await cohere_client.embed(texts=[text])
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args, **kwargs) -> Any:
            # Get circuit breaker if configured
            circuit_breaker = None
            if circuit_breaker_name:
                circuit_breaker = get_circuit_breaker(
                    circuit_breaker_name,
                    failure_threshold=circuit_breaker_threshold,
                    recovery_timeout=circuit_breaker_timeout,
                )

                # Check if circuit breaker is open
                if circuit_breaker.is_open:
                    logger.error(
                        "circuit_breaker_open",
                        function=func.__name__,
                        circuit_breaker=circuit_breaker_name,
                        state=circuit_breaker.state,
                        message="Request blocked by open circuit breaker",
                    )
                    raise CircuitBreakerError(
                        f"Circuit breaker '{circuit_breaker_name}' is open. "
                        f"Service may be experiencing issues. "
                        f"Retry after {circuit_breaker_timeout} seconds."
                    )

            # Define before_sleep callback for metrics
            def emit_retry_metrics(retry_state):
                """Emit Prometheus metrics on each retry attempt."""
                retry_metrics, _ = _get_metrics()
                if retry_metrics:
                    retry_metrics.labels(
                        operation=func.__name__,
                        attempt=str(retry_state.attempt_number),
                        circuit_breaker=circuit_breaker_name or "none",
                    ).inc()

                logger.warning(
                    "retry_attempt",
                    function=func.__name__,
                    attempt=retry_state.attempt_number,
                    max_retries=max_retries,
                    circuit_breaker=circuit_breaker_name,
                    wait_time=retry_state.next_action.sleep
                    if retry_state.next_action
                    else None,
                    error=str(retry_state.outcome.exception())
                    if retry_state.outcome
                    else None,
                )

            # Configure retry policy
            retryer = AsyncRetrying(
                stop=stop_after_attempt(max_retries),
                wait=WaitExponentialJitter(
                    multiplier=base_delay,
                    max=max_delay,
                    exp_base=exponential_base,
                    jitter_factor=jitter_factor,
                ),
                retry=retry_if_exception_type(retryable_exceptions),
                before_sleep=emit_retry_metrics,
                reraise=True,
            )

            try:
                # Execute with retry logic
                result = await retryer(func, *args, **kwargs)

                # Record success in circuit breaker
                if circuit_breaker:
                    circuit_breaker.record_success()

                return result

            except RetryError as e:
                # All retries exhausted
                if circuit_breaker:
                    circuit_breaker.record_failure()

                logger.error(
                    "retry_exhausted",
                    function=func.__name__,
                    max_retries=max_retries,
                    circuit_breaker=circuit_breaker_name,
                    error=str(e.last_attempt.exception()),
                    message="All retry attempts exhausted",
                    exc_info=True,
                )

                # Re-raise the original exception
                raise e.last_attempt.exception() from e

            except Exception as e:
                # Non-retryable exception or unexpected error
                if circuit_breaker:
                    circuit_breaker.record_failure()

                logger.error(
                    "operation_failed",
                    function=func.__name__,
                    circuit_breaker=circuit_breaker_name,
                    error=str(e),
                    error_type=type(e).__name__,
                    message="Operation failed with non-retryable error",
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator
