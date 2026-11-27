"""Fetch from configured sources without renaming their record fields."""
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from xml.etree import ElementTree

from .__main__ import MAX_BYTES, NoRedirect, bluesky_posts, fixture_objects
from .normalization import NativeRecord, to_common

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
CHANNEL = re.compile(r"UC[A-Za-z0-9_-]{22}")
VIDEO = re.compile(r"[A-Za-z0-9_-]{11}")

SOURCE_PROFILES = {
    "jsonl": ("local-export", "local-file", "local-read-access", ("jsonl",)),
    "rss-file": ("publisher-feed-snapshot", "local-file", "local-read-access", ("rss", "atom")),
    "bluesky": ("bluesky-publisher", "public-https", "no-api-credential", ("bluesky-json",)),
    "youtube": ("youtube-channel", "public-https", "no-api-credential", ("youtube-atom",)),
}


def xml_native(raw, channel=None):
    if len(raw) > MAX_BYTES:
        raise ValueError("feed too large")
    xml = raw.decode("utf-8-sig")
    if "\0" in xml or re.search(r"<!\s*(DOCTYPE|ENTITY)\b", xml, re.I):
        raise ValueError("DTD or entity declaration rejected")
    root = ElementTree.fromstring(xml)
    if root.tag == ATOM + "feed":
        for item in root.findall(ATOM + "entry"):
            fields = {k: item.findtext(ATOM + k) for k in ("id", "published", "title")}
            if channel:
                if item.findtext(YT + "channelId") != channel:
                    raise ValueError("channel mismatch")
                vid = item.findtext(YT + "videoId", "")
                if not VIDEO.fullmatch(vid):
                    raise ValueError("invalid video ID")
                fields["videoId"] = vid
            yield NativeRecord("youtube-atom" if channel else "atom", fields)
    elif root.tag == "rss" and channel is None and root.find("channel") is not None:
        for item in root.findall("channel/item"):
            yield NativeRecord("rss", {k: item.findtext(k) for k in ("guid", "pubDate", "title")})
    else:
        raise ValueError("unsupported feed")


def xml_rows(raw, channel=None):
    for record in xml_native(raw, channel):
        yield to_common(record).as_row()


def local_feed(path):
    with Path(path).open("rb") as f:
        yield from xml_native(f.read(MAX_BYTES + 1))


def youtube(channel):
    if not CHANNEL.fullmatch(channel):
        raise ValueError("invalid channel")
    url = "https://www.youtube.com/xml/feeds/videos.xml?" + urlencode({"channel_id": channel})
    req = Request(url, headers={"User-Agent": "social-media-agent/0.2",
                                "Accept": "application/atom+xml,application/xml"})
    with build_opener(NoRedirect()).open(req, timeout=10) as response:
        data = response.read(MAX_BYTES + 1)
    yield from xml_native(data, channel=channel)


def collect(kind, target):
    if kind == "jsonl":
        return (NativeRecord("jsonl", item) for item in fixture_objects(target))
    if kind == "rss-file":
        return local_feed(target)
    if kind == "bluesky":
        return (NativeRecord("bluesky-json", post) for post in bluesky_posts([target], 1))
    if kind == "youtube":
        return youtube(target)
    raise ValueError("unknown collector")
