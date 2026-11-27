"""Independent read-only collector agents, with a shared tuple contract."""
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from xml.etree import ElementTree

from .__main__ import MAX_BYTES, NoRedirect, bluesky, fixtures

ATOM = "{http://www.w3.org/2005/Atom}"
YT = "{http://www.youtube.com/xml/schemas/2015}"
CHANNEL = re.compile(r"UC[A-Za-z0-9_-]{22}")
VIDEO = re.compile(r"[A-Za-z0-9_-]{11}")


def xml_rows(raw, channel=None):
    if len(raw) > MAX_BYTES:
        raise ValueError("feed too large")
    xml = raw.decode("utf-8-sig")
    if "\0" in xml or re.search(r"<!\s*(DOCTYPE|ENTITY)\b", xml, re.I):
        raise ValueError("DTD or entity declaration rejected")
    root = ElementTree.fromstring(xml)
    if root.tag == ATOM + "feed":
        for item in root.findall(ATOM + "entry"):
            if channel:
                if item.findtext(YT + "channelId") != channel:
                    raise ValueError("channel mismatch")
                vid = item.findtext(YT + "videoId", "")
                if not VIDEO.fullmatch(vid):
                    raise ValueError("invalid video ID")
                ident = "yt:video:" + vid
            else:
                ident = item.findtext(ATOM + "id")
            stamp = item.findtext(ATOM + "published")
            # Titles only: do not fetch media, descriptions, comments or transcripts.
            title = item.findtext(ATOM + "title")
            if ident is None or stamp is None or title is None:
                raise ValueError("required Atom fields missing")
            yield ident, stamp, title
    elif root.tag == "rss" and channel is None and root.find("channel") is not None:
        for item in root.findall("channel/item"):
            ident, title = item.findtext("guid"), item.findtext("title")
            stamp = parsedate_to_datetime(item.findtext("pubDate", ""))
            if not ident or title is None or stamp.tzinfo is None:
                raise ValueError("required RSS fields missing")
            yield ident, stamp.astimezone(timezone.utc).isoformat(), title
    else:
        raise ValueError("unsupported feed")


def local_feed(path):
    with Path(path).open("rb") as f:
        yield from xml_rows(f.read(MAX_BYTES + 1))


def youtube(channel):
    if not CHANNEL.fullmatch(channel):
        raise ValueError("invalid channel")
    url = "https://www.youtube.com/xml/feeds/videos.xml?" + urlencode({"channel_id": channel})
    req = Request(url, headers={"User-Agent": "social-media-agent/0.2",
                                "Accept": "application/atom+xml,application/xml"})
    with build_opener(NoRedirect()).open(req, timeout=10) as response:
        data = response.read(MAX_BYTES + 1)
    yield from xml_rows(data, channel=channel)


def collect(kind, target):
    if kind == "jsonl":
        return fixtures(target)
    if kind == "rss-file":
        return local_feed(target)
    if kind == "bluesky":
        return bluesky([target], 1)
    if kind == "youtube":
        return youtube(target)
    raise ValueError("unknown collector")
