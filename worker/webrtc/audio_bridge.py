from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from worker.utils import load_script

SCRIPT_DIR = Path(__file__).parent / "scripts"
DEFAULT_AUDIO_CAPTURE_SCRIPT = SCRIPT_DIR / "bridge.js"


class WebRTCAudioBridge:
    def __init__(
        self,
        callback_name: str = "onMeetMixedAudioChunk",
        stop_function_name: str = "__meetAudioStop",
        script_path: str | Path = DEFAULT_AUDIO_CAPTURE_SCRIPT,
    ) -> None:
        self.callback_name = callback_name
        self.stop_function_name = stop_function_name
        self.script_path = Path(script_path)
        self.installed = False

    @property
    def script(self) -> str:
        return load_script(self.script_path)

    async def install(
        self,
        browser_context: Any,
        on_chunk: Callable[[dict], Awaitable[None]],
    ) -> None:
        if self.installed:
            return

        async def binding(source: Any, chunk: dict) -> None:
            await on_chunk(chunk)

        await browser_context.expose_binding(
            self.callback_name,
            binding,
        )

        await browser_context.add_init_script(self.script)

        self.installed = True

    async def verify(self, page: Any) -> dict:
        if page is None or page.is_closed():
            return {
                "ok": False,
                "reason": "page closed",
            }

        return await page.evaluate(
            """
            () => ({
              ok: true,
              href: location.href,
              injected: window.__meetAudioInjected === true,
              installed: window.__meetAudioCaptureInstalled === true,
              hasCallback: typeof window.onMeetMixedAudioChunk === "function",
              hasStop: typeof window.__meetAudioStop === "function",
              hasRTC: typeof window.RTCPeerConnection !== "undefined",
              rtcName: window.RTCPeerConnection?.name,
              hasMediaStreamTrackProcessor: typeof MediaStreamTrackProcessor !== "undefined",
              hasAudioContext: typeof AudioContext !== "undefined" || typeof webkitAudioContext !== "undefined",
            })
            """  # noqa: E501
        )

    async def stop(self, page: Any) -> None:
        if page is None or page.is_closed():
            return

        await page.evaluate(
            """
            async (stopFunctionName) => {
              if (typeof window[stopFunctionName] === "function") {
                await window[stopFunctionName]();
              }
            }
            """,
            self.stop_function_name,
        )
