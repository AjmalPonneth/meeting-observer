from __future__ import annotations


class AudioBuffer:
    def __init__(self, max_samples: int = 9600) -> None:
        self.max_samples = max_samples
        self.samples: list[float] = []

    def add(self, chunk: list[float]) -> list[list[float]]:
        self.samples.extend(chunk)

        ready: list[list[float]] = []

        while len(self.samples) >= self.max_samples:
            ready.append(self.samples[: self.max_samples])
            self.samples = self.samples[self.max_samples :]

        return ready

    def clear(self) -> None:
        self.samples.clear()
