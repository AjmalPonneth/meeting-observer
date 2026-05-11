from __future__ import annotations

import time

from worker.machine.state.base import BaseState
from worker.machine.type import MeetingStateType
from worker.webhook.payload import build_base_payload
from worker.webhook.type import WebhookType


class InCallState(BaseState):
    state_type = MeetingStateType.IN_CALL

    async def run(self):
        await self.context.event.send_once(
            WebhookType.IN_CALL_NOT_RECORDING,
            build_base_payload(self.context),
        )

        self.context.state.start_time = int(time.time())
        await self.context.observer.start(self.context.runtime.page)
        return self.transition(MeetingStateType.RECORDING)
