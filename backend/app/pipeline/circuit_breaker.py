"""Circuit breaker per §12.1 — HEALTHY → COOLING_DOWN → DISABLED state machine."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class CircuitState(str, Enum):
    HEALTHY = "healthy"
    COOLING_DOWN = "cooling_down"
    DISABLED = "disabled"


@dataclass
class CircuitBreaker:
    name: str
    error_threshold: int = 3
    cooldown_seconds: int = 60
    disable_threshold: int = 3

    state: CircuitState = CircuitState.HEALTHY
    consecutive_errors: int = 0
    cooldown_cycles: int = 0
    last_error_at: datetime | None = None
    cooling_until: datetime | None = None

    def record_success(self) -> None:
        self.consecutive_errors = 0
        if self.state == CircuitState.COOLING_DOWN:
            self.state = CircuitState.HEALTHY
            self.cooldown_cycles = 0
            self.cooling_until = None

    def record_failure(self) -> None:
        self.consecutive_errors += 1
        self.last_error_at = datetime.utcnow()

        if self.consecutive_errors >= self.error_threshold:
            if self.state == CircuitState.HEALTHY:
                self.cooldown_cycles += 1
                if self.cooldown_cycles >= self.disable_threshold:
                    self.state = CircuitState.DISABLED
                else:
                    self.state = CircuitState.COOLING_DOWN
                    self.cooling_until = datetime.utcnow() + timedelta(
                        seconds=self.cooldown_seconds
                    )

    def is_available(self) -> bool:
        if self.state == CircuitState.HEALTHY:
            return True
        if self.state == CircuitState.DISABLED:
            return False
        # COOLING_DOWN: check if cooldown expired
        if self.cooling_until and datetime.utcnow() > self.cooling_until:
            self.state = CircuitState.HEALTHY
            self.consecutive_errors = 0
            return True
        return False

    def status_dict(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "consecutive_errors": self.consecutive_errors,
            "cooldown_cycles": self.cooldown_cycles,
            "last_error_at": self.last_error_at.isoformat() if self.last_error_at else None,
            "cooling_until": self.cooling_until.isoformat() if self.cooling_until else None,
        }
