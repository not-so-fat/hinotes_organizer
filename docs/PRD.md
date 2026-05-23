# Product Requirements Document (PRD)

**Product:** hinotes_organizer — HiDock local transcript pipeline  
**Last updated:** 2026-05-23  
**Status:** MVP in progress

Related docs: [ERD](ERD.md) · [Research & approach](research-and-approach.md)

---

## 1. Overview

A personal tool that automates the path from **HiDock P1 recordings** to **Obsidian-ready markdown transcripts** — without HiNotes cloud, without AI summaries, and without manual copy-paste.

```
HiDock P1 (USB) → sync audio → local transcription → markdown in vault
```

The output format mirrors existing **Fireflies** transcript files in the user's Obsidian vault (YAML front matter + `# Raw Transcript` body with speaker labels).

---

## 2. Problem

| Today (HiNotes manual) | Pain |
|---|---|
| Transfer files in browser | Requires HiNotes tab + USB |
| Click **Generate Now** | Often mandatory in v3 before transcript exists |
| Wait for cloud processing | Slow, quota-bound |
| Copy transcript to knowledge base | Manual, error-prone |
| Summaries generated | Unwanted; user only wants raw transcript |

---

## 3. Goals

| # | Goal |
|---|---|
| G1 | Pull new recordings from HiDock P1 over USB without HiNotes |
| G2 | Transcribe locally with **speaker labels** |
| G3 | Write transcripts to a **configurable Obsidian path** |
| G4 | Store **timestamps as metadata** (not inline in readable body) |
| G5 | Track sync/transcribe state so reruns are idempotent |
| G6 | Keep ongoing cost at **$0** API (local compute only) |

---

## 4. Non-goals

| # | Out of scope (for now) |
|---|---|
| NG1 | AI meeting summaries |
| NG2 | Named speaker recognition across meetings (“this is always Alice”) |
| NG3 | Calendar-based meeting titles |
| NG4 | HiNotes device transfer automation via cloud API |
| NG5 | Mobile app or GUI |
| NG6 | Real-time / live transcription |
| NG7 | Multi-user or hosted service |

---

## 5. Users

**Primary:** Single user (owner of HiDock P1) syncing personal/work meeting recordings into an Obsidian vault.

**Secondary use:** Pulling already-cloud-transcribed notes from HiNotes via unofficial API (`scripts/sync_transcripts.py`) — maintained but not the main product.

---

## 6. User stories

| ID | Story | Priority |
|---|---|---|
| US-1 | As a user, I plug in my P1 and run one command to sync new recordings to my Mac | P0 |
| US-2 | As a user, I run one command to transcribe synced audio with speaker labels | P0 |
| US-3 | As a user, I find new `.md` files in my Obsidian vault under a configurable folder | P0 |
| US-4 | As a user, I can re-run sync/transcribe without duplicating work | P0 |
| US-5 | As a user, I configure the output directory for my Obsidian vault | P0 |
| US-6 | As a user, I access per-utterance timestamps via a sidecar file | P1 |
| US-7 | As a user, I transcribe a single file for testing (`download` + `--limit 1`) | P1 |
| US-8 | As a user, I optionally delete recordings from device after successful sync | P2 |
| US-9 | As a user, I skip partial `Wip*.hda` clips by default | P1 |
| US-10 | As a user, I get a clear error when Chrome/HiNotes blocks USB | P1 |

---

## 7. Functional requirements

### 7.1 USB sync

| ID | Requirement | Status |
|---|---|---|
| FR-1 | List all `Rec*.hda` files on connected P1 | Done |
| FR-2 | Download new files not yet in pipeline state | Done |
| FR-3 | Save downloaded files as `.mp3` in configurable cache dir | Done |
| FR-4 | Key files by device MD5 **signature** for dedup | Done |
| FR-5 | Optionally include `Wip*.hda` files (`sync.include_wip`) | Done |
| FR-6 | Optionally delete from device after download | Config only |
| FR-7 | Fail with actionable message if USB locked by Chrome | Done |

### 7.2 Transcription

| ID | Requirement | Status |
|---|---|---|
| FR-8 | Transcribe audio with faster-whisper | Done |
| FR-9 | Assign speaker labels via pyannote diarization | Done |
| FR-10 | Configurable model, device, language | Done |
| FR-11 | Skip already-transcribed files unless `--force` | Done |
| FR-12 | Support `--limit N` for batch control | Done |

### 7.3 Output

