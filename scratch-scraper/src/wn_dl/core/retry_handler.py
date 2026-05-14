"""
Advanced retry and rate limiting module.

This module provides sophisticated retry logic with exponential backoff,
circuit breaker patterns, and adaptive rate limiting.
"""

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    retry_on_exceptions: tuple = (Exception,)
    retry_on_status_codes: List[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    expected_exception: Type[Exception] = Exception


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_second: float = 2.0
    burst_size: int = 5
    adaptive: bool = True
    min_delay: float = 0.1
    max_delay: float = 10.0


class CircuitBreaker:
    """
    Circuit breaker implementation for handling service failures.

    Prevents cascading failures by temporarily stopping requests to a failing service.
    """

    def __init__(self, config: CircuitBreakerConfig):
        """Initialize circuit breaker."""
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.success_count = 0

        logger.debug(
            f"CircuitBreaker initialized with threshold: {config.failure_threshold}"
        )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If circuit is open or function fails
        """
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time < self.config.recovery_timeout:
                raise Exception("Circuit breaker is OPEN")
            else:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                logger.info("Circuit breaker moved to HALF_OPEN state")

        try:
            result = (
                await func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else func(*args, **kwargs)
            )
            self._on_success()
            return result

        except self.config.expected_exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        """Handle successful request."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 3:  # Require multiple successes to close
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info("Circuit breaker moved to CLOSED state")
        elif self.state == CircuitState.CLOSED:
            self.failure_count = max(
                0, self.failure_count - 1
            )  # Gradually reduce failure count

    def _on_failure(self):
        """Handle failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker moved to OPEN state after {self.failure_count} failures"
            )


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts based on server responses.

    Implements token bucket algorithm with adaptive rate adjustment.
    """

    def __init__(self, config: RateLimitConfig):
        """Initialize rate limiter."""
        self.config = config
        self.tokens = config.burst_size
        self.last_update = time.time()
        self.current_rate = config.requests_per_second
        self.consecutive_successes = 0
        self.consecutive_failures = 0

        logger.debug(
            f"AdaptiveRateLimiter initialized with rate: {config.requests_per_second} req/s"
        )

    async def acquire(self) -> None:
        """Acquire permission to make a request."""
        now = time.time()

        # Add tokens based on elapsed time
        elapsed = now - self.last_update
        self.tokens = min(
            self.config.burst_size, self.tokens + elapsed * self.current_rate
        )
        self.last_update = now

        # If no tokens available, wait
        if self.tokens < 1:
            wait_time = (1 - self.tokens) / self.current_rate
            wait_time = max(
                self.config.min_delay, min(self.config.max_delay, wait_time)
            )

            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)

            # Update tokens after waiting
            self.tokens = 1

        # Consume a token
        self.tokens -= 1

    def on_success(self):
        """Notify rate limiter of successful request."""
        if self.config.adaptive:
            self.consecutive_successes += 1
            self.consecutive_failures = 0

            # Gradually increase rate on consecutive successes
            if self.consecutive_successes >= 10:
                self.current_rate = min(
                    self.config.requests_per_second * 2, self.current_rate * 1.1
                )
                self.consecutive_successes = 0
                logger.debug(f"Increased rate to {self.current_rate:.2f} req/s")

    def on_failure(self, status_code: Optional[int] = None):
        """Notify rate limiter of failed request."""
        if self.config.adaptive:
            self.consecutive_failures += 1
            self.consecutive_successes = 0

            # Decrease rate on rate limiting or server errors
            if status_code == 429 or self.consecutive_failures >= 3:
                self.current_rate = max(
                    self.config.requests_per_second / 4, self.current_rate * 0.5
                )
                self.consecutive_failures = 0
                logger.debug(f"Decreased rate to {self.current_rate:.2f} req/s")


