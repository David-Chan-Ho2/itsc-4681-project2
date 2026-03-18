"""Error handling and retry logic for NEXUS."""

import asyncio
import inspect
import time
from enum import Enum
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


class ErrorCategory(str, Enum):
    """Error categorization for retry decisions."""

    TRANSIENT = "transient"  # Retry with backoff
    RATE_LIMIT = "rate_limit"  # Specific backoff strategy
    PROVIDER_UNAVAILABLE = "provider_unavailable"  # Provider down
    TOOL_EXECUTION_ERROR = "tool_error"  # Tool failed
    VALIDATION_ERROR = "validation"  # Don't retry
    USER_INTERRUPTION = "interrupted"  # User cancelled
    UNKNOWN = "unknown"  # Unknown error


class CircuitBreakerState(str, Enum):
    """State of circuit breaker."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Too many failures, blocking
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreaker:
    """Circuit breaker pattern for handling repeated failures."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ):
        """Initialize circuit breaker.

        Args:
            name: Name for logging.
            failure_threshold: Failures before opening.
            recovery_timeout: Seconds before attempting recovery.
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None

    async def call(self, func: Callable, *args, **kwargs) -> T:
        """Execute function through circuit breaker.

        Args:
            func: Async function to call.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Function result.

        Raises:
            Exception: If circuit is open or function fails.
        """
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_recovery():
                self.state = CircuitBreakerState.HALF_OPEN
                print(
                    f"🔄 Circuit breaker '{self.name}' entering HALF_OPEN state. "
                    "Attempting recovery..."
                )
            else:
                raise Exception(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Waiting {self.recovery_timeout}s before retry."
                )

        try:
            result = await func(*args, **kwargs) if inspect.iscoroutinefunction(func) else func(*args, **kwargs)

            # Success: reset state
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                print(f"✅ Circuit breaker '{self.name}' recovered. State: CLOSED")
            elif self.state == CircuitBreakerState.CLOSED and self.failure_count > 0:
                self.failure_count = 0

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                print(
                    f"🚫 Circuit breaker '{self.name}' opened after {self.failure_count} failures. "
                    f"Recovery attempt in {self.recovery_timeout}s."
                )

            raise

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery.

        Returns:
            True if recovery should be attempted.
        """
        if self.last_failure_time is None:
            return True

        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.recovery_timeout

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None


class RetryManager:
    """Manages retry logic with exponential backoff."""

    def __init__(
        self,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        backoff_max: float = 60.0,
    ):
        """Initialize retry manager.

        Args:
            max_retries: Maximum retry attempts.
            backoff_base: Initial backoff in seconds.
            backoff_max: Maximum backoff in seconds.
        """
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max

    async def execute_with_retry(
        self,
        func: Callable[..., T],
        categorize_error: Optional[Callable[[Exception], ErrorCategory]] = None,
        *args,
        **kwargs,
    ) -> T:
        """Execute function with retry logic.

        Args:
            func: Async function to execute.
            categorize_error: Function to categorize errors.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Function result.

        Raises:
            Exception: If all retries exhausted.
        """
        attempt = 0
        last_exception: Optional[Exception] = None

        while attempt <= self.max_retries:
            try:
                if inspect.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except Exception as e:
                last_exception = e
                attempt += 1

                # Determine error category
                if categorize_error:
                    category = categorize_error(e)
                else:
                    category = self._infer_category(e)

                # Don't retry validation errors
                if category == ErrorCategory.VALIDATION_ERROR:
                    raise

                # Don't retry user interruption
                if category == ErrorCategory.USER_INTERRUPTION:
                    raise

                if attempt > self.max_retries:
                    print(
                        f"❌ All {self.max_retries} retries exhausted for {func.__name__}"
                    )
                    raise

                # Calculate backoff
                backoff = self._calculate_backoff(attempt, category)
                print(
                    f"⏳ Retry {attempt}/{self.max_retries} for {func.__name__} "
                    f"after {backoff:.1f}s (error: {category.value})"
                )

                await asyncio.sleep(backoff)

        # Should not reach here
        if last_exception:
            raise last_exception
        raise Exception(f"Failed to execute {func.__name__}")

    def _infer_category(self, exception: Exception) -> ErrorCategory:
        """Infer error category from exception.

        Args:
            exception: The exception.

        Returns:
            Error category.
        """
        error_str = str(exception).lower()

        if "timeout" in error_str or isinstance(exception, asyncio.TimeoutError):
            return ErrorCategory.TRANSIENT

        if "429" in error_str or "rate" in error_str:
            return ErrorCategory.RATE_LIMIT

        if "connection" in error_str or "unreachable" in error_str:
            return ErrorCategory.PROVIDER_UNAVAILABLE

        if "invalid" in error_str or "validation" in error_str:
            return ErrorCategory.VALIDATION_ERROR

        return ErrorCategory.TRANSIENT  # Default to transient for unknown

    def _calculate_backoff(
        self, attempt: int, category: ErrorCategory
    ) -> float:
        """Calculate backoff time.

        Args:
            attempt: Retry attempt number.
            category: Error category.

        Returns:
            Backoff time in seconds.
        """
        if category == ErrorCategory.RATE_LIMIT:
            # Longer backoff for rate limits
            base_backoff = self.backoff_base * 2
        else:
            base_backoff = self.backoff_base

        # Exponential backoff: 1s, 2s, 4s, 8s, ...
        backoff = base_backoff * (2 ** (attempt - 1))

        # Add jitter (random ±50%)
        import random

        jitter = random.uniform(0.5, 1.5)
        backoff *= jitter

        # Cap at maximum
        return min(backoff, self.backoff_max)
