from __future__ import annotations

import argparse
import logging
import os
import signal
import subprocess

from worker.logging import configure_logger

logger = logging.getLogger(__name__)


def build_gunicorn_command(args) -> list[str]:
    command = [
        "gunicorn",
        "worker.http.app:app",
        "--worker-class",
        "aiohttp.worker.GunicornWebWorker",
        "--bind",
        f"{args.host}:{args.port}",
        "--workers",
        str(args.workers),
        "--log-level",
        args.log_level,
        "--timeout",
        str(args.timeout),
        "--graceful-timeout",
        str(args.graceful_timeout),
        "--keep-alive",
        str(args.keepalive),
        "--max-requests",
        str(args.max_requests),
        "--max-requests-jitter",
        str(args.max_requests_jitter),
        "--access-logfile",
        "-",
        "--error-logfile",
        "-",
        "--capture-output",
        "--enable-stdio-inheritance",
    ]

    if args.reload:
        command.append("--reload")

    return command


def run_server(args) -> int:
    configure_logger(args.log_level)

    env = os.environ.copy()
    env["LOG_LEVEL"] = args.log_level.upper()

    logger.info(
        "starting meeting observer host=%s port=%s workers=%s",
        args.host,
        args.port,
        args.workers,
    )

    process = subprocess.Popen(build_gunicorn_command(args), env=env)

    def shutdown(signum, frame):
        logger.info("shutdown signal received signal=%s", signum)

        if process.poll() is None:
            process.terminate()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    return process.wait()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="meeting-observer")

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    start = subparsers.add_parser(
        "start",
        help="Start meeting observer server",
    )

    start.add_argument("--host", default="0.0.0.0")
    start.add_argument("--port", type=int, default=8000)
    start.add_argument("--workers", type=int, default=1)
    start.add_argument("--log-level", default="info")
    start.add_argument("--reload", action="store_true")

    start.add_argument("--timeout", type=int, default=0)
    start.add_argument("--graceful-timeout", type=int, default=60)
    start.add_argument("--keepalive", type=int, default=5)
    start.add_argument("--max-requests", type=int, default=100)
    start.add_argument("--max-requests-jitter", type=int, default=20)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "start":
        raise SystemExit(run_server(args))

    parser.print_help()
    raise SystemExit(1)


if __name__ == "__main__":
    main()
