"""Operational alerts, deliberately separate from source data and reports."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.request import Request, build_opener

from .__main__ import NoRedirect

WEBHOOK = re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9]+/[A-Za-z0-9]+/[A-Za-z0-9]+")
MESSAGES = {
    "invalid-plan": "Social Media Agent: invalid or unapproved run plan. No collectors ran. Check the run configuration.",
    "source-failed": "Social Media Agent: a collector failed. Combined report withheld. Check local source receipts.",
    "heartbeat-missing": "Social Media Agent: expected run heartbeat is missing. Check the scheduler and status path.",
    "heartbeat-invalid": "Social Media Agent: run heartbeat could not be read. Check its status file and permissions.",
    "heartbeat-stale": "Social Media Agent: run heartbeat is overdue. Check the scheduler or a stuck collector.",
    "status-write-failed": "Social Media Agent: could not write run status. Check the status directory and permissions.",
}


def slack(event):
    url = os.environ.get("SOCIAL_MEDIA_AGENT_SLACK_WEBHOOK_URL", "")
    if not WEBHOOK.fullmatch(url):
        raise ValueError("Slack webhook missing or invalid")
    req = Request(url, method="POST", data=json.dumps({"text": MESSAGES[event]}).encode(),
                  headers={"Content-Type": "application/json"})
    with build_opener(NoRedirect()).open(req, timeout=5) as response:
        if response.status != 200 or response.read(16).strip() != b"ok":
            raise OSError("Slack rejected alert")


def notify(event, enabled):
    if not enabled:
        return False
    try:
        slack(event)
        return True
    except (OSError, ValueError):
        print("Operational Slack alert could not be delivered.", file=sys.stderr)
        return False


def set_status(path, state, now=None):
    now = now or datetime.now(timezone.utc)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as f:
            temp = f.name
            json.dump({"state": state, "at_utc": now.isoformat()}, f)
        os.replace(temp, path)
    finally:
        if temp and os.path.exists(temp):
            os.unlink(temp)


def overdue(path, max_minutes, now=None):
    now = now or datetime.now(timezone.utc)
    try:
        with path.open() as f:
            data = json.loads(f.read(4096))
        stamp = datetime.fromisoformat(data["at_utc"])
        if (stamp.tzinfo is None or stamp > now or
                data["state"] not in {"running", "invalid-plan", "source-failed", "finished"}):
            return "heartbeat-invalid", "invalid"
    except FileNotFoundError:
        return "heartbeat-missing", "missing"
    except (ValueError, TypeError, OSError, KeyError):
        return "heartbeat-invalid", "invalid"
    if (now - stamp).total_seconds() > max_minutes * 60:
        return "heartbeat-stale", data["at_utc"]
    return None, None


def watchdog(path, max_minutes, enabled, now=None, send=notify):
    event, stamp = overdue(path, max_minutes, now)
    # Separate, local receipt allows one alert per unchanged outage.
    marker = path.with_name(path.name + ".alerted")
    if not event:
        marker.unlink(missing_ok=True)
        return None, False
    token = event + ":" + stamp
    if enabled and (not marker.exists() or marker.read_text() != token) and send(event, True):
        # Run a single watchdog instance per plan.
        marker.write_text(token)
        return event, True
    return event, False


def main(argv=None):
    p = argparse.ArgumentParser(description="Detect a collector run that stopped or never started")
    p.add_argument("--status-file", type=Path, required=True)
    p.add_argument("--max-age-minutes", type=int, required=True)
    p.add_argument("--notify-slack", action="store_true")
    a = p.parse_args(argv)
    if a.max_age_minutes < 1:
        p.error("max age must be positive")
    try:
        event, sent = watchdog(a.status_file, a.max_age_minutes, a.notify_slack)
    except OSError:
        print("Unable to update watchdog receipt.", file=sys.stderr)
        return 2
    print(json.dumps({"status": event or "current", "slack_alert_sent": sent}))
    return 1 if event else 0


if __name__ == "__main__":
    raise SystemExit(main())
