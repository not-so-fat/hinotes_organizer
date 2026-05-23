from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


HDA_PATTERN = re.compile(
    r"^(?:(\d{2}))?(\d{2})(\w{3})(\d{2})-(\d{2})(\d{2})(\d{2})-(Rec|Wip)(\d+)\.hda$",
    re.IGNORECASE,
)

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


@dataclass(frozen=True)
class ParsedRecording:
    device_file: str
    recorded_at: datetime
    rec_kind: str
    rec_id: str
    signature: str

    @property
    def date_str(self) -> str:
        return self.recorded_at.strftime("%Y-%m-%d")

    @property
    def date_slash(self) -> str:
        return self.recorded_at.strftime("%Y/%m/%d")

    @property
    def iso_datetime(self) -> str:
        return self.recorded_at.isoformat(timespec="seconds")

    @property
    def short_id(self) -> str:
        return self.signature[:8]


def parse_hda_filename(name: str, signature: str, fallback_time: datetime | None = None) -> ParsedRecording:
    match = HDA_PATTERN.match(name)
    if match:
        _century, yy, mon, dd, hh, mm, ss, kind, num = match.groups()
        month = MONTHS.get(mon.lower())
        if month is None:
            raise ValueError(f"Unknown month in filename: {name}")
        year = 2000 + int(yy)
        recorded_at = datetime(year, month, int(dd), int(hh), int(mm), int(ss))
        return ParsedRecording(
            device_file=name,
            recorded_at=recorded_at,
            rec_kind=kind,
            rec_id=f"{kind}{num}",
            signature=signature,
        )

    if fallback_time is not None:
        base = name.rsplit(".", 1)[0]
        return ParsedRecording(
            device_file=name,
            recorded_at=fallback_time,
            rec_kind="Rec",
            rec_id=base,
            signature=signature,
        )

    raise ValueError(f"Cannot parse HiDock filename: {name}")


def slugify_title(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title, flags=re.UNICODE)
    slug = re.sub(r"[\s_-]+", "_", slug.strip())
    return slug or "Recording"


def build_markdown_filename(pattern: str, parsed: ParsedRecording, title: str) -> str:
    rendered = pattern.format(
        date=parsed.date_str,
        title=slugify_title(title),
        id=parsed.short_id,
        rec_id=parsed.rec_id,
        signature=parsed.signature,
    )
    if not rendered.endswith(".md"):
        rendered += ".md"
    return rendered
