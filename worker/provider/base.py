from abc import ABC, abstractmethod

from playwright.async_api import Page


class BaseProvider(ABC):
    @abstractmethod
    async def open_page(
        self,
        page: Page,
        meeting_url: str,
        streaming_input: str | None = None,
        attempts: int = 0,
        max_attempts: int = 3,
    ) -> Page:
        raise NotImplementedError

    @abstractmethod
    async def join_meeting(self, page) -> None:
        raise NotImplementedError

    @abstractmethod
    async def detect_waiting_room(self, page) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def detect_access_denied(self, page) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def wait_until_joined(self, page, timeout_ms: int = 30000) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def prepare_recording(self, page) -> None:
        raise NotImplementedError

    @abstractmethod
    async def should_end(self, page) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def leave_meeting(self, page) -> None:
        raise NotImplementedError
