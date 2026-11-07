"""A small circuit breaker that skips a failing model for a cooldown."""

import time
from dataclasses import dataclass


class CircuitOpenError(Exception):
    """Raised instead of calling a model that is in its cooldown."""


@dataclass
class CircuitBreaker:
    failures_to_open: int
    cooldown_seconds: float
    failures: int = 0
    opened_at: float | None = None

    def allows_call(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at >= self.cooldown_seconds:
            self.opened_at = None  # let one call through to test the model
            return True
        return False

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failures_to_open:
            self.opened_at = time.monotonic()
