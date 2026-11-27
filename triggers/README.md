# Triggers

| Trigger | Entry point | Enabled automatically? |
| --- | --- | --- |
| Manual | `python3 -m social_media_agent.orchestrator --plan … --week …` | No. Live requires manual execution and approved sources. |
| Local clock | `python3 triggers/offline_timer.py` | No. Optional scheduler entry point for the bundled offline example only. |
| CI / test harness | Same CLI with `--trigger ci` | No hosted runner is configured. Offline only. |

The timer computes the last complete UTC week from the clock. The sample fixture only contains November 23–29, 2026, so use the fixed-week manual demo to see nonzero sample counts. A local scheduler can invoke the timer if desired; do not interpret an empty result from this fixture as feed availability. The timer is not installed on any server.

A webhook and n8n port are possible later. Do not expose a raw-URL or arbitrary-shell interface or schedule live collection without a separate approved deployment.
