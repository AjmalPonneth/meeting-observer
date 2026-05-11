from __future__ import annotations

import json
from typing import Any

from worker.llm.prompt import (
    FINAL_SUMMARY_INSTRUCTIONS,
    LIVE_SUMMARY_INSTRUCTIONS,
    SESSION_INSTRUCTIONS,
)


def session_config() -> dict[str, Any]:
    return {
        "type": "realtime",
        "instructions": SESSION_INSTRUCTIONS,
        "output_modalities": ["text"],
        "audio": {
            "input": {
                "format": {
                    "type": "audio/pcm",
                    "rate": 24000,
                },
                "transcription": {
                    "model": "gpt-4o-mini-transcribe",
                },
                "turn_detection": {
                    "type": "server_vad",
                    "create_response": False,
                },
            },
        },
    }


def response_config(
    *,
    final: bool = False,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    instructions = FINAL_SUMMARY_INSTRUCTIONS if final else LIVE_SUMMARY_INSTRUCTIONS

    if context:
        instructions = (
            instructions
            + "\n\nAdditional observed meeting metadata:\n"
            + json.dumps(context, ensure_ascii=False)
            + "\n\nUse this metadata only as supporting context. "
            "Do not invent facts. If a participant role is unknown, use null."
        )

    return {
        "conversation": "auto",
        "instructions": instructions,
    }
