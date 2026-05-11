from __future__ import annotations

from typing import Any, TypedDict


class MeetingPayload(TypedDict):
    bot_id: str
    meeting_url: str
    provider: str
    bot_name: str
    recording_mode: str


class TimingPayload(TypedDict):
    start_time: int | None
    exit_time: int | None
    duration_seconds: int | None


class StatusPayload(TypedDict):
    end_reason: str | None
    has_error: bool
    error_message: str | None


class RecordingPayload(TypedDict):
    start_time: int | None


class SummaryStatusPayload(TypedDict):
    has_summary: bool
    has_raw_summary: bool


class StatsPayload(TypedDict):
    audio_chunks_received: int
    current_speaker: str | None
    participants: list[str]

    realtime_audio_chunks_queued: int
    realtime_audio_chunks_sent: int
    realtime_audio_chunks_dropped: int


class ErrorPayload(TypedDict):
    message: str | None
    type: str | None


class BaseWebhookStatus(TypedDict):
    meeting: MeetingPayload
    timing: TimingPayload
    status: StatusPayload


class CallEndedWebhookStatus(TypedDict):
    meeting: MeetingPayload
    timing: TimingPayload
    status: StatusPayload


class InCallRecordingWebhookStatus(TypedDict):
    meeting: MeetingPayload
    timing: TimingPayload
    status: StatusPayload
    recording: RecordingPayload


class RecordingSucceededWebhookStatus(TypedDict):
    meeting: MeetingPayload
    timing: TimingPayload
    status: StatusPayload
    summary: dict[str, Any]
    raw_summary: str | None
    summary_status: SummaryStatusPayload
    stats: StatsPayload


class RecordingFailedWebhookStatus(TypedDict):
    meeting: MeetingPayload
    timing: TimingPayload
    status: StatusPayload
    error: ErrorPayload


class MeetingErrorWebhookStatus(TypedDict):
    meeting: MeetingPayload
    timing: TimingPayload
    status: StatusPayload
    error: ErrorPayload


class WebhookData(TypedDict):
    bot_id: str
    event_uuid: str | None
    status: dict[str, Any]
    extra: dict[str, Any]


class WebhookEnvelope(TypedDict):
    event: str
    data: WebhookData
