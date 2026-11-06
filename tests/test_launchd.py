"""C6: the plist is valid, fires at the D-11 time, does not run at load, and carries no secret."""

from __future__ import annotations

import plistlib
from pathlib import Path

PLIST = Path(__file__).resolve().parents[1] / "launchd" / "com.labintelligence.g1-signal-scout.plist"


def test_plist_is_valid_and_matches_d11():
    d = plistlib.load(PLIST.open("rb"))
    assert d["Label"] == "com.labintelligence.g1-signal-scout"
    assert d["StartCalendarInterval"] == {"Weekday": 1, "Hour": 6, "Minute": 0}  # Monday 06:00 local (America/Chicago on the owner's Mac)
    assert d["RunAtLoad"] is False
    args = d["ProgramArguments"]
    assert args[0].endswith("/uv") and "scout" in args and "--live" in args
    text = PLIST.read_text()
    assert "ANTHROPIC_API_KEY" not in d.get("EnvironmentVariables", {})  # secrets come from .env, never the plist
    assert "sk-ant" not in text
