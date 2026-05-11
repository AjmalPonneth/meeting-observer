from __future__ import annotations

import asyncio
import logging

from aiohttp import web

from worker.session.meeting_session import MeetingSession

logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


async def run_meeting_session(payload: dict) -> None:
    bot_uid = payload.get("bot_uuid")
    try:
        async with MeetingSession(payload) as session:
            await session.run()

        logger.info(f"Meeting session completed bot_uid {bot_uid}")
    except asyncio.CancelledError:
        logger.warning(f"Meeting session cancelled bot_uid={bot_uid}")
        raise
    except Exception:
        logger.exception(f"Meeting session failed bot_uid={bot_uid}")


@routes.post("/meetings/observe")
async def observe_meeting(request: web.Request) -> web.Response:
    payload = await request.json()

    task = asyncio.create_task(
        run_meeting_session(payload),
        name=f"meeting:{payload.get('bot_uuid') or 'unknown'}",
    )
    tasks: set[asyncio.Task] = request.app["meeting_tasks"]
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return web.json_response(
        {
            "status": "accepted",
            "message": "meeting observer started",
        },
        status=202,
    )


def setup_routes(app: web.Application) -> None:
    app["meeting_tasks"] = set()
    app.add_routes(routes)
