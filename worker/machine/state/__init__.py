from __future__ import annotations

from worker.machine.state.error import ErrorState
from worker.machine.state.finalizing import FinalizingState
from worker.machine.state.in_call import InCallState
from worker.machine.state.initialization import InitializationState
from worker.machine.state.recording import RecordingState
from worker.machine.state.waiting_room import WaitingRoomState
from worker.machine.type import MeetingStateType
from worker.session.context import MeetingContext

STATE_MAP = {
    MeetingStateType.INITIALIZATION: InitializationState,
    MeetingStateType.WAITING_ROOM: WaitingRoomState,
    MeetingStateType.IN_CALL: InCallState,
    MeetingStateType.RECORDING: RecordingState,
    MeetingStateType.FINALIZING: FinalizingState,
    MeetingStateType.ERROR: ErrorState,
}


def get_state_instance(state_type: MeetingStateType, context: MeetingContext):
    state_class = STATE_MAP[state_type]
    return state_class(context)
