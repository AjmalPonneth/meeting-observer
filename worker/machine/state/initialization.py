from __future__ import annotations

from worker.machine.state.base import BaseState
from worker.machine.type import MeetingEndReason, MeetingStateType
from worker.webhook.payload import build_base_payload
from worker.webhook.type import WebhookType


class InitializationState(BaseState):
    state_type = MeetingStateType.INITIALIZATION

    async def run(self):
        meeting_url = self.context.config.meeting_url.strip()

        if not meeting_url:
            await self.context.event.send_once(
                WebhookType.INVALID_MEETING_URL,
                build_base_payload(self.context),
            )

            return self.fail_with(
                MeetingEndReason.INVALID_MEETING_URL,
                "Invalid meeting URL",
            )

        await self.context.observer.enable_context(self.context.runtime.browser_context)

        await self.context.event.send_once(
            WebhookType.JOINING_CALL,
            build_base_payload(self.context),
        )
        return self.transition(MeetingStateType.WAITING_ROOM)
