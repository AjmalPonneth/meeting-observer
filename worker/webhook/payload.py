from __future__ import annotations

from worker.llm.model import MeetingSummary
from worker.session.context import MeetingContext
from worker.webhook.schema import (
    BaseWebhookStatus,
    CallEndedWebhookStatus,
    ErrorPayload,
    InCallRecordingWebhookStatus,
    MeetingErrorWebhookStatus,
    MeetingPayload,
    RecordingFailedWebhookStatus,
    RecordingSucceededWebhookStatus,
    StatsPayload,
    StatusPayload,
    SummaryStatusPayload,
    TimingPayload,
)


def build_meeting(context: MeetingContext) -> MeetingPayload:
    payload: MeetingPayload = {
        "bot_id": context.config.bot_uuid,
        "meeting_url": context.config.meeting_url,
        "provider": context.config.provider,
        "bot_name": context.config.bot_name,
        "recording_mode": context.config.recording_mode,
    }

    return payload


def build_timing(context: MeetingContext) -> TimingPayload:
    payload: TimingPayload = {
        "start_time": context.state.start_time,
        "exit_time": context.state.exit_time,
        "duration_seconds": context.state.duration_seconds(),
    }

    return payload


def build_status(context: MeetingContext) -> StatusPayload:
    payload: StatusPayload = {
        "end_reason": str(context.state.end_reason)
        if context.state.end_reason
        else None,
        "has_error": context.state.has_error(),
        "error_message": context.state.get_error_message()
        if context.state.has_error()
        else None,
    }

    return payload


def build_base_payload(context: MeetingContext) -> BaseWebhookStatus:
    payload: BaseWebhookStatus = {
        "meeting": build_meeting(context),
        "timing": build_timing(context),
        "status": build_status(context),
    }
    return payload


def build_call_ended_payload(context: MeetingContext) -> CallEndedWebhookStatus:
    payload: CallEndedWebhookStatus = {
        "meeting": build_meeting(context),
        "timing": build_timing(context),
        "status": build_status(context),
    }

    return payload


def build_in_call_recording_payload(
    context: MeetingContext,
) -> InCallRecordingWebhookStatus:
    payload: InCallRecordingWebhookStatus = {
        "meeting": build_meeting(context),
        "timing": build_timing(context),
        "status": build_status(context),
        "recording": {
            "start_time": context.state.start_time,
        },
    }

    return payload


def build_summary_status(context: MeetingContext) -> SummaryStatusPayload:
    summary = context.state.final_summary or MeetingSummary()

    payload: SummaryStatusPayload = {
        "has_summary": bool(summary.summary),
        "has_raw_summary": bool(context.state.raw_summary),
    }

    return payload


def build_stats(context: MeetingContext) -> StatsPayload:
    payload: StatsPayload = {
        "audio_chunks_received": context.observer.audio_chunks_received,
        "current_speaker": context.observer.current_speaker,
        "participants": context.observer.get_participant_names(),
        "realtime_audio_chunks_queued": context.observer.realtime.audio_chunks_queued,
        "realtime_audio_chunks_sent": context.observer.realtime.audio_chunks_sent,
        "realtime_audio_chunks_dropped": context.observer.realtime.audio_chunks_dropped,
    }

    return payload


def build_recording_succeeded_payload(
    context: MeetingContext,
) -> RecordingSucceededWebhookStatus:
    summary = context.state.final_summary or MeetingSummary()

    payload: RecordingSucceededWebhookStatus = {
        "meeting": build_meeting(context),
        "timing": build_timing(context),
        "status": build_status(context),
        "summary": summary.to_dict(),
        "raw_summary": context.state.raw_summary,
        "summary_status": build_summary_status(context),
        "stats": build_stats(context),
    }

    return payload


def build_error(context: MeetingContext) -> ErrorPayload:
    payload: ErrorPayload = {
        "message": context.state.get_error_message(),
        "type": context.state.error.__class__.__name__ if context.state.error else None,
    }

    return payload


def build_recording_failed_payload(
    context: MeetingContext,
) -> RecordingFailedWebhookStatus:
    payload: RecordingFailedWebhookStatus = {
        "meeting": build_meeting(context),
        "timing": build_timing(context),
        "status": build_status(context),
        "error": build_error(context),
    }

    return payload


def build_meeting_error_payload(
    context: MeetingContext,
) -> MeetingErrorWebhookStatus:
    payload: MeetingErrorWebhookStatus = {
        "meeting": build_meeting(context),
        "timing": build_timing(context),
        "status": build_status(context),
        "error": build_error(context),
    }
    return payload
