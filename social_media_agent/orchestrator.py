"""Trigger → policy → collector agents → normalization → aggregate review."""
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
from itertools import islice
import json
from pathlib import Path
import sys
from urllib.error import HTTPError
from xml.etree.ElementTree import ParseError

from .__main__ import HANDLE, KEY, aggregate, config
from .collectors import CHANNEL, collect

LIVE = {"bluesky", "youtube"}
OFFLINE = {"jsonl", "rss-file"}
SOURCE_LIMIT = 5
ROW_LIMIT = 100


def read_plan(path, allow_live, week, now):
    with path.open("rb") as f:
        data = f.read(32_769)
    if len(data) > 32_768:
        raise ValueError("plan too large")
    plan = json.loads(data)
    if set(plan) != {"mode", "vocabulary", "sources", "min_count"}:
        raise ValueError("unknown or missing plan fields")
    mode = plan["mode"]
    permitted = LIVE if mode == "live" else OFFLINE if mode == "offline" else set()
    sources = plan["sources"]
    floor = plan["min_count"]
    if not isinstance(sources, list) or not 1 <= len(sources) <= SOURCE_LIMIT:
        raise ValueError("provide 1–5 sources")
    if type(floor) is not int or floor < (5 if mode == "live" else 1):
        raise ValueError("invalid threshold")
    if mode == "live" and (not allow_live or week + timedelta(days=7) > now):
        raise ValueError("live mode requires approval and a completed UTC week")
    ids, endpoints, resolved = set(), set(), []
    for source in sources:
        if set(source) != {"name", "kind", "target"}:
            raise ValueError("invalid source")
        name, kind, target = (source[k] for k in ("name", "kind", "target"))
        if not KEY.fullmatch(name) or len(name) > 40 or name in ids or kind not in permitted:
            raise ValueError("invalid or duplicate source")
        if not isinstance(target, str) or not target or len(target) > 253:
            raise ValueError("invalid target")
        if kind == "bluesky" and not HANDLE.fullmatch(target):
            raise ValueError("invalid handle")
        if kind == "youtube" and not CHANNEL.fullmatch(target):
            raise ValueError("invalid channel")
        actual = target if kind in LIVE else (path.parent / target).resolve()
        if (kind, actual) in endpoints:
            raise ValueError("duplicate source target")
        endpoints.add((kind, actual))
        ids.add(name)
        resolved.append((name, kind, actual))
    themes, publishers = config(path.parent / plan["vocabulary"])
    if publishers:
        raise ValueError("put publishers in the plan, not vocabulary config")
    return mode, floor, resolved, themes


def run(path, week, trigger, allow_live=False, invoke=collect, now=None):
    if week.weekday() != 0 or trigger not in {"manual", "timer", "ci"}:
        raise ValueError("invalid trigger or UTC week")
    mode, floor, sources, themes = read_plan(
        path, allow_live, week, now or datetime.now(timezone.utc).date())
    if mode == "live" and trigger != "manual":
        raise ValueError("live dispatch is manual only in this release")
    signature = {k: [p.pattern for p in v] for k, v in themes.items()}
    hash_ = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    receipts = []
    batches = []
    for i, (name, kind, target) in enumerate(sources, 1):
        label = name if mode == "offline" else f"source-{i}"
        try:
            batch = list(islice(invoke(kind, target), ROW_LIMIT + 1))
            if len(batch) > ROW_LIMIT:
                raise ValueError("source row cap")
            # Validate every source before attempting the pooled summary.
            aggregate(batch, {}, week, floor)
            batches.append(batch)
            receipts.append({"source": label, "agent": kind, "status": "ok"})
        except (HTTPError, OSError, ValueError, TypeError, KeyError, AttributeError, ParseError, OverflowError) as exc:
            reason = f"http-{exc.code}" if isinstance(exc, HTTPError) else "read-or-validation-error"
            if isinstance(exc, HTTPError):
                exc.close()
            receipts.append({"source": label, "agent": kind, "status": "failed", "reason": reason})
    report = {"schema": "social-media-agent/run-v1", "trigger": trigger,
              "mode": mode, "week_utc": week.isoformat(), "min_count": floor,
              "vocabulary_sha256": hash_, "sources": receipts}
    if any(r["status"] != "ok" for r in receipts):
        report.update(status="withheld", reason="one or more collector agents failed")
        return report
    counts, n, dup = aggregate((row for batch in batches for row in batch), themes, week, floor)
    report.update(status="review-required", theme_mentions=counts,
                  scope="bounded sample; overlapping literal mentions; not population estimates")
    if mode == "offline":
        report.update(eligible_items=n, duplicate_items=dup)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", type=Path, required=True)
    ap.add_argument("--week", type=date.fromisoformat, required=True)
    ap.add_argument("--trigger", choices=["manual", "timer", "ci"], default="manual")
    ap.add_argument("--confirm-approved-sources", action="store_true")
    a = ap.parse_args(argv)
    try:
        report = run(a.plan, a.week, a.trigger, a.confirm_approved_sources)
    except (ValueError, OSError, TypeError, KeyError, AttributeError, OverflowError):
        print("Plan invalid or not authorized; no collectors dispatched.", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["status"] == "withheld" else 0


if __name__ == "__main__":
    raise SystemExit(main())
