"""Timing helpers for assistant chat pipeline instrumentation."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ChatPerfTimer:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    started_at: float = field(default_factory=time.monotonic)
    stages_ms: dict[str, int] = field(default_factory=dict)
    _marks: dict[str, float] = field(default_factory=dict)

    def start(self, stage: str) -> None:
        self._marks[stage] = time.monotonic()

    def stop(self, stage: str) -> int:
        started = self._marks.pop(stage, None)
        if started is None:
            return 0
        elapsed = int((time.monotonic() - started) * 1000)
        self.stages_ms[stage] = elapsed
        return elapsed

    def mark(self, stage: str, elapsed_ms: int) -> None:
        self.stages_ms[stage] = elapsed_ms

    def total_ms(self) -> int:
        return int((time.monotonic() - self.started_at) * 1000)

    def log_summary(self, **extra: Any) -> None:
        logger.info(
            "chat_perf run_id=%s total_ms=%s stages=%s extra=%s",
            self.run_id,
            self.total_ms(),
            self.stages_ms,
            extra,
        )
