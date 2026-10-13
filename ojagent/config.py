from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "anthropic/claude-sonnet-5.5"


@dataclass
class Settings:
    api_key: str
    base_url: str | None
    model: str
    db_path: Path
    out_dir: Path


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    if key := os.getenv("LLM_API_KEY"):
        base_url = os.getenv("LLM_BASE_URL") or None
    elif key := os.getenv("OPENROUTER_API_KEY"):
        base_url = OPENROUTER_BASE_URL
    elif key := os.getenv("OPENAI_API_KEY"):
        base_url = None
    else:
        raise SystemExit("Set LLM_API_KEY, OPENROUTER_API_KEY, or OPENAI_API_KEY in .env")
    return Settings(
        api_key=key,
        base_url=base_url,
        model=os.getenv("LLM_MODEL", DEFAULT_MODEL),
        db_path=ROOT / "data" / "ojagent.sqlite3",
        out_dir=ROOT / "out",
    )
