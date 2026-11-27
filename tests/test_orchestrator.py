from datetime import date
from pathlib import Path
from urllib.error import HTTPError
import json
import subprocess
import sys
import tempfile
import unittest

from social_media_agent.collectors import xml_rows
from social_media_agent.orchestrator import run
from social_media_agent.normalization import NativeRecord, to_common
from triggers.offline_timer import previous_complete_week

DEMO = Path("examples/orchestrator-demo.json")
WEEK = date(2026, 11, 23)
AFTER = date(2026, 11, 30)
CHANNEL = "UC" + "a" * 22


class OrchestratorTests(unittest.TestCase):
    def test_cli_dispatches_both_agents_and_deduplicates(self):
        out = subprocess.check_output([sys.executable, "-m", "social_media_agent.orchestrator",
                                       "--plan", str(DEMO), "--week", WEEK.isoformat()])
        r = json.loads(out)
        self.assertEqual([x["agent"] for x in r["sources"]], ["jsonl", "rss-file"])
        self.assertEqual((r["eligible_items"], r["duplicate_items"]), (4, 2))
        self.assertEqual(r["theme_mentions"]["support-resource-language"], 2)
        self.assertNotIn(b"example-3", out)

    def test_failure_withholds_healthy_source_too(self):
        def lookup(kind, target):
            if kind == "rss-file":
                raise HTTPError("https://private.example", 429, "slow down", {}, None)
            return iter([NativeRecord("jsonl", {"id":"private-id", "created_at":"2026-11-24T00:00:00Z","text":"clinic hours"})])
        r = run(DEMO, WEEK, "timer", invoke=lookup)
        self.assertEqual(r["status"], "withheld")
        self.assertEqual(r["sources"][1]["reason"], "rate-limited")
        self.assertNotIn("theme_mentions", r)
        self.assertNotIn("private", json.dumps(r))

    def test_live_agents_called_and_metadata_redacted(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "plan.json"
            (path.parent / "vocab.json").write_text('{"themes":{"test":["clinic hours"]}}')
            path.write_text(json.dumps({"mode":"live","vocabulary":"vocab.json","min_count":5,
                "sources":[{"name":"named-publication","kind":"bluesky","target":"pub.example"},
                           {"name":"another-publication","kind":"youtube","target":CHANNEL}]}))
            called = []
            def dispatch(kind, target):
                called.append(kind)
                if kind == "bluesky":
                    return iter([NativeRecord("bluesky-json", {"uri":kind+str(i),"record":{"createdAt":"2026-11-24T00:00:00Z","text":"clinic hours"}}) for i in range(3)])
                return iter([NativeRecord("youtube-atom", {"videoId":kind+str(i),"published":"2026-11-24T00:00:00Z","title":"clinic hours"}) for i in range(3)])
            for trigger, approve in [("timer", True), ("manual", False)]:
                with self.assertRaises(ValueError):
                    run(path, WEEK, trigger, approve, invoke=dispatch, now=AFTER)
            self.assertEqual(called, [])
            result = run(path, WEEK, "manual", True, invoke=dispatch, now=AFTER)
            self.assertEqual(called, ["bluesky","youtube"])
            self.assertEqual(result["theme_mentions"], {"test":6})
            for x in ("pub.example", CHANNEL, "named-publication", "eligible_items", "clinic hours"):
                self.assertNotIn(x, json.dumps(result))

    def test_reject_xml_entities_and_wrong_channel(self):
        with self.assertRaises(ValueError):
            list(xml_rows(b'<!DOCTYPE foo><rss/>'))
        xml = f'''<feed xmlns="http://www.w3.org/2005/Atom"
              xmlns:yt="http://www.youtube.com/xml/schemas/2015">
              <entry><yt:channelId>{CHANNEL}</yt:channelId><yt:videoId>abc123abc12</yt:videoId>
              <title>Demo title</title><published>2026-11-24T00:00:00Z</published>
              </entry></feed>'''.encode()
        self.assertEqual(list(xml_rows(xml, CHANNEL)), [
            ("yt:video:abc123abc12", "2026-11-24T00:00:00+00:00", "Demo title")])
        with self.assertRaises(ValueError):
            list(xml_rows(xml, "UC" + "b" * 22))

    def test_source_fields_map_to_same_id_timestamp_and_text(self):
        a = to_common(NativeRecord("rss", {"guid":"example","pubDate":"Thu, 26 Nov 2026 08:00:00 -0400","title":"Useful title"}))
        b = to_common(NativeRecord("jsonl", {"id":"example","created_at":"2026-11-26T12:00:00Z","text":"Useful title"}))
        self.assertEqual(a, b)
        self.assertEqual(a.published_at_utc, "2026-11-26T12:00:00+00:00")

    def test_temporary_failure_recovers_and_only_that_source_retries(self):
        from social_media_agent.collectors import collect
        called, delays = [], []
        def lookup(kind, target):
            called.append(kind)
            if kind == "rss-file" and called.count(kind) < 3:
                raise HTTPError("https://private.example", 503, "busy", {}, None)
            return collect(kind, target)
        r = run(DEMO, WEEK, "manual", invoke=lookup, pause=delays.append)
        self.assertEqual(called, ["jsonl","rss-file","rss-file","rss-file"])
        self.assertEqual(delays, [1, 2])
        self.assertEqual(r["status"], "review-required")
        self.assertEqual(r["sources"][1]["attempts"], 3)
        self.assertEqual(r["sources"][1]["previous_failures"][0]["reason"], "upstream-http-503")

    def test_exhausted_retry_explains_failure(self):
        from social_media_agent.collectors import collect
        def lookup(kind, target):
            if kind == "rss-file":
                raise TimeoutError("raw error")
            return collect(kind, target)
        r = run(DEMO, WEEK, "manual", invoke=lookup, pause=lambda _: None)
        self.assertEqual(r["status"], "withheld")
        self.assertEqual(r["sources"][0]["status"], "ok")
        self.assertEqual(r["sources"][1]["attempts"], 3)
        self.assertEqual(r["sources"][1]["reason"], "network-error")
        self.assertNotIn("raw error", json.dumps(r))

    def test_missing_field_stops_at_normalize_without_retry(self):
        def lookup(kind, target):
            return iter([NativeRecord("jsonl", {"id":"private-id"})])
        r = run(Path("examples/single-source-demo.json"), WEEK, "manual", invoke=lookup,
                pause=lambda _: self.fail("should not retry a missing field"))
        self.assertEqual(r["sources"][0]["attempts"], 1)
        self.assertEqual(r["sources"][0]["stage"], "normalize")
        self.assertEqual(r["sources"][0]["reason"], "missing-field")
        self.assertEqual(r["sources"][0]["field"], "created_at")

    def test_previous_complete_week(self):
        self.assertEqual(previous_complete_week(date(2026,11,30)), WEEK)
        self.assertEqual(previous_complete_week(date(2026,12,6)), WEEK)


if __name__ == "__main__":
    unittest.main()