class RetryHandler:
    """
    Advanced retry handler with exponential backoff and circuit breaker.

    Provides sophisticated retry logic for handling transient failures.
    """

    def __init__(
        self,
        retry_config: Optional[RetryConfig] = None,
        circuit_config: Optional[CircuitBreakerConfig] = None,
        rate_limit_config: Optional[RateLimitConfig] = None,
    ):
        """Initialize retry handler."""
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker = (
            CircuitBreaker(circuit_config) if circuit_config else None
        )
        self.rate_limiter = (
            AdaptiveRateLimiter(rate_limit_config) if rate_limit_config else None
        )

        logger.debug("RetryHandler initialized")

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all retries fail
        """
        last_exception = None

        for attempt in range(self.retry_config.max_retries + 1):
            try:
                # Apply rate limiting
                if self.rate_limiter:
                    await self.rate_limiter.acquire()

                # Execute with circuit breaker protection
                if self.circuit_breaker:
                    result = await self.circuit_breaker.call(func, *args, **kwargs)
                else:
                    result = (
                        await func(*args, **kwargs)
                        if asyncio.iscoroutinefunction(func)
                        else func(*args, **kwargs)
                    )

                # Notify success
                if self.rate_limiter:
                    self.rate_limiter.on_success()

                if attempt > 0:
                    logger.info(f"Request succeeded on attempt {attempt + 1}")

                return result

            except Exception as e:
                last_exception = e

                # Check if we should retry this exception
                if not self._should_retry(e, attempt):
                    logger.error(f"Not retrying exception: {e}")
                    raise e

                # Notify failure
                if self.rate_limiter:
                    status_code = getattr(e, "status_code", None)
                    self.rate_limiter.on_failure(status_code)

                # Calculate delay for next attempt
                if attempt < self.retry_config.max_retries:
                    # Check if exception has custom retry delay (e.g., from Retry-After header)
                    if hasattr(e, "retry_after") and e.retry_after:
                        delay = float(e.retry_after)
                        logger.warning(
                            f"Attempt {attempt + 1} failed: {e}. Server suggests retrying in {delay:.2f}s"
                        )
                    else:
                        delay = self._calculate_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s"
                        )

                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"All {self.retry_config.max_retries + 1} attempts failed"
                    )

        # All retries exhausted
        raise last_exception

    def _should_retry(self, exception: Exception, attempt: int) -> bool:
        """
        Determine if exception should be retried.

        Args:
            exception: Exception that occurred
            attempt: Current attempt number

        Returns:
            True if should retry
        """
        # Check if we have retries left
        if attempt >= self.retry_config.max_retries:
            return False

        # Check if exception type is retryable
        if not isinstance(exception, self.retry_config.retry_on_exceptions):
            return False

        # Check status code if available
        if hasattr(exception, "status_code"):
            return exception.status_code in self.retry_config.retry_on_status_codes

        return True

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for next retry attempt.

        Args:
            attempt: Current attempt number (0-based)

        Returns:
            Delay in seconds
        """
        # Exponential backoff
        delay = self.retry_config.base_delay * (
            self.retry_config.backoff_factor**attempt
        )

        # Apply maximum delay limit
        delay = min(delay, self.retry_config.max_delay)

        # Add jitter to prevent thundering herd
        if self.retry_config.jitter:
            jitter = delay * 0.1 * random.random()
            delay += jitter

        return delay


# Convenience functions for common use cases


async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    *args,
    **kwargs,
) -> Any:
    """
    Simple retry function with exponential backoff.

    Args:
        func: Function to retry
        max_retries: Maximum number of retries
        base_delay: Base delay in seconds
        backoff_factor: Backoff multiplier
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result
    """
    config = RetryConfig(
        max_retries=max_retries, base_delay=base_delay, backoff_factor=backoff_factor
    )

    handler = RetryHandler(retry_config=config)
    return await handler.execute(func, *args, **kwargs)


def create_web_scraper_retry_handler() -> RetryHandler:
    """
    Create retry handler optimized for web scraping.

    Returns:
        Configured RetryHandler instance
    """
    # Import HTTPError here to avoid circular imports
    from .base_scraper import HTTPError

    retry_config = RetryConfig(
        max_retries=3,
        base_delay=1.0,
        max_delay=30.0,
        backoff_factor=2.0,
        jitter=True,
        retry_on_exceptions=(HTTPError, Exception),
        retry_on_status_codes=[429, 500, 502, 503, 504, 520, 521, 522, 524],
    )

    circuit_config = CircuitBreakerConfig(failure_threshold=5, recovery_timeout=60.0)

    rate_limit_config = RateLimitConfig(
        requests_per_second=1.0, burst_size=3, adaptive=True
    )

    return RetryHandler(retry_config, circuit_config, rate_limit_config)
