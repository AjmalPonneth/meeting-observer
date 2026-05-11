from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConsumerConfig:
    webhook_url: str | None = None
    api_key: str | None = None
    extra: dict[str, Any] | None = None


@dataclass(frozen=True)
class SessionConfig:
    bot_uuid: str
    meeting_url: str
    provider: str = "google_meet"
    bot_name: str = "Meeting Bot"
    recording_mode: str = "speaker_view"
    retry_count: int = 0
    consumer: ConsumerConfig = field(default_factory=ConsumerConfig)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> SessionConfig:
        meeting_url = (payload.get("meeting_url") or "").strip()
        bot_uuid = (payload.get("bot_uuid") or "").strip()

        if not meeting_url:
            raise RuntimeError("Missing required parameter: meeting_url")
        if not bot_uuid:
            raise RuntimeError("Missing required parameter: bot_uuid")

        consumer = payload.get("consumer") or {}

        return cls(
            bot_uuid=bot_uuid,
            meeting_url=meeting_url,
            provider=payload.get("provider", "google_meet"),
            bot_name=payload.get("bot_name", "Meeting Bot"),
            recording_mode=normalize_recording_mode(
                payload.get("recording_mode", "speaker_view")
            ),
            retry_count=int(payload.get("retry_count") or 0),
            consumer=ConsumerConfig(
                webhook_url=consumer.get("webhook_url"),
                api_key=consumer.get("api_key"),
                extra=consumer.get("extra"),
            ),
        )


def normalize_recording_mode(mode: str) -> str:
    if mode in {"speaker_view", "SpeakerView"}:
        return "speaker_view"
    if mode in {"gallery_view", "GalleryView"}:
        return "gallery_view"
    if mode in {"audio_only", "AudioOnly"}:
        return "audio_only"
    return "speaker_view"
