from __future__ import annotations

from worker.machine.state.base import BaseState
from worker.machine.type import MeetingEndReason, MeetingStateType
from worker.webhook.payload import build_base_payload
from worker.webhook.type import WebhookType


class WaitingRoomState(BaseState):
    state_type = MeetingStateType.WAITING_ROOM

    async def run(self):
        page = self.context.runtime.page
        provider = self.context.provider

        await provider.open_page(page, self.context.config.meeting_url)
        if await provider.detect_access_denied(page):
            await self.context.event.send_once(
                WebhookType.BOT_REJECTED,
                build_base_payload(self.context),
            )

            return self.fail_with(
                MeetingEndReason.BOT_REJECTED,
                "Google Meet blocked the bot from joining this meeting",
            )

        waiting = await provider.detect_waiting_room(page)
        if waiting:
            await self.context.event.send_once(
                WebhookType.IN_WAITING_ROOM,
                build_base_payload(self.context),
            )

        await provider.join_meeting(page)

        joined = await provider.wait_until_joined(page, timeout_ms=30000)
        if not joined:
            await self.context.event.send_once(
                WebhookType.WAITING_ROOM_TIMEOUT,
                build_base_payload(self.context),
            )

            return self.fail_with(
                MeetingEndReason.WAITING_ROOM_TIMEOUT,
                "Timed out waiting to join the meeting",
            )

        return self.transition(MeetingStateType.IN_CALL)
