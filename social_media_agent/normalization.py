"""Translate source-native records to one internal schema before combining."""
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

COMMON_SCHEMA = "social-media-agent/normalized-v1"
FIELD_MAP = {
    "jsonl": ("id", "created_at", "text"),
    "rss": ("guid", "pubDate", "title"),
    "atom": ("id", "published", "title"),
    "bluesky-json": ("uri", "record.createdAt", "record.text"),
    "youtube-atom": ("videoId", "published", "title"),
}


@dataclass(frozen=True)
class NativeRecord:
    format: str
    fields: dict


@dataclass(frozen=True)
class CommonRecord:
    item_id: str
    published_at_utc: str
    text: str

    def as_row(self):
        return self.item_id, self.published_at_utc, self.text


class NormalizationError(ValueError):
    def __init__(self, reason, field_name):
        super().__init__(reason)
        self.reason = reason
        self.field_name = field_name


def field(record, path):
    try:
        for key in path.split("."):
            record = record[key]
    except (KeyError, TypeError):
        raise NormalizationError("missing-field", path) from None
    if record is None:
        raise NormalizationError("missing-field", path)
    return record


def to_common(record):
    paths = FIELD_MAP[record.format]
    ident, stamp, text = (field(record.fields, p) for p in paths)
    if not isinstance(ident, str) or not ident.strip() or len(ident) > 1024:
        raise NormalizationError("invalid-id", paths[0])
    if not isinstance(text, str) or len(text) > 10_000:
        raise NormalizationError("invalid-text", paths[2])
    try:
        if not isinstance(stamp, str):
            raise ValueError
        when = parsedate_to_datetime(stamp) if record.format == "rss" else datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if when.tzinfo is None:
            raise ValueError
        utc = when.astimezone(timezone.utc).isoformat()
    except (ValueError, OverflowError, TypeError):
        raise NormalizationError("invalid-timestamp", paths[1]) from None
    if record.format == "youtube-atom":
        ident = "yt:video:" + ident
    return CommonRecord(ident, utc, text)
