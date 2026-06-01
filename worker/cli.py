from __future__ import annotations

import argparse
import logging

from aiohttp import web

from worker.http.app import create_app
from worker.logging import configure_logging

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meeting-observer",
        description="Run the meeting observer worker.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    start = subparsers.add_parser("start")

    start.add_argument("--host", default="0.0.0.0")
    start.add_argument("--port", type=int, default=8000)
    start.add_argument("--log-level", default="info")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    configure_logging(args.log_level)

    logger.info(
        "starting meeting observer host=%s port=%s",
        args.host,
        args.port,
    )

    app = create_app()
    web.run_app(
        app,
        host=args.host,
        port=args.port,
        access_log=logging.getLogger("aiohttp.access"),
    )


if __name__ == "__main__":
    main()
