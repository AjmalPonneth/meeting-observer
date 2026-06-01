from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import BrowserContext, Playwright, async_playwright

PLAYWRIGHT_ARGS = [
    "--window-size=1280,860",
    "--window-position=0,0",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--lang=en-US",
    "--accept-lang=en-US,en",
    "--autoplay-policy=no-user-gesture-required",
    "--disable-blink-features=AutomationControlled",
    "--disable-audio-input",
    "--ignore-certificate-errors",
    "--allow-insecure-localhost",
]


@dataclass
class WorkerRuntime:
    playwright: Playwright | None = None

    async def start(self) -> None:
        if self.playwright:
            return

        self.playwright = await async_playwright().start()

    async def new_browser_context(self) -> BrowserContext:
        if self.playwright is None:
            raise RuntimeError("WorkerRuntime is not started")

        user_data_dir = Path(
            f"/tmp/playwright-worker-profile-{os.getpid()}-{uuid.uuid4().hex}"
        )
        return await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            viewport=None,
            args=PLAYWRIGHT_ARGS,
            permissions=["camera", "microphone"],
            ignore_https_errors=True,
        )

    async def stop(self) -> None:
        if self.playwright is None:
            return

        await self.playwright.stop()
        self.playwright = None

        await asyncio.sleep(0)
