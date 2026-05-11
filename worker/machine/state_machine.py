from __future__ import annotations

import logging

from worker.machine.state import get_state_instance
from worker.machine.type import NORMAL_END_REASONS, MeetingEndReason, MeetingStateType
from worker.session.context import MeetingContext

logger = logging.getLogger(__name__)


class StateMachine:
    def __init__(self) -> None:
        self.context: MeetingContext | None = None
        self.current_state = MeetingStateType.INITIALIZATION

    def bind(self, context: MeetingContext) -> None:
        self.context = context

    async def start(self) -> None:
        if self.context is None:
            raise RuntimeError("StateMachine context is not bound")

        while self.current_state != MeetingStateType.TERMINATED:
            state = get_state_instance(self.current_state, self.context)
            transition = await state.execute()

            logger.info(
                "state transition %s -> %s",
                self.current_state,
                transition.next_state,
            )
            self.current_state = transition.next_state
            self.context = transition.context

    async def stop_meeting(self, reason: MeetingEndReason) -> None:
        if self.context is None:
            return

        self.context.state.set_end_reason(reason)

    def was_successful(self) -> bool:
        if self.context is None:
            return False

        if self.context.state.has_error():
            return False

        return self.context.state.end_reason in NORMAL_END_REASONS

    def get_error(self) -> Exception | None:
        if self.context and self.context.state.has_error():
            return Exception(self.context.state.get_error_message())

        return None
