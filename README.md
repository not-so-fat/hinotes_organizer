# hinotes_organizer

Sync HiDock P1 recordings to your Mac, transcribe with speaker labels via **AssemblyAI** (default), and save Obsidian-ready markdown — no HiNotes cloud required.

## 5-minute setup

**You need:** HiDock P1 (USB), macOS, [Node.js 22+](https://nodejs.org/), Python 3.10+, [AssemblyAI API key](https://www.assemblyai.com/dashboard) (free tier works for testing).

```bash
# macOS USB access
brew install libusb

# clone the repo, then from repo root:
chmod +x scripts/setup.sh
./scripts/setup.sh
```

Edit **`config.yaml`** — only two required fields:

```yaml
output:
  dir: ./output/transcripts          # or your Obsidian vault folder

secrets:
  assemblyai_api_key: "your-key-here"
```

**First run** (close HiNotes / Chrome first — they lock the USB device):

```bash
source .venv/bin/activate
python scripts/pipeline.py run --limit 1
```

That downloads one recording, transcribes it, writes markdown, and removes it from the device. Re-run without `--limit` to process everything pending.

### Setup checklist

| Step | Command / action |
|---|---|
| 1. One-time install | `./scripts/setup.sh` |
| 2. Config | `output.dir` + `secrets.assemblyai_api_key` in `config.yaml` |
| 3. Close HiNotes | Quit Chrome tab or app using the HiDock |
| 4. Test | `python scripts/pipeline.py run --limit 1` |
| 5. Point at Obsidian | Change `output.dir` to your vault when ready |

All settings live in **`config.yaml`** (gitignored). No `.env` file.

### Manual setup (instead of `setup.sh`)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd device_usb && npm install && npm run build && cd ..

cp config.example.yaml config.yaml
# edit config.yaml, then:
python scripts/pipeline.py run --limit 1
```

**Local transcription** (Whisper + pyannote on your GPU) needs extra packages — see [Local transcription](#local-transcription-whisper--pyannote) below.

## What you get

Each recording becomes a markdown file:

```
output/transcripts/2026-01-15_Recording_Rec12_a1b2c3d4.md
```

```yaml
---
title: Recording Rec12
date: 2026/01/15
recorded_at: 2026-01-15T10:30:00
duration_seconds: 3600.0
source: HiDock
tags: [transcript, hidock, meeting]
segments_file: 2026-01-15_Recording_Rec12_a1b2c3d4.segments.json
---

# Raw Transcript

Speaker 1: Hello everyone.
Speaker 2: Thanks for joining.
```

Per-utterance timestamps live in the companion `.segments.json` file.

## How it works

```
Phase 1  sync        →  download new .hda files to .cache/audio/
Phase 2  transcribe  →  AssemblyAI → markdown in output.dir
```

```bash
python scripts/pipeline.py sync         # download only
python scripts/pipeline.py transcribe   # transcribe cached audio only
python scripts/pipeline.py run          # both phases
python scripts/pipeline.py list         # what's on the device (JSON)
```

Use `--limit N` to cap batch size (newest first). Good for testing:

```bash
python scripts/pipeline.py run --limit 1
```

After a successful transcript, the recording is **removed from the HiDock** by default so a second laptop won't re-download it. Set `sync.delete_after_transcribe: false` in `config.yaml` to keep files on the device.

## Configuration

| Setting | Default | Notes |
|---|---|---|
| `output.dir` | `./output/transcripts` | Where markdown is written |
| `transcription.provider` | `assemblyai` | Omit to use AssemblyAI |
| `secrets.assemblyai_api_key` | *(required)* | [Get a key](https://www.assemblyai.com/dashboard) |
| `sync.delete_after_transcribe` | `true` | Clears device after success |
| `markdown.save_segments_json` | `true` | Timestamp sidecar JSON |

Everything else has sensible defaults. See `config.example.yaml` for local, remote, and HiNotes options.

### Multi-laptop

Use the same Obsidian vault on both machines (iCloud, Syncthing, etc.). Default AssemblyAI + `delete_after_transcribe` is the intended workflow. Check employer policy before sending confidential meetings to a cloud API.

## Local transcription (Whisper + pyannote)

For a GPU machine or overnight batch on a home PC — **not recommended on a MacBook CPU** for long recordings.

```bash
pip install -r requirements-local.txt
```

```yaml
transcription:
  provider: local

secrets:
  hf_token: "hf_..."   # accept pyannote/speaker-diarization-community-1 on Hugging Face
```

Retry diarization without re-running Whisper:

```bash
python scripts/pipeline.py transcribe --limit 1 --reuse-whisper
```

### Self-hosted GPU worker

On the GPU machine:

```bash
pip install -r requirements-local.txt
python scripts/transcribe_worker.py --host 0.0.0.0 --port 8765
```

On your laptop (`requirements.txt` only):

```yaml
transcription:
  provider: remote
  remote_url: http://192.168.1.50:8765
  remote_token: "shared-secret"   # optional
```

Use Tailscale or a VPN — don't expose the worker on the public internet.

## Automation

Safe to re-run — `.state/pipeline.json` skips finished files.

```bash
./scripts/run_pipeline.sh
```

For macOS LaunchAgent setup, see [Automation details](#automation-details) below.

## Device storage

Manual cleanup of old synced files (automatic delete-after-transcribe handles the common case):

```bash
python scripts/pipeline.py device-clean --dry-run
python scripts/pipeline.py device-clean --older-than 30 --yes
python scripts/pipeline.py device-rm 2026Jan15-103000-Rec12.hda
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `LIBUSB_ERROR_ACCESS` | Close HiNotes / Chrome, replug device |
| `device_usb not built` | Run `./scripts/setup.sh` or `cd device_usb && npm install && npm run build` |
| `Missing config.yaml` | `cp config.example.yaml config.yaml` |
| `UnicodeDecodeError` in config | Re-save `config.yaml` as UTF-8; use plain `-` in comments |
| `assemblyai_api_key is not set` | Add key under `secrets:` in `config.yaml` |
| AssemblyAI 400 / `speech_models` | Update to latest code — API requires `universal-2` model |
| Wrong `duration_seconds` | Fixed in latest code — re-transcribe or edit front matter |
| Diarization / HF 403 | Local mode only — set `hf_token`, accept [community-1 model](https://huggingface.co/pyannote/speaker-diarization-community-1) |
| Duplicate work on re-run | Expected — state file skips completed files |
| Generic titles (`Recording Rec12`) | Rename in Obsidian; device filenames lack meeting names |

## HiNotes cloud sync (optional)

If you already have transcripts in HiNotes cloud:

```yaml
secrets:
  hinotes_token: "..."   # Chrome → hinotes.hidock.com → localStorage.getItem('accessToken')
```

```bash
python scripts/sync_transcripts.py verify
python scripts/sync_transcripts.py sync
```

## Automation details

**Requirements:** HiDock plugged in, HiNotes closed, setup done.

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

## Documentation

| Doc | Audience |
|---|---|
| [docs/PRD.md](docs/PRD.md) | Product requirements, scope, phases |
| [docs/ERD.md](docs/ERD.md) | Data model and file relationships |
| [docs/research-and-approach.md](docs/research-and-approach.md) | Technical research and design rationale |
