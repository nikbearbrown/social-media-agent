from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO

from social_media_agent.__main__ import aggregate, bluesky, config, main

WEEK = date(2026, 11, 23)
STAMP = "2026-11-24T12:00:00Z"
BASE = ["--config", "examples/fictional-themes.json", "--week", WEEK.isoformat()]


def post(i, handle="pub.example", **extra):
    return {"post": {"uri": f"item-{i}", "author": {"handle": handle},
                     "record": {"text": "clinic hours", "createdAt": STAMP}}, **extra}


class CollectorTests(unittest.TestCase):
    def test_demo_output(self):
        p = subprocess.run([sys.executable, "-m", "social_media_agent", *BASE,
                            "--fixture", "examples/fictional-posts.jsonl", "--min-count", "1"],
                           text=True, capture_output=True, check=True)
        data = json.loads(p.stdout)
        self.assertEqual(data["eligible_items"], 3)
        self.assertEqual(data["duplicate_items"], 1)
        self.assertEqual(data["theme_mentions"]["care-access-language"], 2)
        self.assertNotIn("example-1", p.stdout)
        self.assertNotIn("Fictional reminder", p.stdout)

    def test_week_boundary_utc_and_literal_matching(self):
        themes, _ = config("examples/fictional-themes.json")
        rows = [
            ("1", "2026-11-22T23:00:00-02:00", "CLINIC HOURS and care access"),
            ("2", "2026-11-30T00:00:00Z", "clinic hours"),
            ("3", STAMP, "clinic hourss and aftercare access"),
        ]
        self.assertEqual(aggregate(rows, themes, WEEK, 1),
                         ({"care-access-language": 1}, 2, 0))

    def test_default_suppression(self):
        themes, _ = config("examples/fictional-themes.json")
        self.assertEqual(aggregate([("1", STAMP, "clinic hours")], themes, WEEK, 5)[0], {})

    def test_cross_author_reposts_and_replies_excluded(self):
        reply = post(3)
        reply["post"]["record"]["reply"] = {"root": {}}
        data = {"feed": [post(1), post(2, handle="other.example"), reply,
                         post(4, reason={"type":"repost"})]}
        self.assertEqual(list(bluesky(["pub.example"], 1, lambda *_: data)),
                         [("item-1", STAMP, "clinic hours")])

    def test_pagination_is_bounded(self):
        seen = []
        def fetch(actor, cursor):
            seen.append((actor, cursor))
            return {"feed": [post(1)], "cursor": str(len(seen))}
        self.assertEqual(len(list(bluesky(["pub.example"], 2, fetch))), 2)
        self.assertEqual(seen, [("pub.example", None), ("pub.example", "1")])

    def test_repeated_cursor_fails(self):
        with self.assertRaises(ValueError):
            list(bluesky(["pub.example"], 2, lambda *_: {"feed": [], "cursor": "same"}))

    def test_live_gate(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
            main([*BASE, "--bluesky"])
        self.assertEqual(error.exception.code, 2)

    def test_live_http_error_does_not_emit_partial_report(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td, "cfg.json")
            cfg.write_text('{"publishers":["pub.example"],"themes":{"theme":["clinic hours"]}}')
            out = StringIO()
            with patch("social_media_agent.__main__.bluesky", side_effect=HTTPError(
                    "https://example.org", 429, "rate limit", {}, None)), redirect_stdout(out), redirect_stderr(StringIO()):
                result = main(["--config", str(cfg), "--week", "2026-01-05", "--bluesky",
                               "--confirm-approved-publishers"])
            self.assertEqual(result, 1)
            self.assertEqual(out.getvalue(), "")

    def test_offline_cli_invalid_input_no_report(self):
        with tempfile.TemporaryDirectory() as td:
            broken = Path(td, "bad.jsonl")
            broken.write_text('{"id":"private-id","created_at":"bad","text":"private-text"}')
            out, err = StringIO(), StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                result = main([*BASE, "--fixture", str(broken)])
            self.assertEqual(result, 1)
            self.assertEqual(out.getvalue(), "")
            self.assertNotIn("private-", err.getvalue())


if __name__ == "__main__":
    unittest.main()
