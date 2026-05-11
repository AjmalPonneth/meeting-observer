from __future__ import annotations

from enum import StrEnum


class MeetingStateType(StrEnum):
    INITIALIZATION = "initialization"
    WAITING_ROOM = "waiting_room"
    IN_CALL = "in_call"
    RECORDING = "recording"
    FINALIZING = "finalizing"
    ERROR = "error"
    TERMINATED = "terminated"


class MeetingEndReason(StrEnum):
    INTERNAL = "internal"
    INVALID_MEETING_URL = "invalid_meeting_url"
    BOT_REJECTED = "bot_rejected"
    BOT_REMOVED = "bot_removed"
    WAITING_ROOM_TIMEOUT = "waiting_room_timeout"
    CALL_ENDED = "call_ended"
    API_REQUEST = "api_request"
    COMPLETED = "completed"


NORMAL_END_REASONS = {
    MeetingEndReason.CALL_ENDED,
    MeetingEndReason.API_REQUEST,
    MeetingEndReason.COMPLETED,
}
