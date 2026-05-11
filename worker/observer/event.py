from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

Handler = Callable[[Any], Awaitable[None]]


@dataclass
class AudioChunkReceived:
    audio_data: list[float]
    sample_rate: int
    timestamp: int
    speaker: str | None = None


class EventListener:
    def __init__(self) -> None:
        self._handlers: dict[type, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: type, handler: Handler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: object) -> None:
        for handler in self._handlers[type(event)]:
            await handler(event)