| ID | Requirement | Status |
|---|---|---|
| FR-13 | Write markdown with YAML front matter | Done |
| FR-14 | Body format: `Speaker N: utterance` under `# Raw Transcript` | Done |
| FR-15 | Filename pattern configurable (`{date}_{title}_{id}`) | Done |
| FR-16 | Write `.segments.json` sidecar with start/end/speaker/text | Done |
| FR-17 | Front matter includes `recorded_at`, `device_file`, `signature` | Done |

### 7.4 CLI

| ID | Command | Status |
|---|---|---|
| FR-18 | `list` — show device files | Done |
| FR-19 | `sync` — download new files | Done |
| FR-20 | `download <name>` — single file | Done |
| FR-21 | `transcribe` — process cached audio | Done |
| FR-22 | `run` — sync then transcribe | Done |

---

## 8. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | **Privacy** — audio and transcripts stay on local machine |
| NFR-2 | **Cost** — no paid STT API required for primary path |
| NFR-3 | **Idempotency** — safe to re-run; state tracked in `.state/pipeline.json` |
| NFR-4 | **Portability** — macOS primary target; Node 22+ + Python 3.10+ |
| NFR-5 | **Simplicity** — vendored USB protocol in-repo; no external hidock-mcp dependency |
| NFR-6 | **Obsidian compatibility** — plain markdown + YAML; no proprietary plugins required |

---

## 9. Output specification

### 9.1 Path layout

```
{output.dir}/{date}_{title}_{id}.md
{output.dir}/{date}_{title}_{id}.segments.json   # when save_segments_json: true (default)
```

Example:

```
Transcripts/HiDock/personal/2026-05-21_Recording_Rec58_e9b8238c.md
```

Fireflies reference layout:

```
Transcripts/Fireflies/kite/2026-05-21_Weekly_AI_Practice_Sharing_Session_01KRN0YZ2ZW1WDPRAGHTDN2MGT.md
```

### 9.2 Markdown front matter

| Field | Required | Example |
|---|---|---|
| `title` | Yes | `Recording Rec58` |
| `date` | Yes | `2026/05/21` |
| `recorded_at` | Yes | `2026-05-21T15:46:15` |
| `device_file` | Yes | `2026May21-154615-Rec58.hda` |
| `signature` | Yes | MD5 hex (32 chars) |
| `source` | Yes | `HiDock` |
| `tags` | Yes | `[transcript, hidock, meeting]` |
| `duration_seconds` | No | `3600.0` |
| `segments_file` | No | basename of sidecar JSON (default: written when `save_segments_json: true`) |

### 9.3 Body

```markdown
# Raw Transcript

Speaker 1: Hello everyone.
Speaker 2: Thanks for joining.
```

No inline timestamps in body — those live in `.segments.json`.

---

## 10. Phases

### Phase 1 — MVP (current)

- [x] USB list + download
- [x] Local transcription + diarization
- [x] Fireflies-style markdown output
- [x] Configurable paths and state tracking
- [ ] End-to-end test on one real recording
- [ ] Backfill script/docs for 220-file backlog

### Phase 2 — Quality of life

- [ ] USB plug-in trigger (launchd)
- [ ] Background job queue (one at a time)
- [ ] Device delete after successful transcribe
- [ ] Better error recovery (partial download retry)

### Phase 3 — Enhancements (optional)

- [ ] Speaker name mapping library
- [ ] Calendar title enrichment
- [ ] Cloud STT fallback adapter (AssemblyAI)

---

## 11. Success metrics

| Metric | Target |
|---|---|
| Manual steps per new recording | 1 command (`run`) or 2 (`sync` + `transcribe`) |
| HiNotes dependency for transcripts | None |
| Duplicate transcript files on re-run | 0 |
| API cost per month | $0 |
| Time to first transcript (after setup) | < 30 min including model download |

---

## 12. Constraints & dependencies

| Constraint | Detail |
|---|---|
| USB lock | Close Chrome/HiNotes before sync |
| Node 22+ | Required for `device_usb/` |
| libusb | `brew install libusb` on macOS |
| HF token | Required for pyannote; accept model license |
| Compute | Long meetings = long local processing |
| Titles | Device filenames lack meeting names; manual rename in Obsidian |

---

## 13. Open items

1. End-to-end validation on `2026May21-154615-Rec58.hda`
2. Confirm `.hda` → MP3 assumption on all firmware versions
3. Backfill strategy for ~220 files / ~54 GB
4. `delete_after_download` not wired in sync script yet

---

## 14. References

- [ERD.md](ERD.md) — data model
- [research-and-approach.md](research-and-approach.md) — technical research and alternatives
- [README.md](../README.md) — user setup and usage
