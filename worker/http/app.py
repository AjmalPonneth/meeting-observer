import asyncio

from aiohttp import web

from worker.http.routes import setup_routes
from worker.runtime.registry import stop_worker_runtime


async def on_cleanup(app: web.Application) -> None:
    tasks = app.get("meeting_tasks", set())

    for task in list(tasks):
        task.cancel()

    if tasks:
        await asyncio.gather(*list(tasks), return_exceptions=True)

    tasks.clear()
    await stop_worker_runtime()


def create_app() -> web.Application:
    app = web.Application()
    app["meeting_tasks"] = set()

    setup_routes(app)
    app.on_cleanup.append(on_cleanup)
    return app


app = create_app()
