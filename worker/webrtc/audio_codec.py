from __future__ import annotations

import base64
from array import array


def downsample_48k_to_24k(samples: list[float]) -> list[float]:
    """
    Simple 48kHz -> 24kHz downsampling.

    Drops every alternate sample.
    """

    return samples[::2]


def float32_to_pcm16_base64(samples: list[float]) -> str:
    """Convert normalized float32 audio samples to base64-encoded PCM16."""
    pcm16 = array(
        "h",
        (int(max(-1.0, min(1.0, sample)) * 32767) for sample in samples),
    )
    return base64.b64encode(pcm16.tobytes()).decode("utf-8")
