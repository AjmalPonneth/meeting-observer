from __future__ import annotations


class WebhookType:
    JOINING_CALL = "joining_call"
    IN_WAITING_ROOM = "in_waiting_room"
    IN_CALL_NOT_RECORDING = "in_call_not_recording"
    IN_CALL_RECORDING = "in_call_recording"

    CALL_ENDED = "call_ended"

    RECORDING_SUCCEEDED = "recording_succeeded"
    RECORDING_FAILED = "recording_failed"

    MEETING_ERROR = "meeting_error"

    INVALID_MEETING_URL = "invalid_meeting_url"
    BOT_REJECTED = "bot_rejected"
    BOT_REMOVED = "bot_removed"
    WAITING_ROOM_TIMEOUT = "waiting_room_timeout"
