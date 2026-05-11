from worker.observer.speaker.base import BaseSpeakerObserver, SpeakerData
from worker.observer.speaker.meet import MeetSpeakerObserver


def create_speaker_observer(
    provider: str,
    page,
    bot_name: str,
    recording_mode: str,
    on_speakers_change,
) -> BaseSpeakerObserver:
    if provider == "google_meet":
        return MeetSpeakerObserver(
            page=page,
            bot_name=bot_name,
            on_speakers_change=on_speakers_change,
            recording_mode=recording_mode,
        )

    raise RuntimeError(f"Unsupported speaker observer provider: {provider}")


__all__ = ["BaseSpeakerObserver", "SpeakerData", "create_speaker_observer"]
