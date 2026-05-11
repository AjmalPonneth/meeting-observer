from __future__ import annotations

import time

from worker.llm.model import MeetingSummary, Participant
from worker.machine.state.base import BaseState
from worker.machine.type import MeetingEndReason, MeetingStateType
from worker.webhook.payload import (
    build_call_ended_payload,
    build_recording_succeeded_payload,
)
from worker.webhook.type import WebhookType


class FinalizingState(BaseState):
    state_type = MeetingStateType.FINALIZING

    async def run(self):
        self.context.state.exit_time = int(time.time())
        await self.context.event.send_once(
            WebhookType.CALL_ENDED,
            build_call_ended_payload(self.context),
        )

        await self.context.observer.stop_capture(self.context.runtime.page)
        summary_text = await self.context.observer.request_summary(final=True)
        self.context.state.raw_summary = summary_text

        if summary_text:
            self.context.state.final_summary = MeetingSummary.from_json(summary_text)
        else:
            self.context.state.final_summary = MeetingSummary()

        if not self.context.state.final_summary.participants:
            self.context.state.final_summary.participants = [
                Participant(name=name, role=None)
                for name in self.context.observer.get_participant_names()
            ]

        if not self.context.state.end_reason:
            self.context.state.set_end_reason(MeetingEndReason.COMPLETED)

        await self.context.event.send_once(
            WebhookType.RECORDING_SUCCEEDED,
            build_recording_succeeded_payload(self.context),
        )
        return self.transition(MeetingStateType.TERMINATED)
