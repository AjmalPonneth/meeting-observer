from __future__ import annotations

import asyncio
import logging

from worker.machine.state_machine import StateMachine
from worker.observer.meeting import MeetingObserver
from worker.provider import get_provider
from worker.runtime.registry import get_or_start_worker_runtime
from worker.session.config import SessionConfig
from worker.session.context import (
    MeetingContext,
    MeetingRunState,
    RuntimeResources,
)
from worker.webhook.client import Client

logger = logging.getLogger(__name__)


class MeetingSession:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.config = SessionConfig.from_payload(payload)

        self.runtime = None
        self.page = None

        self.context: MeetingContext | None = None
        self.machine: StateMachine | None = None

    async def __aenter__(self) -> MeetingSession:
        logger.info(
            "meeting session starting bot_id=%s provider=%s",
            self.config.bot_uuid,
            self.config.provider,
        )
        self.runtime = await get_or_start_worker_runtime()

        browser_context = await self.runtime.new_browser_context()

        self.page = await browser_context.new_page()

        provider = get_provider(self.config.provider)

        observer = MeetingObserver(
            provider=self.config.provider,
            bot_name=self.config.bot_name,
            recording_mode=self.config.recording_mode,
        )

        event = Client(self.config)
        self.context = MeetingContext(
            config=self.config,
            provider=provider,
            runtime=RuntimeResources(
                page=self.page,
                browser_context=browser_context,
                playwright=self.runtime.playwright,
            ),
            observer=observer,
            event=event,
            state=MeetingRunState(),
        )

        self.machine = StateMachine()
        self.machine.bind(self.context)

        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            await asyncio.shield(self._cleanup())
        finally:
            self.context = None
            self.machine = None
            self.page = None

    async def _cleanup(self) -> None:
        if self.context is None:
            return

        page = self.context.runtime.page
        browser_context = self.context.runtime.browser_context

        await self.context.observer.stop(page)

        if page and not page.is_closed():
            await page.close()

        if browser_context:
            await browser_context.close()

    async def run(self) -> None:
        if self.machine is None:
            raise RuntimeError("MeetingSession is not initialized")

        await self.machine.start()
        error = self.machine.get_error()
        if error:
            logger.error(
                f"Meeting session failed bot_id={self.config.bot_uuid} error={error}",
            )
            raise error
