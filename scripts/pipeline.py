#!/usr/bin/env python3
"""HiDock USB sync + local transcription pipeline."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from hidock.config import load_config
from hidock.filename import build_markdown_filename, parse_hda_filename
from hidock.markdown import TranscriptSegment, write_segments_json, write_transcript_markdown
from hidock.state import FileRecord, load_state, save_state
from hidock.transcribers import get_transcriber


def _limit_label(limit: int | None) -> str:
    return f" (limit {limit}, newest first)" if limit else ""


def run_node_sync(config, include_wip: bool | None = None, limit: int | None = None) -> dict:
    include = config.sync.include_wip if include_wip is None else include_wip
    cmd = [
        "node",
        str(REPO_ROOT / "scripts" / "sync_device.mjs"),
        "sync-new",
        "--cache-dir",
        str(config.audio.cache_dir),
        "--state-file",
        str(config.state_file),
    ]
    if include:
        cmd.append("--include-wip")
    if limit is not None:
        cmd.extend(["--limit", str(limit)])

    # Stream stderr live so download progress is visible; capture stdout for JSON.
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        cwd=REPO_ROOT,
    )
    stdout, _ = proc.communicate()
    if proc.returncode != 0:
        err = (stdout or "").strip()
        raise RuntimeError(f"USB sync failed:\n{err}")
    return json.loads(stdout)


def run_node_list(config, include_wip: bool | None = None) -> dict:
    include = config.sync.include_wip if include_wip is None else include_wip
    cmd = [
        "node",
        str(REPO_ROOT / "scripts" / "sync_device.mjs"),
        "list",
    ]
    if include:
        cmd.append("--include-wip")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return json.loads(result.stdout)


def run_node_delete(config, name: str) -> None:
    cmd = [
        "node",
        str(REPO_ROOT / "scripts" / "sync_device.mjs"),
        "delete",
        "--name",
        name,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")


def _parse_recorded_at(iso_time: str | None, device_file: str, signature: str) -> datetime | None:
    if iso_time:
        return datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
    try:
        return parse_hda_filename(device_file, signature).recorded_at
    except ValueError:
        return None


def _device_clean_candidates(
    config,
    *,
    synced_only: bool,
    transcribed_only: bool,
    older_than_days: int | None,
) -> list[dict]:
    listing = run_node_list(config)
    state = load_state(config.state_file)
    now = datetime.now(timezone.utc)
    candidates: list[dict] = []

    for file in listing.get("files", []):
        name = file.get("name")
        signature = file.get("signature")
        if not name or not signature:
            continue

        rec = state.get(signature)
        if synced_only:
            if not rec or not rec.audio_path:
                continue
            if not Path(rec.audio_path).exists():
                continue
            if transcribed_only and not rec.markdown_path:
                continue

        if older_than_days is not None:
            recorded_at = _parse_recorded_at(file.get("time"), name, signature)
            if recorded_at is None:
                continue
            if recorded_at.tzinfo is None:
                recorded_at = recorded_at.replace(tzinfo=timezone.utc)
            age_days = (now - recorded_at.astimezone(timezone.utc)).days
            if age_days < older_than_days:
                continue

        candidates.append(file)

    candidates.sort(key=lambda f: f.get("time") or "")
    return candidates


def transcribe_pending(
    config,
    limit: int | None = None,
    force: bool = False,
    reuse_whisper: bool = False,
) -> int:
    state = load_state(config.state_file)
    pending = [
        rec
        for rec in state.files.values()
        if rec.audio_path and (force or not rec.markdown_path)
    ]
    pending.sort(key=lambda r: r.recorded_at or "", reverse=True)
    if limit is not None:
        pending = pending[:limit]

    if not pending:
        print("No recordings waiting for transcription.", file=sys.stderr, flush=True)
        return 0

    transcriber = get_transcriber(config)
    total = len(pending)
    print(
        f"Transcribing {total} file(s) via {transcriber.name!r}...",
        file=sys.stderr,
        flush=True,
    )

    reuse_cache = reuse_whisper and transcriber.supports_cache_reuse()
    if reuse_whisper and not transcriber.supports_cache_reuse():
        print(
            f"  (--reuse-whisper ignored for provider {transcriber.name!r})",
            file=sys.stderr,
            flush=True,
        )

    audio_paths = [
        Path(rec.audio_path)
        for rec in pending
        if rec.audio_path and Path(rec.audio_path).exists()
    ]

    completed = 0
    try:
        transcriber.prepare(audio_paths, reuse_cache=reuse_cache)

        for idx, rec in enumerate(pending, start=1):
            audio_path = Path(rec.audio_path)
            if not audio_path.exists():
                print(f"[{idx}/{total}] Skipping missing audio: {audio_path}", file=sys.stderr, flush=True)
                continue

            fallback_time = None
            if rec.recorded_at:
                fallback_time = datetime.fromisoformat(rec.recorded_at.replace("Z", "+00:00"))

            parsed = parse_hda_filename(
                rec.device_file,
                rec.signature,
                fallback_time=fallback_time,
            )
            title = config.markdown.title_template.format(
                rec_id=parsed.rec_id,
                date=parsed.date_str,
                device_file=parsed.device_file,
            )
            md_name = build_markdown_filename(config.output.filename_pattern, parsed, title)
            md_path = config.transcript_dir / md_name
            segments_json_path = md_path.with_suffix(".segments.json")

            size_mb = audio_path.stat().st_size / 1024 / 1024
            print(
                f"[{idx}/{total}] {rec.device_file} ({size_mb:.1f} MB) -> {md_path.name}",
                file=sys.stderr,
                flush=True,
            )
            result = transcriber.transcribe(audio_path, reuse_cache=reuse_cache)
            segments = result.segments
            duration = result.duration_seconds

            if config.markdown.save_segments_json:
                write_segments_json(segments_json_path, segments, parsed)

            write_transcript_markdown(
                md_path,
                title=title,
                parsed=parsed,
                segments=segments,
                source=config.markdown.source,
                tags=config.markdown.tags,
                duration_seconds=duration,
                segments_json_path=segments_json_path if config.markdown.save_segments_json else None,
            )

            rec.transcribed_at = datetime.now(timezone.utc).isoformat()
            rec.markdown_path = str(md_path)
            if config.markdown.save_segments_json:
                rec.segments_path = str(segments_json_path)
            state.upsert(rec)
            save_state(config.state_file, state)
            completed += 1
            print(f"[{idx}/{total}] Done — wrote {md_path}", file=sys.stderr, flush=True)

            if config.sync.delete_after_transcribe and rec.device_file:
                print(
                    f"[{idx}/{total}] Deleting {rec.device_file} from device...",
                    file=sys.stderr,
                    flush=True,
                )
                run_node_delete(config, rec.device_file)
                print(
                    f"[{idx}/{total}] Deleted {rec.device_file} from device",
                    file=sys.stderr,
                    flush=True,
                )
    finally:
        transcriber.close()

    print(f"Transcribed {completed} recording(s).", file=sys.stderr, flush=True)
    return completed


def cmd_list(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config) if args.config else None)
    data = run_node_list(config, include_wip=args.include_wip)
    print(json.dumps(data, indent=2))


def cmd_sync(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config) if args.config else None)
    print(f"Phase 1: Downloading new recordings{_limit_label(args.limit)}...", file=sys.stderr, flush=True)
    data = run_node_sync(config, include_wip=args.include_wip, limit=args.limit)
    count = data.get("downloaded_count", 0)
    print(f"Phase 1 complete — {count} file(s) downloaded.", file=sys.stderr, flush=True)
    print(json.dumps(data, indent=2))


def cmd_transcribe(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config) if args.config else None)
    print(f"Phase 2: Transcribing{_limit_label(args.limit)}...", file=sys.stderr, flush=True)
    transcribe_pending(
        config,
        limit=args.limit,
        force=args.force,
        reuse_whisper=args.reuse_whisper,
    )


def cmd_run(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config) if args.config else None)
    print(f"Phase 1/2: Downloading new recordings{_limit_label(args.limit)}...", file=sys.stderr, flush=True)
    data = run_node_sync(config, include_wip=args.include_wip, limit=args.limit)
    count = data.get("downloaded_count", 0)
    print(f"Phase 1 complete — {count} file(s) downloaded.", file=sys.stderr, flush=True)
    if count == 0:
        print(
            "  (nothing new to download — continuing with cached audio)",
            file=sys.stderr,
            flush=True,
        )
    print(f"Phase 2/2: Transcribing{_limit_label(args.limit)}...", file=sys.stderr, flush=True)
    transcribe_pending(
        config,
        limit=args.limit,
        force=args.force,
        reuse_whisper=args.reuse_whisper,
    )


def cmd_device_rm(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config) if args.config else None)
    run_node_delete(config, args.name)
    print(f"Deleted {args.name} from device")


def cmd_device_clean(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config) if args.config else None)
    candidates = _device_clean_candidates(
        config,
        synced_only=not args.all_on_device,
        transcribed_only=args.transcribed_only,
        older_than_days=args.older_than,
    )

    if not candidates:
        print("No device files matched the cleanup criteria.")
        return

    print(f"Matched {len(candidates)} file(s) on device:")
    for file in candidates:
        when = (file.get("time") or "?")[:10]
        size_mb = round((file.get("length") or 0) / 1024 / 1024, 1)
        print(f"  {when}  {size_mb:>6} MB  {file['name']}")

    if args.dry_run:
        print("Dry run — nothing deleted.")
        return

    if not args.yes:
        print("Re-run with --yes to delete these files from the device.")
        return

    for file in candidates:
        run_node_delete(config, file["name"])
    print(f"Deleted {len(candidates)} file(s) from device.")


def cmd_download_one(args: argparse.Namespace) -> None:
    config = load_config(Path(args.config) if args.config else None)
    out = config.audio.cache_dir / args.name.replace(".hda", ".mp3")
    cmd = [
        "node",
        str(REPO_ROOT / "scripts" / "sync_device.mjs"),
        "download",
        "--name",
        args.name,
        "--out",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    payload = json.loads(result.stdout)

    listing = run_node_list(config)
    match = next((f for f in listing.get("files", []) if f.get("name") == args.name), None)
    if match:
        state = load_state(config.state_file)
        state.upsert(
            FileRecord(
                signature=match["signature"],
                device_file=args.name,
                recorded_at=match.get("time"),
                downloaded_at=datetime.now(timezone.utc).isoformat(),
                audio_path=str(out),
            ),
        )
        save_state(config.state_file, state)

    print(json.dumps(payload, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HiDock sync + transcribe pipeline")
    parser.add_argument("--config", help="Path to config.yaml (default: ./config.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)

    list_p = sub.add_parser("list", help="List recordings on device (JSON)")
    list_p.add_argument("--include-wip", action="store_true")
    list_p.set_defaults(func=cmd_list)

    sync_p = sub.add_parser("sync", help="Phase 1: download all new recordings from device")
    sync_p.add_argument("--include-wip", action="store_true")
    sync_p.add_argument("--limit", type=int, default=None, help="Download at most N newest files (testing)")
    sync_p.set_defaults(func=cmd_sync)

    dl_p = sub.add_parser("download", help="Download one file by name")
    dl_p.add_argument("name", help="Device filename, e.g. 2026May21-154615-Rec58.hda")
    dl_p.set_defaults(func=cmd_download_one)

    tr_p = sub.add_parser("transcribe", help="Phase 2: transcribe all downloaded audio")
    tr_p.add_argument("--limit", type=int, default=None, help="Cap transcription batch size")
    tr_p.add_argument("--force", action="store_true")
    tr_p.add_argument(
        "--reuse-whisper",
        action="store_true",
        help="Skip Whisper when .whisper.json cache exists beside the audio file",
    )
    tr_p.set_defaults(func=cmd_transcribe)

    run_p = sub.add_parser("run", help="Phase 1 then 2: download all, then transcribe all")
    run_p.add_argument("--include-wip", action="store_true")
    run_p.add_argument("--limit", type=int, default=None, help="Max files per phase (testing)")
    run_p.add_argument("--force", action="store_true")
    run_p.add_argument(
        "--reuse-whisper",
        action="store_true",
        help="Skip Whisper when .whisper.json cache exists beside the audio file",
    )
    run_p.set_defaults(func=cmd_run)

    rm_p = sub.add_parser("device-rm", help="Delete one recording from the device")
    rm_p.add_argument("name", help="Device filename, e.g. 2026May21-154615-Rec58.hda")
    rm_p.set_defaults(func=cmd_device_rm)

    clean_p = sub.add_parser("device-clean", help="Delete recordings from device (with safety filters)")
    clean_p.add_argument(
        "--older-than",
        type=int,
        metavar="DAYS",
        help="Only files recorded at least N days ago",
    )
    clean_p.add_argument(
        "--transcribed-only",
        action="store_true",
        help="Require local transcript before deleting (safer)",
    )
    clean_p.add_argument(
        "--all-on-device",
        action="store_true",
        help="Ignore local sync state (dangerous — may delete files not yet downloaded)",
    )
    clean_p.add_argument("--dry-run", action="store_true", help="List matches without deleting")
    clean_p.add_argument("--yes", action="store_true", help="Confirm deletion")
    clean_p.set_defaults(func=cmd_device_clean)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
