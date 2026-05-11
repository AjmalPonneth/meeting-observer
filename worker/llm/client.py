from __future__ import annotations

import logging
import os
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)
API_KEY = os.environ.get("OPENAI_API_KEY")


class RealtimeLLMClient:
    def __init__(self, model: str = "gpt-realtime") -> None:
        self.client = AsyncOpenAI(api_key=API_KEY)
        self.model = model

        self.connection: Any | None = None

        self.connected = False
        self.connecting = False
        self.closing = False

    async def connect(self) -> None:
        if self.connected or self.connecting:
            return

        if self.closing:
            raise RuntimeError("RealtimeLLMClient is closing")

        self.connecting = True

        try:
            self.connection = await self.client.realtime.connect(
                model=self.model,
            ).__aenter__()

            self.connected = True

        finally:
            self.connecting = False

    async def update_session(self, session: dict[str, Any]) -> None:
        conn = self.require_connection()
        await conn.session.update(session=session)

    async def append_audio(self, audio_b64: str) -> None:
        conn = self.require_connection()
        await conn.input_audio_buffer.append(audio=audio_b64)

    async def create_response(self, response: dict[str, Any]) -> None:
        conn = self.require_connection()
        await conn.response.create(response=response)

    async def receive(self):
        conn = self.require_connection()

        async for event in conn:
            yield event

    def require_connection(self) -> Any:
        if not self.connected or self.connection is None or self.closing:
            raise RuntimeError("Realtime connection is not established")

        return self.connection

    async def close(self) -> None:
        if self.closing:
            return

        self.closing = True
        self.connected = False

        if self.connection:
            await self.connection.close()
            self.connection = None
