# hinotes_organizer

Sync HiDock P1 recordings to your Mac, transcribe them locally with speaker labels, and save Obsidian-ready markdown — no HiNotes cloud required.

## Quick start

```bash
cp config.example.yaml config.yaml
# Edit config.yaml: output.dir and secrets.hf_token

python3 -m venv .venv && source .venv/bin/activate pip install -r requirements.txt

cd device_usb && npm install && npm run build && cd ..

python scripts/pipeline.py run
```

**Before syncing:** close HiNotes / Chrome — they hold an exclusive USB lock on the device.

All settings and secrets live in **`config.yaml`** (gitignored). No `.env` file.

## What you get

Each recording becomes a markdown file in your vault:

```
Transcripts/HiDock/2026-01-15_Recording_Rec12_a1b2c3d4.md
```

```yaml
---
title: Recording Rec12
date: 2026/01/15
recorded_at: 2026-01-15T10:30:00
source: HiDock
tags: [transcript, hidock, meeting]
segments_file: 2026-01-15_Recording_Rec12_a1b2c3d4.segments.json
---

# Raw Transcript

Speaker 1: Hello everyone.
Speaker 2: Thanks for joining.
```

Timestamps (start/end per utterance) are in a companion `.segments.json` file, linked from the markdown front matter.

## Prerequisites

| Requirement | Notes |
|---|---|
| HiDock P1 | Connected via USB |
| Node.js 22+ | For USB sync (`device_usb/`) |
| libusb | macOS: `brew install libusb` |
| Python 3.10+ | Transcription pipeline |
| Hugging Face token | Required for speaker labels — see [Speaker labels (Hugging Face)](#speaker-labels-hugging-face) below |

## How it works

Two separate phases — **all downloads finish before any transcription starts**:

```
Phase 1  sync     →  download every new .hda to .cache/audio/
Phase 2  transcribe  →  process cached audio → markdown in output.dir
```

`run` = phase 1, then phase 2. You can also run them separately:

```bash
python scripts/pipeline.py sync         # download everything new first
python scripts/pipeline.py transcribe   # then transcribe everything downloaded
```

`--limit N` caps how many files are processed (newest first). Handy for testing:

```bash
python scripts/pipeline.py run --limit 1    # one recording end-to-end
python scripts/pipeline.py sync --limit 3   # download 3 newest only
python scripts/pipeline.py transcribe --limit 3
```

Without `--limit`, phase 1 downloads **all** pending files before phase 2 starts.

## Commands

```bash
python scripts/pipeline.py list        # list recordings on device
python scripts/pipeline.py sync        # download new files
python scripts/pipeline.py transcribe  # transcribe cached audio
python scripts/pipeline.py run         # phase 1 + 2

# Device storage management
python scripts/pipeline.py device-clean --dry-run              # preview safe cleanup
python scripts/pipeline.py device-clean --older-than 30 --yes  # delete synced files 30+ days old
python scripts/pipeline.py device-rm 2026Jan15-103000-Rec12.hda

# Test with one recent recording
python scripts/pipeline.py run --limit 1

# Retry diarization only (after a failed run that cached Whisper output)
python scripts/pipeline.py transcribe --limit 1 --reuse-whisper
```

## Configuration

Copy `config.example.yaml` → `config.yaml`. Two fields to fill in for local transcription:

```yaml
output:
  dir: /path/to/your/Obsidian/Transcripts/HiDock

secrets:
  hf_token: "hf_..."   # required for speaker labels — accept pyannote/speaker-diarization-community-1
```

| Setting | Default | Notes |
|---|---|---|
| `output.dir` | `./output/transcripts` | Where markdown files are written |
| `transcription.provider` | `local` | `local` \| `assemblyai` \| `remote` \| `custom` |
| `secrets.hf_token` | *(local / worker)* | Required for local speaker labels |
| `secrets.assemblyai_api_key` | *(cloud)* | Required when `provider: assemblyai` |
| `transcription.model` | `medium` | Local / worker only — use `large-v3` for better quality |
| `transcription.diarize` | `true` | Local only (pyannote speaker labels) |
| `sync.delete_after_transcribe` | `true` for cloud/remote | Delete from device after successful transcript |
| `markdown.save_segments_json` | `true` | Timestamp sidecar; set `false` only if you don't need timings |

Other options are documented as comments in `config.example.yaml`.

### Processing profiles

| Profile | Config | Best for |
|---|---|---|
| **A — Local** | `provider: local` | GPU machine or small tests on CPU |
| **B — Cloud** | `provider: assemblyai` | Multi-laptop, fast turnaround, no local GPU |
| **C1 — GPU box** | Plug HiDock into home PC, `provider: local` | One machine owns sync + transcribe |
| **C2 — Remote worker** | `provider: remote` + worker on GPU host | Sync on laptop, transcribe on home PC |

**Profile B (AssemblyAI):**

```yaml
transcription:
  provider: assemblyai
  language: en   # optional; omit for auto-detect

secrets:
  assemblyai_api_key: "..."
```

**Profile C2 (self-hosted worker):** On your GPU machine:

```bash
python scripts/transcribe_worker.py --host 0.0.0.0 --port 8765
```

On your laptop:

```yaml
transcription:
  provider: remote
  remote_url: http://192.168.1.50:8765   # or Tailscale hostname
  remote_token: "shared-secret"          # optional
```

Use Tailscale or a VPN so the worker is not exposed on the public internet. The worker accepts one job at a time; clients retry automatically on HTTP 503.

### Multi-laptop workflow

When you use the same HiDock on a personal and work laptop:

1. Point both machines at the same Obsidian vault (iCloud, Syncthing, etc.).
2. Use **Profile B** or **C2** — local CPU transcription is too slow for daily use.
3. Enable `sync.delete_after_transcribe: true` (default for `assemblyai` and `remote`) so the second laptop does not re-download finished recordings.

After a successful transcript, the pipeline removes the file from the device. Local audio in `.cache/audio/` and markdown in `output.dir` remain on that machine; the synced vault is the shared source of truth for transcripts.

**Privacy:** Check employer policy before sending work meetings to AssemblyAI (Profile B). Profile C2 keeps audio on your own network.

### Speaker labels (Hugging Face)

Speaker diarization (`transcription.diarize: true`, the default) uses **[pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)** on Hugging Face. Accept the model terms on that page (log in first, then **Agree and access repository**), create a token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) (read access is enough), and set it in `config.yaml`:

