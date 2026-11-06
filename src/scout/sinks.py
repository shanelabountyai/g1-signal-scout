"""DigestSink (C4, D-26): where the digest lands. The pipeline marks items seen only after `write` returns.

LocalSink  — Markdown + JSON (+ the HTML the Doc conversion would use) under out/<week>/. Tested.
DriveSink  — uploads the HTML as a Google Doc (same multipart conversion as G1·B's Write digest node) and the
             Markdown next to it, with a service account. Implemented, not live-tested without credentials.
FailingSink — raises; used by the error-path tests (AC 3) and by `scout --break-sink`.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from scout.config import ENV_DRIVE_FOLDER, ENV_DRIVE_SA, OUT_DIR
from scout.models import Digest
from scout.render import to_html, to_json, to_markdown


class SinkError(RuntimeError):
    """The digest could not be written. Nothing downstream (measurement, seen_items) happens."""


@dataclass
class WriteResult:
    sink: str
    location: str  # path or URL a human can open
    details: dict[str, str]


class DigestSink(Protocol):
    name: str

    def write(self, digest: Digest) -> WriteResult: ...


class LocalSink:
    name = "local"

    def __init__(self, root: Path = OUT_DIR) -> None:
        self.root = Path(root)

    def write(self, digest: Digest) -> WriteResult:
        folder = self.root / digest.week
        try:
            folder.mkdir(parents=True, exist_ok=True)
            stem = f"signal-scout-{digest.week}"
            md = folder / f"{stem}.md"
            js = folder / f"{stem}.json"
            ht = folder / f"{stem}.html"
            md.write_text(to_markdown(digest), encoding="utf-8")
            js.write_text(to_json(digest), encoding="utf-8")
            ht.write_text(to_html(digest), encoding="utf-8")
        except OSError as e:
            raise SinkError(f"local sink could not write under {folder}: {e}") from e
        return WriteResult(sink=self.name, location=str(md), details={"markdown": str(md), "json": str(js), "html": str(ht)})


class FailingSink:
    name = "failing"

    def __init__(self, message: str = "sink broken on purpose") -> None:
        self.message = message

    def write(self, digest: Digest) -> WriteResult:
        raise SinkError(self.message)


class DriveSink:
    """Google Drive via a service account (D-26). The folder must be shared with the service account's email.

    Env: SCOUT_DRIVE_SERVICE_ACCOUNT_JSON (path to the key file), SCOUT_DRIVE_FOLDER_ID.
    Extra `drive`: `uv sync --extra drive` installs google-api-python-client and google-auth.
    """

    name = "drive"
    SCOPES = ("https://www.googleapis.com/auth/drive.file",)

    def __init__(self, key_path: str | None = None, folder_id: str | None = None) -> None:
        self.key_path = key_path or os.environ.get(ENV_DRIVE_SA)
        self.folder_id = folder_id or os.environ.get(ENV_DRIVE_FOLDER)
        if not self.key_path or not self.folder_id:
            raise SinkError(f"Drive sink needs {ENV_DRIVE_SA} and {ENV_DRIVE_FOLDER} in the environment")
        if not Path(self.key_path).expanduser().is_file():
            raise SinkError(f"Drive sink: no key file at {self.key_path}")

    def _service(self):
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError as e:  # pragma: no cover — depends on the optional extra
            raise SinkError("Drive sink needs the `drive` extra: uv sync --extra drive") from e
        creds = service_account.Credentials.from_service_account_file(str(Path(self.key_path).expanduser()), scopes=list(self.SCOPES))
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    def write(self, digest: Digest) -> WriteResult:
        try:
            from googleapiclient.http import MediaInMemoryUpload

            svc = self._service()
            doc = svc.files().create(
                body={"name": digest.title, "mimeType": "application/vnd.google-apps.document", "parents": [self.folder_id]},
                media_body=MediaInMemoryUpload(to_html(digest).encode("utf-8"), mimetype="text/html"),
                fields="id,webViewLink", supportsAllDrives=True,
            ).execute()
            md = svc.files().create(
                body={"name": f"{digest.title}.md", "parents": [self.folder_id]},
                media_body=MediaInMemoryUpload(to_markdown(digest).encode("utf-8"), mimetype="text/markdown"),
                fields="id,webViewLink", supportsAllDrives=True,
            ).execute()
        except SinkError:
            raise
        except Exception as e:  # noqa: BLE001 — any API/auth failure is a failed write, nothing is marked seen
            raise SinkError(f"Drive write failed: {e}") from e
        return WriteResult(sink=self.name, location=doc.get("webViewLink", f"https://docs.google.com/document/d/{doc['id']}/edit"),
                           details={"doc_id": doc["id"], "markdown_id": md["id"], "folder_id": self.folder_id})


def sink_from_name(name: str, out_dir: Path = OUT_DIR) -> DigestSink:
    if name == "local":
        return LocalSink(out_dir)
    if name == "drive":
        return DriveSink()
    if name == "failing":
        return FailingSink()
    raise SinkError(f"unknown sink '{name}' (local, drive, failing)")


def digest_json_path(out_dir: Path, week: str) -> Path:
    return Path(out_dir) / week / f"signal-scout-{week}.json"


def load_digest(path: Path) -> Digest:
    return Digest.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))
