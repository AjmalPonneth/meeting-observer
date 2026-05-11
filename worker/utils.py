from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=32)
def load_script(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")
