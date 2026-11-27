import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_BYTES = 2_000_000
MAX_ITEMS = 500
URL = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
HANDLE = re.compile(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+")
KEY = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def public_page(actor, cursor):
    if not HANDLE.fullmatch(actor) or len(actor) > 253:
        raise ValueError("invalid publisher handle")
    q = {"actor": actor, "filter": "posts_no_replies", "limit": 50}
    if cursor:
        q["cursor"] = cursor
    req = Request(URL + "?" + urlencode(q), headers={
        "Accept": "application/json", "User-Agent": "social-media-agent/0.1"})
    with build_opener(NoRedirect()).open(req, timeout=10) as response:
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("source response exceeded size limit")
    return json.loads(raw)


def bluesky(actors, pages, fetch=public_page):
    for actor in actors:
        cursor = None
        cursors = set()
        for _ in range(pages):
            payload = fetch(actor, cursor)
            feed = payload["feed"]
            if not isinstance(feed, list) or len(feed) > 50:
                raise ValueError("invalid source page")
            for item in feed:
                post = item["post"]
                record = post["record"]
                if item.get("reason") or record.get("reply") or post.get("author", {}).get("handle") != actor:
                    continue
                yield (post["uri"], record["createdAt"], record["text"])
            cursor = payload.get("cursor")
            if not cursor:
                break
            if not isinstance(cursor, str) or len(cursor) > 1024 or cursor in cursors:
                raise ValueError("invalid/repeated cursor")
            cursors.add(cursor)


def fixtures(path):
    with open(path, "rb") as f:
        data = f.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("fixture exceeds size limit")
    for line in data.decode().splitlines():
        if line.strip():
            item = json.loads(line)
            yield (item["id"], item["created_at"], item["text"])


def config(path):
    with open(path, "rb") as f:
        raw = f.read(100_001)
    if len(raw) > 100_000:
        raise ValueError("config exceeds size limit")
    cfg = json.loads(raw)
    if set(cfg) - {"publishers", "themes"}:
        raise ValueError("unsupported configuration fields")
    themes = cfg["themes"]
    if not isinstance(themes, dict) or not 1 <= len(themes) <= 25:
        raise ValueError("provide 1–25 themes")
    compiled = {}
    for name, aliases in themes.items():
        if not KEY.fullmatch(name) or len(name) > 50 or not isinstance(aliases, list) or not 1 <= len(aliases) <= 25:
            raise ValueError("invalid theme")
        if any(not isinstance(s, str) or not 2 <= len(s.strip()) <= 80 for s in aliases):
            raise ValueError("invalid alias")
        compiled[name] = [re.compile(r"(?<!\w)" + re.escape(normalize(s.strip())) + r"(?!\w)") for s in aliases]
    actors = cfg.get("publishers", [])
    if not isinstance(actors, list) or len(actors) > 5 or any(not isinstance(a, str) or len(a) > 253 or not HANDLE.fullmatch(a) for a in actors) or len(set(actors)) != len(actors):
        raise ValueError("provide up to five unique approved publisher handles")
    return compiled, actors


def normalize(s):
    return unicodedata.normalize("NFKC", s).casefold()


def aggregate(rows, themes, week, threshold):
    counts = Counter()
    seen = set()
    duplicates = 0
    eligible = 0
    for i, (ident, stamp, body) in enumerate(rows, 1):
        if i > MAX_ITEMS:
            raise ValueError("item limit exceeded; narrow the input")
        if not all(isinstance(x, str) for x in (ident, stamp, body)) or not ident or len(ident) > 1024 or len(body) > 10_000:
            raise ValueError("malformed item")
        ts = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            raise ValueError("timezone required")
        if not week <= ts.astimezone(timezone.utc).date() < week + timedelta(days=7):
            continue
        if ident in seen:
            duplicates += 1
            continue
        seen.add(ident)
        eligible += 1
        for name, patterns in themes.items():
            if any(p.search(normalize(body)) for p in patterns):
                counts[name] += 1
    return {k: v for k, v in sorted(counts.items()) if v >= threshold}, eligible, duplicates


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--week", required=True, type=date.fromisoformat, help="UTC Monday, YYYY-MM-DD")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--fixture", type=Path, help="Local synthetic or approved JSONL; no network")
    source.add_argument("--bluesky", action="store_true", help="Official public feed for explicitly approved organizational publishers")
    parser.add_argument("--confirm-approved-publishers", action="store_true")
    parser.add_argument("--pages", type=int, choices=(1, 2), default=1, help="Maximum pages per publisher")
    parser.add_argument("--min-count", type=int, default=5)
    a = parser.parse_args(argv)
    if a.week.weekday() != 0 or a.min_count < 1:
        parser.error("use a Monday and a positive count")
    if a.bluesky and (not a.confirm_approved_publishers or a.min_count < 5 or
                     a.week + timedelta(days=7) > datetime.now(timezone.utc).date()):
        parser.error("live mode requires a completed week, at least 5 per bucket, and approved publishers")
    try:
        themes, actors = config(a.config)
        if a.bluesky and not actors:
            raise ValueError("live mode requires explicit publisher handles")
        counts, n, dup = aggregate(bluesky(actors, a.pages) if a.bluesky else fixtures(a.fixture),
                                   themes, a.week, a.min_count)
    except HTTPError as e:
        e.close()
        print(f"source returned HTTP {e.code}; no output, no retries", file=sys.stderr)
        return 1
    except (ValueError, OSError, TypeError, KeyError, AttributeError):
        print("Source or configuration could not be validated. No report emitted.", file=sys.stderr)
        return 1
    result = {"mode": "bounded_public_publisher_sample" if a.bluesky else "local_input",
              "week_utc": a.week.isoformat(), "min_count": a.min_count,
              "theme_mentions": counts, "scope": "literal mentions; overlapping themes; not population estimates"}
    if not a.bluesky:
        result.update(eligible_items=n, duplicate_items=dup)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
