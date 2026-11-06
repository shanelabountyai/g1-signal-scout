"""Paths, environment names and the feed list (C1).

Everything configurable is read here and nowhere else. Values never live in
the repo; `.env.example` lists the names.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

# The repo root when running from a checkout (the normal case: cron/launchd on the owner's Mac
# runs `uv run --directory <repo> scout`). Fixtures, config/feeds.md and docs live there.
REPO_ROOT = Path(__file__).resolve().parents[2]
FEEDS_MD = REPO_ROOT / "config" / "feeds.md"
FIXTURES_JSON = REPO_ROOT / "fixtures" / "feed-items.json"
RECORDED_JSON = REPO_ROOT / "fixtures" / "recorded-responses.json"
OUT_DIR = REPO_ROOT / "out"

FRESH_DAYS = 7  # same window as G1·B's Normalize node
ENV_DB_PATH = "SCOUT_DB_PATH"  # seen_items SQLite (D-27)
ENV_DRIVE_SA = "SCOUT_DRIVE_SERVICE_ACCOUNT_JSON"  # path to a service-account key file (D-26)
ENV_DRIVE_FOLDER = "SCOUT_DRIVE_FOLDER_ID"
ENV_API_KEY = "ANTHROPIC_API_KEY"
ENV_G0_DB = "G0_DB_PATH"  # read by the shared layer itself


def default_db_path() -> Path:
    return Path.home() / ".g1-signal-scout" / "scout.sqlite"


def db_path() -> str:
    return os.environ.get(ENV_DB_PATH) or str(default_db_path())


def api_key_present() -> bool:
    return bool(os.environ.get(ENV_API_KEY))


@dataclass(frozen=True)
class Feed:
    source: str
    url: str


_FEED_ROW = re.compile(r"^\| ([^|]+?) \| (https?://[^\s|]+) \|", re.M)


def feeds(path: Path = FEEDS_MD) -> list[Feed]:
    """The feed table rows of config/feeds.md, same regex as n8n/build.py."""
    rows = _FEED_ROW.findall(path.read_text(encoding="utf-8"))
    return [Feed(source=s.strip(), url=u) for s, u in rows if s.strip() != "Source"]
