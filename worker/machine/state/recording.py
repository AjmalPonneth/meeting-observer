from __future__ import annotations

import asyncio

from worker.machine.state.base import BaseState
from worker.machine.type import MeetingEndReason, MeetingStateType
from worker.webhook.payload import build_in_call_recording_payload
from worker.webhook.type import WebhookType


class RecordingState(BaseState):
    state_type = MeetingStateType.RECORDING

    async def run(self):
        await self.context.event.send_once(
            WebhookType.IN_CALL_RECORDING,
            build_in_call_recording_payload(self.context),
        )
        page = self.context.runtime.page
        provider = self.context.provider

        while True:
            should_end = await provider.should_end(page)
            if should_end:
                self.context.state.set_end_reason(MeetingEndReason.CALL_ENDED)
                return self.transition(MeetingStateType.FINALIZING)
            await asyncio.sleep(2)
