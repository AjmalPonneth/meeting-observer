from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from worker.observer.speaker.base import BaseSpeakerObserver, SpeakerData
from worker.utils import load_script

SpeakerCallback = Callable[[list[SpeakerData]], Awaitable[None]]
SCRIPT_DIR = Path(__file__).resolve().parent / "scripts"


class MeetSpeakerObserver(BaseSpeakerObserver):
    def __init__(
        self,
        page: Any,
        bot_name: str,
        on_speakers_change: SpeakerCallback,
        recording_mode: str = "speaker_view",
    ) -> None:
        self.page = page
        self.bot_name = bot_name
        self.recording_mode = recording_mode
        self.on_speakers_change = on_speakers_change

        self.running = False
        self.callback_name = "meetSpeakersChanged"
        self.cleanup_name = "meetObserverCleanup"

    async def start(self) -> None:
        if self.running:
            return

        await self.open_people_panel()
        await self.expose_callback()
        await self.inject_observer()

        self.running = True

    async def stop(self) -> None:
        if not self.running:
            return

        self.running = False

        if self.page is None or self.page.is_closed():
            return

        await self.page.evaluate(
            """
            (cleanupName) => {
              if (typeof window[cleanupName] === "function") {
                window[cleanupName]();
              }
            }
            """,
            self.cleanup_name,
        )

    async def open_people_panel(self) -> None:
        script = load_script(SCRIPT_DIR / "open_people_panel.js")

        await self.page.evaluate(script)

    async def expose_callback(self) -> None:
        async def callback(speakers: list[dict]) -> None:
            parsed = self.parse_speakers(speakers)

            if not parsed:
                return

            await self.on_speakers_change(parsed)

        try:
            await self.page.expose_function(
                self.callback_name,
                callback,
            )
        except Exception as exc:
            # Playwright does not allow exposing the same name twice.
            # In normal flow this should not happen, but reloads/retries can hit it.
            if "has been already registered" not in str(exc):
                raise

    async def inject_observer(self) -> None:
        script = load_script(SCRIPT_DIR / "inject_observer.js")

        await self.page.evaluate(
            script,
            {
                "recordingMode": self.recording_mode,
                "botName": self.bot_name,
                "callbackName": self.callback_name,
                "cleanupName": self.cleanup_name,
                "speakerLatency": 0,
                "mutationDebounce": 50,
                "checkInterval": 10_000,
                "freezeTimeout": 8_000,
            },
        )

    def parse_speakers(self, speakers: list[dict]) -> list[SpeakerData]:
        parsed: list[SpeakerData] = []

        bot_name = self.bot_name.strip().lower()

        for item in speakers:
            if not isinstance(item, dict):
                continue

            name = str(item.get("name") or "").strip()

            if not name:
                continue

            parsed.append(
                SpeakerData(
                    name=name,
                    is_speaking=bool(item.get("isSpeaking") or item.get("is_speaking")),
                    is_bot=name.lower() == bot_name,
                )
            )
        return parsed
