from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from worker.machine.type import MeetingEndReason, MeetingStateType
from worker.session.context import MeetingContext

logger = logging.getLogger(__name__)


@dataclass()
class StateTransition:
    next_state: MeetingStateType
    context: MeetingContext


class BaseState:
    state_type: MeetingStateType

    def __init__(self, context: MeetingContext) -> None:
        self.context = context

    async def execute(self) -> StateTransition:
        try:
            return await self.run()
        except asyncio.CancelledError:
            raise

        except Exception as error:
            logger.exception(
                "state execution failed state=%s",
                self.state_type,
            )
            self.context.state.set_error(
                MeetingEndReason.INTERNAL,
                str(error),
                error,
            )
            if self.state_type == MeetingStateType.ERROR:
                return self.transition(MeetingStateType.TERMINATED)
            return self.transition(MeetingStateType.ERROR)

    async def run(self) -> StateTransition:
        raise NotImplementedError

    def transition(self, next_state: MeetingStateType) -> StateTransition:
        return StateTransition(next_state=next_state, context=self.context)

    def fail_with(
        self,
        reason: MeetingEndReason,
        message: str,
        next_state: MeetingStateType = MeetingStateType.ERROR,
    ) -> StateTransition:
        self.context.state.set_error(reason, message)
        return self.transition(next_state)
