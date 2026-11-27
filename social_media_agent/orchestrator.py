"""Trigger → policy → collector agents → normalization → aggregate review."""
import argparse
import errno
import ssl
from time import sleep
from http.client import IncompleteRead, RemoteDisconnected
from datetime import date, datetime, timedelta, timezone
import hashlib
from itertools import islice
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from xml.etree.ElementTree import ParseError

from .__main__ import HANDLE, KEY, aggregate, config
from .collectors import CHANNEL, SOURCE_PROFILES, collect
from .normalization import COMMON_SCHEMA, NormalizationError, to_common
from .ops import notify, set_status

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


def diagnose(exc):
    if isinstance(exc, NormalizationError):
        return exc.reason, None
    if isinstance(exc, HTTPError):
        code = exc.code
        wait = exc.headers.get("Retry-After", "") if exc.headers else ""
        exc.close()
        if code == 429:
            return "rate-limited", float(wait) if wait.isascii() and wait.isdigit() and len(wait) < 3 and 0 <= int(wait) <= 5 else None
        if code in {401, 403}:
            return "access-denied", None
        if code in {408, 500, 502, 503, 504} and not wait:
            return "upstream-http-" + str(code), 1
        return "http-" + str(code), None
    if isinstance(exc, FileNotFoundError):
        return "file-not-found", None
    if isinstance(exc, PermissionError):
        return "file-access-denied", None
    if isinstance(exc, ParseError):
        return "invalid-xml", None
    if isinstance(exc, json.JSONDecodeError):
        return "invalid-json", None
    if isinstance(exc, URLError):
        if isinstance(exc.reason, ssl.SSLError):
            return "tls-error", None
        return "network-error", 1
    if isinstance(exc, (ConnectionError, TimeoutError, IncompleteRead, RemoteDisconnected)):
        return "network-error", 1
    if isinstance(exc, OSError) and exc.errno in {errno.EINTR, errno.EAGAIN, errno.EBUSY}:
        return "temporary-io-error", 1
    if isinstance(exc, OSError):
        return "io-error", None
    return "invalid-source-record", None


SOURCE_ERRORS = (OSError, ValueError, TypeError, KeyError, AttributeError, ParseError, OverflowError, IncompleteRead)


def run_source(kind, target, invoke, pause):
    profile, transport, auth, formats = SOURCE_PROFILES[kind]
    base = {"agent": kind, "source_type": profile, "transport": transport,
            "access": auth, "expected_formats": list(formats)}
    history = []
    for attempt in range(1, 4):
        stage = "collect"
        try:
            raw = list(islice(invoke(kind, target), ROW_LIMIT + 1))
            if len(raw) > ROW_LIMIT:
                raise ValueError("source row cap")
            stage = "normalize"
            if any(x.format not in formats for x in raw):
                raise ValueError("unexpected native format")
            batch = [to_common(x).as_row() for x in raw]
            detected = sorted({x.format for x in raw})
            return batch, {**base, "status": "ok", "attempts": attempt,
                           "detected_formats": detected, "previous_failures": history}
        except SOURCE_ERRORS as exc:
            reason, delay = diagnose(exc)
            failure = {"stage": stage, "reason": reason}
            if isinstance(exc, NormalizationError):
                failure["field"] = exc.field_name
            history.append(failure)
            if stage != "collect" or delay is None or attempt == 3:
                return None, {**base, "status": "failed", **failure,
                              "attempts": attempt, "previous_failures": history[:-1]}
            pause(max(delay, attempt))


def run(path, week, trigger, allow_live=False, invoke=collect, now=None, pause=sleep):
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
        batch, receipt = run_source(kind, target, invoke, pause)
        if batch is not None:
            batches.append(batch)
        receipts.append({"source": label, **receipt})
    report = {"schema": "social-media-agent/run-v1", "trigger": trigger,
              "mode": mode, "week_utc": week.isoformat(), "min_count": floor,
              "normalized_record_schema": COMMON_SCHEMA,
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
    ap.add_argument("--status-file", type=Path, help="Local heartbeat file; parent directory must exist")
    ap.add_argument("--notify-slack", action="store_true", help="Send fixed operational alerts using an environment webhook")
    a = ap.parse_args(argv)

    def record(state):
        if a.status_file is not None:
            try:
                set_status(a.status_file, state)
            except OSError:
                print("Could not write the run status file.", file=sys.stderr)
                notify("status-write-failed", a.notify_slack)

    record("running")
    try:
        report = run(a.plan, a.week, a.trigger, a.confirm_approved_sources)
    except (ValueError, OSError, TypeError, KeyError, AttributeError, OverflowError):
        record("invalid-plan")
        notify("invalid-plan", a.notify_slack)
        print("Plan invalid or not authorized; no collectors dispatched.", file=sys.stderr)
        return 2
    failed = report["status"] == "withheld"
    record("source-failed" if failed else "finished")
    if failed:
        notify("source-failed", a.notify_slack, report["sources"])
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