```yaml
secrets:
  hf_token: "hf_..."
```

If you only want plain transcription without `Speaker 1` / `Speaker 2` labels, set `transcription.diarize: false` — then no Hugging Face token or model access is required.

## Automation

The pipeline is safe to re-run — state in `.state/pipeline.json` skips files already synced or transcribed.

**Requirements for unattended runs:**

- Close HiNotes / Chrome first (USB exclusive lock)
- One-time setup done (venv, `device_usb` built, `config.yaml` with tokens)
- Device stays plugged in until sync finishes

### Option 1: Run after plugging in

```bash
./scripts/run_pipeline.sh
```

### Option 2: macOS LaunchAgent

Runs every minute; skips if no HiDock connected. Reads secrets from `config.yaml` — no extra env vars needed.

1. `chmod +x scripts/run_pipeline.sh`
2. Create `~/Library/LaunchAgents/com.hidock.pipeline.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.hidock.pipeline</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/hinotes_organizer/scripts/run_pipeline.sh</string>
  </array>
  <key>StartInterval</key>
  <integer>60</integer>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/hidock-pipeline.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/hidock-pipeline.log</string>
</dict>
</plist>
```

3. `launchctl load ~/Library/LaunchAgents/com.hidock.pipeline.plist`

Logs: `/tmp/hidock-pipeline.log`

## Device storage

Free space on the P1 by deleting recordings **already copied to your laptop**.

Default `device-clean` only targets files that are **downloaded locally** (audio exists in `.cache/audio/`). Use `--dry-run` first:

```bash
python scripts/pipeline.py device-clean --dry-run
python scripts/pipeline.py device-clean --yes
```

| Flag | Effect |
|---|---|
| `--older-than 30` | Only recordings at least 30 days old |
| `--transcribed-only` | Also require a local transcript before deleting |
| `--dry-run` | Show matches, delete nothing |
| `--yes` | Actually delete (required) |
| `--all-on-device` | Skip local safety checks (**dangerous**) |

Delete one file by name:

```bash
python scripts/pipeline.py device-rm 2026Jan15-103000-Rec12.hda
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `LIBUSB_ERROR_ACCESS` | Close HiNotes tab or quit Chrome, replug device |
| `device_usb not built` | Run `cd device_usb && npm install && npm run build` |
| Diarization error / HF 403 | Set `secrets.hf_token` and accept [speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1) |
| `Invalid data found when processing input` (torchcodec) | Fixed in current code — re-run `transcribe`; audio is decoded via Whisper's loader, not torchcodec |
| `AVFFrameReceiver` duplicate class warning | Harmless on macOS when Homebrew `ffmpeg` is installed alongside PyAV; ignore unless you see crashes |
| Duplicate work on re-run | Normal — state in `.state/pipeline.json` skips finished files |
| No meeting title | Device filenames are generic (`Recording Rec12`); rename in Obsidian |

## HiNotes cloud sync (optional)

If you already have transcripts in HiNotes cloud, add your token to the same `config.yaml`:

```yaml
secrets:
  hinotes_token: "..."   # Chrome → localStorage.getItem('accessToken')
```

Then:

```bash
python scripts/sync_transcripts.py verify
python scripts/sync_transcripts.py sync
```

Uses the same `output.dir` as the USB pipeline.

## Documentation

| Doc | Audience |
|---|---|
| [docs/PRD.md](docs/PRD.md) | Product requirements, scope, phases |
| [docs/ERD.md](docs/ERD.md) | Data model and file relationships |
| [docs/research-and-approach.md](docs/research-and-approach.md) | Technical research and design rationale |
