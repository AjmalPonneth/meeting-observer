from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from worker.llm.client import RealtimeLLMClient
from worker.llm.schema import response_config, session_config

logger = logging.getLogger(__name__)

EventHandler = Callable[[Any], Awaitable[None]]


IGNORED_EVENTS = {
    "response.output_audio.delta",
    "response.output_audio.done",
    "response.output_audio_transcript.delta",
    "response.output_audio_transcript.done",
    "response.content_part.added",
    "response.output_item.added",
    "conversation.item.added",
    "conversation.item.done",
    "rate_limits.updated",
}

SUMMARY_TIMEOUT_SECONDS = 60.0
AUDIO_QUEUE_DRAIN_TIMEOUT_SECONDS = 5.0


class RealtimeMeetingSession:
    def __init__(
        self,
        client: RealtimeLLMClient,
        *,
        audio_queue_size: int = 100,
    ) -> None:
        self.client = client

        self.receive_task: asyncio.Task | None = None
        self.sender_task: asyncio.Task | None = None

        self.audio_queue: asyncio.Queue[str | None] = asyncio.Queue(
            maxsize=audio_queue_size,
        )

        self.response_text = ""
        self.response_done = asyncio.Event()

        self.audio_chunks_queued = 0
        self.audio_chunks_sent = 0
        self.audio_chunks_dropped = 0

        self.started = False
        self.closed = False

        self.event_handlers: dict[str, EventHandler] = {
            "error": self.handle_error,
            "response.text.delta": self.handle_response_delta,
            "response.output_text.delta": self.handle_response_delta,
            "response.text.done": self.handle_response_text_done,
            "response.output_text.done": self.handle_response_text_done,
            "response.done": self.handle_response_done,
            "response.completed": self.handle_response_done,
            "conversation.item.input_audio_transcription.completed": (
                self.handle_transcript
            ),
            "session.created": self.handle_log_event,
            "session.updated": self.handle_log_event,
            "input_audio_buffer.speech_started": self.handle_log_event,
            "input_audio_buffer.speech_stopped": self.handle_log_event,
            "input_audio_buffer.committed": self.handle_log_event,
            "conversation.item.created": self.handle_log_event,
            "response.created": self.handle_log_event,
        }

    async def start(self) -> None:
        if self.started:
            return

        self.started = True
        self.closed = False

        await self.client.connect()
        await self.client.update_session(session=session_config())

        self.receive_task = asyncio.create_task(
            self.receive_loop(),
            name="realtime-receive-loop",
        )

        self.sender_task = asyncio.create_task(
            self.audio_sender_loop(),
            name="realtime-audio-sender-loop",
        )

    async def send_audio(self, audio_b64: str) -> None:
        if self.closed or not self.started:
            return

        try:
            self.audio_queue.put_nowait(audio_b64)
            self.audio_chunks_queued += 1

        except asyncio.QueueFull:
            self.audio_chunks_dropped += 1

            if self.audio_chunks_dropped == 1 or self.audio_chunks_dropped % 50 == 0:
                logger.warning(
                    f"Realtime audio queue full dropped={self.audio_chunks_dropped}",
                )

    async def audio_sender_loop(self) -> None:
        while True:
            audio_b64 = await self.audio_queue.get()

            try:
                if audio_b64 is None or self.closed:
                    return

                await self.client.append_audio(audio_b64)
                self.audio_chunks_sent += 1

            finally:
                self.audio_queue.task_done()

    async def request_summary(
        self,
        *,
        final: bool = False,
        context: dict | None = None,
    ) -> str | None:
        if not self.started or self.closed:
            return None

        self.response_text = ""
        self.response_done.clear()

        await self.drain_audio_queue()

        logger.info("Requesting realtime summary final=%s", final)

        await self.client.create_response(
            response=response_config(final=final, context=context),
        )

        try:
            async with asyncio.timeout(SUMMARY_TIMEOUT_SECONDS):
                await self.response_done.wait()
        except TimeoutError:
            logger.warning("Realtime summary timeout.")

        return self.response_text.strip() or None

    async def drain_audio_queue(self) -> None:
        try:
            async with asyncio.timeout(AUDIO_QUEUE_DRAIN_TIMEOUT_SECONDS):
                await self.audio_queue.join()
        except TimeoutError:
            logger.warning("Audio queue drain timeout.")

    async def receive_loop(self) -> None:
        try:
            async for event in self.client.receive():
                await self.dispatch_event(event)
        except Exception:
            if not self.closed:
                logger.exception("Realtime receive loop failed.")
                self.response_done.set()

    async def dispatch_event(self, event: Any) -> None:
        event_type = getattr(event, "type", None)

        if not event_type:
            await self.handle_unknown_event(event)
            return

        if event_type in IGNORED_EVENTS:
            return

        handler = self.event_handlers.get(event_type)

        if handler is None:
            await self.handle_unknown_event(event)
            return

        await handler(event)

    async def handle_response_delta(self, event: Any) -> None:
        delta = getattr(event, "delta", "") or ""
        self.response_text += delta

    async def handle_response_text_done(self, event: Any) -> None:
        text = getattr(event, "text", "") or ""
        self.response_text += text

    async def handle_response_done(self, event: Any) -> None:
        extracted = self.extract_response_text(event)

        if extracted:
            self.response_text = extracted

        self.response_done.set()

    async def handle_transcript(self, event: Any) -> None:
        transcript = getattr(event, "transcript", None)

        if transcript:
            logger.info(f"[transcript] {transcript}")

    async def handle_error(self, event: Any) -> None:
        self.response_done.set()

    async def handle_log_event(self, event: Any) -> None:
        logger.info(f"[event] {event.type}")

    async def handle_unknown_event(self, event: Any) -> None:
        logger.info(f"[ignored] {getattr(event, 'type', None)}")

    def extract_response_text(self, event: Any) -> str:
        response = getattr(event, "response", None)
        if not response:
            return ""

        output = getattr(response, "output", None) or []
        parts: list[str] = []

        for item in output:
            content = getattr(item, "content", None) or []

            for block in content:
                text = (
                    getattr(block, "text", None)
                    or getattr(block, "transcript", None)
                    or getattr(block, "output_text", None)
                )

                if text:
                    parts.append(text)

        return "".join(parts).strip()

    def register_handler(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        self.event_handlers[event_type] = handler

    async def close(self) -> None:
        if self.closed:
            return

        self.closed = True

        if self.sender_task:
            self.audio_queue.put_nowait(None)
            await self.sender_task
            self.sender_task = None

        await self.client.close()

        if self.receive_task:
            await self.receive_task
            self.receive_task = None

        self.started = False
