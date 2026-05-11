from worker.provider.google_meet import MeetProvider


def get_provider(provider: str):
    normalized = provider.lower()

    if normalized in {"google_meet", "meet"}:
        return MeetProvider()

    raise RuntimeError(f"Unsupported meeting provider: {provider}")
