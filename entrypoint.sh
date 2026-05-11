#!/usr/bin/env bash
set -e

export DISPLAY=:99

rm -f /tmp/.X99-lock

Xvfb "$DISPLAY" -screen 0 1280x720x24 -ac +extension RANDR &
XVFB_PID=$!

cleanup() {
  echo "Cleaning up..."
  kill "$XVFB_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

uv run gunicorn worker.http.app:app \
  --worker-class aiohttp.GunicornWebWorker \
  --workers 1 \
  --bind 0.0.0.0:8000 \
  --timeout 0

