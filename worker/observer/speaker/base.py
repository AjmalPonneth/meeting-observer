from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass
class SpeakerData:
    name: str
    is_speaking: bool
    is_bot: bool = False


SpeakerChangeCallback = Callable[[list[SpeakerData]], Awaitable[None]]


class BaseSpeakerObserver(ABC):
    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError
