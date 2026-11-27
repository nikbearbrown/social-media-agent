"""Call from a local scheduler. Runs the bundled offline plan for the last complete UTC week."""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sys


def previous_complete_week(day):
    return day - timedelta(days=day.weekday() + 7)


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    week = previous_complete_week(datetime.now(timezone.utc).date())
    os.execv(sys.executable, [sys.executable, "-m", "social_media_agent.orchestrator",
                             "--plan", "examples/orchestrator-demo.json",
                             "--week", week.isoformat(), "--trigger", "timer"])
