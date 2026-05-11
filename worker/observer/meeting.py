import logging
from typing import Any

from worker.llm.client import RealtimeLLMClient
from worker.llm.session import RealtimeMeetingSession
from worker.observer.audio import AudioBuffer
from worker.observer.event import (
    AudioChunkReceived,
    EventListener,
)
from worker.observer.speaker import (
    BaseSpeakerObserver,
    SpeakerData,
    create_speaker_observer,
)
from worker.webrtc.audio_bridge import WebRTCAudioBridge
from worker.webrtc.audio_codec import downsample_48k_to_24k, float32_to_pcm16_base64

logger = logging.getLogger(__name__)


class AudioCaptureObserver:
    def __init__(
        self,
        listener: EventListener,
        bridge: WebRTCAudioBridge | None = None,
    ) -> None:
        self.listener = listener
        self.bridge = bridge or WebRTCAudioBridge()
        self.enabled = False

    async def enable_context(self, browser_context: Any) -> None:
        await self.bridge.install(browser_context, self.on_audio_chunk)
        self.enabled = True

    async def on_audio_chunk(self, chunk: dict) -> None:
        if not self.enabled:
            return

        await self.listener.publish(
            AudioChunkReceived(
                audio_data=chunk.get("audioData", []),
                sample_rate=chunk.get("sampleRate", 48000),
                timestamp=chunk.get("timestamp", 0),
            )
        )

    async def stop(self, page: Any) -> None:
        self.enabled = False
        await self.bridge.stop(page)


class MeetingObserver:
    def __init__(
        self,
        provider: str,
        bot_name: str,
        recording_mode: str,
        listener: EventListener | None = None,
        realtime_client: RealtimeLLMClient | None = None,
        audio_buffer: AudioBuffer | None = None,
    ) -> None:
        self.provider = provider
        self.bot_name = bot_name

        self.recording_mode = recording_mode

        self.listener = listener or EventListener()

        self.realtime_client = realtime_client or RealtimeLLMClient()
        self.realtime = RealtimeMeetingSession(self.realtime_client)

        self.audio = AudioCaptureObserver(self.listener)
        self.audio_buffer = audio_buffer or AudioBuffer(max_samples=9600)

        self.speakers: BaseSpeakerObserver | None = None

        self.current_speaker: str | None = None
        self.participants: set[str] = set()
        self.audio_chunks_received = 0

        self.started = False
        self.stopped = False

        self.listener.subscribe(AudioChunkReceived, self.handle_audio_chunk)

    async def enable_context(self, browser_context: Any) -> None:
        await self.audio.enable_context(browser_context)

    async def start(self, page: Any) -> None:
        if self.started:
            return

        self.started = True
        self.stopped = False
        self.capture_stopped = False

        await self.realtime.start()

        self.speakers = create_speaker_observer(
            provider=self.provider,
            page=page,
            bot_name=self.bot_name,
            recording_mode=self.recording_mode,
            on_speakers_change=self.on_speakers_change,
        )

        await self.speakers.start()

    async def stop_capture(self, page: Any):
        if self.stopped:
            return

        self.stopped = True

        if self.speakers:
            await self.speakers.stop()

        if self.audio:
            await self.audio.stop(page=page)

    async def stop(self, page: Any) -> None:
        await self.stop_capture(page)

        if self.realtime:
            await self.realtime.close()

    async def request_summary(
        self,
        *,
        final: bool = True,
    ) -> str | None:
        logger.info("Realtime meeting summary requested.")
        return await self.realtime.request_summary(
            final=final,
            context={
                "last_known_speaker": self.current_speaker,
                "participants": self.get_participant_names(),
            },
        )

    async def on_speakers_change(self, speakers: list[SpeakerData]) -> None:
        non_bot = [speaker for speaker in speakers if not speaker.is_bot]

        for speaker in non_bot:
            self.participants.add(speaker.name)

        speaker = self.resolve_active_speaker(non_bot)

        if speaker == self.current_speaker:
            return

        self.current_speaker = speaker

    async def handle_audio_chunk(self, event: AudioChunkReceived) -> None:
        if self.stopped:
            return

        self.audio_chunks_received += 1

        chunks = self.audio_buffer.add(event.audio_data)
        for buffered_audio in chunks:
            downsampled = downsample_48k_to_24k(buffered_audio)
            audio_b64 = float32_to_pcm16_base64(downsampled)
            await self.realtime.send_audio(audio_b64)
            if self.audio_chunks_received % 100 == 0:
                logger.info(
                    (
                        "streaming audio to realtime "
                        "chunks_received=%s "
                        "chunks_sent=%s "
                        "speaker=%s"
                    ),
                    self.audio_chunks_received,
                    self.realtime.audio_chunks_sent,
                    self.current_speaker,
                )

    def resolve_active_speaker(self, speakers: list[SpeakerData]) -> str | None:
        active = [speaker for speaker in speakers if speaker.is_speaking]

        if active:
            return active[0].name

        if len(speakers) == 1:
            return speakers[0].name

        return self.current_speaker

    def get_participant_names(self) -> list[str]:
        return sorted(self.participants)
