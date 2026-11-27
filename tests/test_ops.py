from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from social_media_agent import ops, orchestrator

NOW = datetime(2026, 11, 27, 20, tzinfo=timezone.utc)


class OpsTests(unittest.TestCase):
    def test_watcher_only_alerts_once_on_missing_and_rearms(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "run.json"
            calls = []
            def send(event, enabled):
                calls.append(event)
                return True
            self.assertEqual(ops.watchdog(p, 90, True, NOW, send), ("heartbeat-missing", True))
            self.assertEqual(ops.watchdog(p, 90, True, NOW, send), ("heartbeat-missing", False))
            ops.set_status(p, "finished", NOW)
            self.assertEqual(ops.watchdog(p, 90, True, NOW, send), (None, False))
            self.assertEqual(ops.watchdog(p, 90, True, NOW + timedelta(hours=2), send),
                             ("heartbeat-stale", True))
            self.assertEqual(calls, ["heartbeat-missing", "heartbeat-stale"])

    def test_failure_is_distinct_from_no_run_and_dry_run_never_alerts(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "run.json"
            ops.set_status(p, "source-failed", NOW)
            self.assertEqual(ops.overdue(p, 90, NOW), (None, None))
            with patch.object(ops, "slack") as mocked:
                self.assertEqual(ops.watchdog(p, 90, False, NOW + timedelta(hours=2)),
                                 ("heartbeat-stale", False))
            mocked.assert_not_called()

    def test_orchestrator_routes_safe_failure_events(self):
        with tempfile.TemporaryDirectory() as d, redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            p = Path(d) / "run.json"
            common = ["--week","2026-11-23","--status-file",str(p),"--notify-slack"]
            with patch.object(orchestrator, "notify") as n:
                self.assertEqual(orchestrator.main([*common,"--plan","missing-secret.json"]), 2)
                self.assertEqual(json.loads(p.read_text())["state"], "invalid-plan")
                n.assert_called_once_with("invalid-plan", True)
                n.reset_mock()
                self.assertEqual(orchestrator.main([*common,"--plan","examples/failed-source-demo.json"]), 1)
                self.assertEqual(json.loads(p.read_text())["state"], "source-failed")
                n.assert_called_once_with("source-failed", True)

    def test_notify_builds_fixed_payload_without_exposing_secret(self):
        with patch.dict("os.environ", {"SOCIAL_MEDIA_AGENT_SLACK_WEBHOOK_URL":
                                       "https://hooks.slack.com/services/A/B/Secret"}), patch.object(ops, "build_opener") as b:
            response = b.return_value.open.return_value.__enter__.return_value
            response.status, response.read.return_value = 200, b"ok"
            self.assertTrue(ops.notify("source-failed", True))
            req = b.return_value.open.call_args.args[0]
            self.assertEqual(json.loads(req.data), {"text": ops.MESSAGES["source-failed"]})
            self.assertNotIn(b"Secret", req.data)

    def test_rejects_other_hosts_without_network(self):
        with patch.dict("os.environ", {"SOCIAL_MEDIA_AGENT_SLACK_WEBHOOK_URL":
                                       "https://example.org/services/A/B/Secret"}), patch.object(ops, "build_opener") as b:
            with redirect_stderr(StringIO()) as out:
                self.assertFalse(ops.notify("source-failed", True))
            self.assertNotIn("Secret", out.getvalue())
            b.assert_not_called()


if __name__ == "__main__":
    unittest.main()
