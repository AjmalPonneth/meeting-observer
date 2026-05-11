from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from worker.machine.type import MeetingEndReason


@dataclass
class RuntimeResources:
    page: Any
    browser_context: Any
    playwright: Any


@dataclass
class MeetingRunState:
    start_time: int | None = None
    exit_time: int | None = None

    is_paused: bool = False
    total_pause_duration: int = 0

    current_speaker: str | None = None

    raw_summary: str | None = None
    final_summary: Any | None = None

    end_reason: MeetingEndReason | None = None
    error: Exception | None = None
    error_message: str | None = None
    should_retry: bool = False

    def duration_seconds(self) -> int | None:
        if self.start_time is None:
            return None

        if self.exit_time is None:
            return None

        duration = self.exit_time - self.start_time

        if duration < 0:
            return 0

        return duration

    def set_error(
        self,
        reason: MeetingEndReason,
        message: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.end_reason = reason
        self.error = error
        self.error_message = message or (str(error) if error else None)

    def set_end_reason(self, reason: MeetingEndReason) -> None:
        self.end_reason = reason
        self.error = None
        self.error_message = None

    def has_error(self) -> bool:
        return self.error is not None or self.error_message is not None

    def get_error_message(self) -> str:
        return self.error_message or str(self.error) or "Meeting observation failed"


@dataclass
class MeetingContext:
    config: Any
    provider: Any
    runtime: RuntimeResources
    observer: Any
    event: Any
    state: MeetingRunState
