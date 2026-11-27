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
            return iter([("private-id", "2026-11-24T00:00:00Z", "clinic hours")])
        r = run(DEMO, WEEK, "timer", invoke=lookup)
        self.assertEqual(r["status"], "withheld")
        self.assertEqual(r["sources"][1]["reason"], "http-429")
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
                return iter([(kind + str(i), "2026-11-24T00:00:00Z", "clinic hours") for i in range(3)])
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
            ("yt:video:abc123abc12", "2026-11-24T00:00:00Z", "Demo title")])
        with self.assertRaises(ValueError):
            list(xml_rows(xml, "UC" + "b" * 22))

    def test_previous_complete_week(self):
        self.assertEqual(previous_complete_week(date(2026,11,30)), WEEK)
        self.assertEqual(previous_complete_week(date(2026,12,6)), WEEK)


if __name__ == "__main__":
    unittest.main()
