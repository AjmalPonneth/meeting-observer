from __future__ import annotations

import logging
from typing import Any

import aiohttp

from worker.session.config import SessionConfig
from worker.webhook.type import WebhookType

logger = logging.getLogger(__name__)


class Client:
    def __init__(self, config: SessionConfig) -> None:
        self.config = config
        self.sent_events: set[WebhookType] = set()

    async def send_once(
        self,
        event_type: WebhookType,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if event_type in self.sent_events:
            return

        self.sent_events.add(event_type)
        await self.send(event_type, payload)

    async def send(
        self,
        event_type: WebhookType,
        payload: dict[str, Any] | None = None,
    ) -> None:
        consumer = self.config.consumer

        if not consumer.webhook_url:
            return

        status = {"code": event_type, **(payload or {})}
        webhook_payload = {
            "event": "bot.status_change",
            "data": {
                "bot_id": self.config.bot_uuid,
                "event_uuid": None,
                "status": status,
                "extra": consumer.extra or {},
            },
        }

        headers = {}
        if consumer.api_key:
            headers["Authorization"] = f"Bearer {consumer.api_key}"

        try:
            async with aiohttp.request(
                "POST",
                consumer.webhook_url,
                json=webhook_payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as response:
                if response.status >= 400:
                    logger.warning(
                        "webhook failed code=%s status=%s",
                        event_type,
                        response,
                    )
                    return

                logger.info("webhook sent code=%s status=%s", event_type, response)
        except aiohttp.ClientError:
            logger.exception("webhook request failed code=%s", event_type)
