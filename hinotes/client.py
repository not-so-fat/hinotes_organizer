"""Unofficial HiNotes web API client (reverse-engineered from hinotes.hidock.com frontend)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests


BASE_URL = "https://hinotes.hidock.com"
TOKEN_EXPIRED = 10000


class HiNotesError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class NoteSummary:
    id: str
    title: str
    state: str | None
    create_time: str | None
    raw: dict[str, Any]


class HiNotesClient:
    def __init__(
        self,
        access_token: str,
        *,
        language: str = "en",
        session: requests.Session | None = None,
    ):
        self.access_token = access_token
        self.language = language
        self.session = session or requests.Session()

    def _headers(self, *, json_request: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "accesstoken": self.access_token,
            "Interface-Language": self.language,
        }
        if json_request:
            headers["Content-Type"] = "application/json"
        return headers

    def _handle_response(self, payload: dict[str, Any]) -> Any:
        error = payload.get("error")
        if error == 0:
            return payload.get("data")
        message = payload.get("message") or f"API error {error}"
        if error == TOKEN_EXPIRED:
            raise HiNotesError(error, "Access token expired. Log in again in Chrome and refresh the token.")
        raise HiNotesError(error, message)

    def get_json(self, path: str, *, params: dict[str, Any] | None = None, timeout: int = 60) -> Any:
        response = self.session.get(
            f"{BASE_URL}{path}",
            params=params,
            headers=self._headers(),
            timeout=timeout,
        )
        response.raise_for_status()
        return self._handle_response(response.json())

    def post_form(self, path: str, data: dict[str, Any], *, timeout: int = 120) -> Any:
        response = self.session.post(
            f"{BASE_URL}{path}",
            data=data,
            headers=self._headers(),
            timeout=timeout,
        )
        response.raise_for_status()
        return self._handle_response(response.json())

    def get_text(self, path: str, *, params: dict[str, Any] | None = None, timeout: int = 120) -> str:
        response = self.session.get(
            f"{BASE_URL}{path}",
            params=params,
            headers=self._headers(),
            timeout=timeout,
        )
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            data = self._handle_response(response.json())
            if isinstance(data, str):
                return data
            return json.dumps(data, indent=2, ensure_ascii=False)
        return response.text

    @staticmethod
    def tz_offset_minutes() -> int:
        now = datetime.now().astimezone()
        return int(now.utcoffset().total_seconds() // 60) if now.utcoffset() else 0

    def list_recording_notes(
        self,
        *,
        page_index: int = 0,
        page_size: int = 20,
        folder_id: str | None = None,
    ) -> tuple[list[NoteSummary], dict[str, Any]]:
        params: dict[str, Any] = {
            "pageIndex": page_index,
            "pageSize": page_size,
            "sortType": "descending",
            "sortField": "dateCreated",
        }
        if folder_id:
            params["folderId"] = folder_id

        data = self.get_json("/v1/note/recording/list", params=params)
        if not isinstance(data, dict):
            raise HiNotesError(-1, f"Unexpected list response: {type(data)}")

        content = data.get("content") or []
        notes: list[NoteSummary] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            notes.append(
                NoteSummary(
                    id=str(item.get("id") or item.get("noteId") or ""),
                    title=str(item.get("title") or item.get("name") or "Untitled"),
                    state=item.get("state"),
                    create_time=item.get("createTime") or item.get("createtime") or item.get("create_time"),
                    raw=item,
                )
            )
        return notes, data

    def iter_all_recording_notes(self, *, page_size: int = 50) -> list[NoteSummary]:
        all_notes: list[NoteSummary] = []
        page_index = 0
        while True:
            notes, meta = self.list_recording_notes(page_index=page_index, page_size=page_size)
            all_notes.extend(notes)
            if meta.get("last") is True or not notes or len(notes) < page_size:
                break
            page_index += 1
        return all_notes

    def get_note_info(self, note_id: str) -> dict[str, Any]:
        data = self.post_form("/v2/note/info", {"id": note_id})
        if not isinstance(data, dict):
            raise HiNotesError(-1, f"Unexpected note info response: {type(data)}")
        return data

    def get_transcription(self, note_id: str) -> Any:
        return self.post_form("/v2/note/transcription/list", {"noteId": note_id})

    def export_transcript_txt(self, note_id: str, *, include_timestamps: bool = True, include_speakers: bool = True) -> str:
        include_fields: list[str] = []
        if include_timestamps:
            include_fields.append("timestamp")
        if include_speakers:
            include_fields.append("speaker_name")

        params: dict[str, Any] = {
            "note_id": note_id,
            "scope": "transcription",
            "export_format": "TXT",
            "language": self.language,
            "tz_offset": self.tz_offset_minutes(),
        }
        if include_fields:
            params["include_field"] = ",".join(include_fields)

        return self.get_text("/v2/note/export", params=params)

    def trigger_summarize(self, note_id: str, *, ai_engine: str, template_code: str) -> Any:
        return self.post_form(
            "/v2/note/summarize",
            {
                "noteId": note_id,
                "aiEngine": ai_engine,
                "templateCode": template_code,
                "tzOffset": self.tz_offset_minutes(),
            },
        )

    def verify_token(self) -> dict[str, Any]:
        data = self.post_form("/v1/user/info", {})
        if not isinstance(data, dict):
            raise HiNotesError(-1, f"Unexpected user info response: {type(data)}")
        return data


def format_transcription_payload(payload: Any) -> str:
    """Best-effort plain-text formatter for /v2/note/transcription/list payloads."""
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload.strip()

    if isinstance(payload, dict):
        for key in ("content", "transcription", "paragraphs", "sentences", "items", "list"):
            if key in payload:
                return format_transcription_payload(payload[key])

    if isinstance(payload, list):
        lines: list[str] = []
        for item in payload:
            if isinstance(item, str):
                lines.append(item)
                continue
            if not isinstance(item, dict):
                lines.append(str(item))
                continue

            speaker = item.get("speaker") or item.get("speakerName") or item.get("name")
            text = item.get("text") or item.get("content") or item.get("paragraphText") or item.get("sentence")
            timestamp = item.get("timestamp") or item.get("startTime") or item.get("time")

            parts: list[str] = []
            if timestamp:
                parts.append(f"[{timestamp}]")
            if speaker:
                parts.append(f"{speaker}:")
            if text:
                parts.append(str(text).strip())
            elif item.get("paragraph"):
                parts.append(str(item["paragraph"]).strip())

            if parts:
                lines.append(" ".join(parts))
            else:
                lines.append(json.dumps(item, ensure_ascii=False))

        return "\n".join(line for line in lines if line).strip()

    return json.dumps(payload, indent=2, ensure_ascii=False)
