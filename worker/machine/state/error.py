from __future__ import annotations

import logging
import time

from worker.machine.state.base import BaseState
from worker.machine.type import MeetingStateType
from worker.webhook.payload import (
    build_call_ended_payload,
    build_meeting_error_payload,
    build_recording_failed_payload,
)
from worker.webhook.type import WebhookType

logger = logging.getLogger(__name__)


class ErrorState(BaseState):
    state_type = MeetingStateType.ERROR

    async def run(self):
        logger.error(
            "meeting entered error state reason=%s message=%s",
            self.context.state.end_reason,
            self.context.state.get_error_message(),
        )

        self.context.state.exit_time = int(time.time())

        await self.context.event.send_once(
            WebhookType.MEETING_ERROR,
            build_meeting_error_payload(self.context),
        )

        await self.context.event.send_once(
            WebhookType.CALL_ENDED,
            build_call_ended_payload(self.context),
        )

        await self.context.event.send_once(
            WebhookType.RECORDING_FAILED,
            build_recording_failed_payload(self.context),
        )
        return self.transition(MeetingStateType.TERMINATED)
