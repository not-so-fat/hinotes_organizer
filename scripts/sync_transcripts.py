#!/usr/bin/env python3
"""Sync HiNotes meeting transcripts to local files."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hidock.config import load_config
from hinotes.client import HiNotesClient, HiNotesError, format_transcription_payload


def slugify(value: str, *, max_len: int = 80) -> str:
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE).strip().lower()
    value = re.sub(r"[\s_-]+", "-", value)
    return (value or "untitled")[:max_len].strip("-") or "untitled"


def load_state(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("synced_note_ids", []))
    except json.JSONDecodeError:
        return set()


def save_state(path: Path, synced_ids: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "synced_note_ids": sorted(synced_ids),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def resolve_token(explicit: str | None, config_path: Path | None) -> str:
    if explicit:
        return explicit.strip()
    token = load_config(config_path).hinotes_token()
    if not token:
        print(
            "Missing HiNotes token.\n"
            "1. In Chrome on https://hinotes.hidock.com/home, open DevTools → Console\n"
            "2. Run: localStorage.getItem('accessToken')\n"
            "3. Add to config.yaml under secrets.hinotes_token\n",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


def fetch_transcript_text(client: HiNotesClient, note_id: str) -> str:
    try:
        return client.export_transcript_txt(note_id).strip()
    except (HiNotesError, requests.HTTPError):
        pass

    payload = client.get_transcription(note_id)
    return format_transcription_payload(payload)


def cmd_verify(client: HiNotesClient) -> int:
    user = client.verify_token()
    email = user.get("email") or user.get("userEmail") or user.get("name") or "unknown"
    print(f"Token OK — signed in as {email}")
    return 0


def cmd_list(client: HiNotesClient, args: argparse.Namespace) -> int:
    notes, _ = client.list_recording_notes(page_index=0, page_size=args.limit)
    if not notes:
        print("No notes found.")
        return 0

    for note in notes:
        created = note.create_time or "?"
        state = note.state or "?"
        print(f"{note.id}\t{state}\t{created}\t{note.title}")
    return 0


def cmd_export(client: HiNotesClient, args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    note_id = args.note_id
    info = client.get_note_info(note_id)
    title = str(info.get("title") or info.get("name") or note_id)
    created = info.get("createTime") or info.get("createtime") or info.get("create_time")
    date_prefix = ""
    if created:
        date_prefix = str(created)[:10].replace("/", "-")
    filename = f"{date_prefix}_{slugify(title)}_{note_id[:8]}.txt" if date_prefix else f"{slugify(title)}_{note_id[:8]}.txt"
    out_path = output_dir / filename

    text = fetch_transcript_text(client, note_id)
    if not text:
        print(f"No transcript available for note {note_id} (state={info.get('state')}).", file=sys.stderr)
        print("HiNotes v3 may require running Generate Now in the UI first.", file=sys.stderr)
        return 1

    out_path.write_text(text + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


def cmd_sync(client: HiNotesClient, args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = Path(args.state_file)
    synced = load_state(state_path)

    notes = client.iter_all_recording_notes(page_size=args.page_size)
    candidates = [n for n in notes if n.id and n.id not in synced]
    if args.limit:
        candidates = candidates[: args.limit]

    if not candidates:
        print("No new notes to sync.")
        return 0

    saved = 0
    skipped = 0
    for note in candidates:
        try:
            text = fetch_transcript_text(client, note.id)
        except HiNotesError as exc:
            print(f"Skip {note.id} ({note.title}): {exc}", file=sys.stderr)
            skipped += 1
            continue

        if not text:
            print(f"Skip {note.id} ({note.title}): no transcript yet (state={note.state})", file=sys.stderr)
            skipped += 1
            continue

        created = note.create_time or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        date_prefix = str(created)[:10].replace("/", "-")
        filename = f"{date_prefix}_{slugify(note.title)}_{note.id[:8]}.txt"
        out_path = output_dir / filename
        out_path.write_text(text + "\n", encoding="utf-8")
        synced.add(note.id)
        saved += 1
        print(f"Saved {out_path}")

        if args.delay:
            time.sleep(args.delay)

    save_state(state_path, synced)
    print(f"Done. Saved {saved}, skipped {skipped}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync HiNotes transcripts locally")
    parser.add_argument("--config", help="Path to config.yaml (default: ./config.yaml)")
    parser.add_argument("--token", help="HiNotes accessToken override")
    parser.add_argument("--output-dir", help="Output directory override (default: output.dir from config)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("verify", help="Check that the access token works")

    list_parser = sub.add_parser("list", help="List recent recording notes")
    list_parser.add_argument("--limit", type=int, default=20)

    export_parser = sub.add_parser("export", help="Export one note transcript")
    export_parser.add_argument("note_id")

    sync_parser = sub.add_parser("sync", help="Export all new notes not yet synced")
    sync_parser.add_argument("--page-size", type=int, default=50)
    sync_parser.add_argument("--limit", type=int, default=0, help="Max notes to process this run")
    sync_parser.add_argument("--delay", type=float, default=0.5, help="Delay between notes (seconds)")
    sync_parser.add_argument(
        "--state-file",
        default=str(ROOT / ".sync_state.json"),
        help="Track already-synced note IDs",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config_path = Path(args.config) if args.config else None

    try:
        config = load_config(config_path)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    if args.output_dir:
        args.output_dir = args.output_dir
    else:
        args.output_dir = str(config.output.dir)

    token = resolve_token(args.token, config_path)
    client = HiNotesClient(token)

    try:
        if args.command == "verify":
            return cmd_verify(client)
        if args.command == "list":
            return cmd_list(client, args)
        if args.command == "export":
            return cmd_export(client, args)
        if args.command == "sync":
            return cmd_sync(client, args)
    except HiNotesError as exc:
        print(f"HiNotes API error: {exc}", file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
