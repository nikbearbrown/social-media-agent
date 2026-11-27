# Operations alerts

The run-plan validator is a control, not a notification system. There are two paths:

| What happened | Who detects it | What gets reported |
| --- | --- | --- |
| Invalid or unapproved plan | Orchestrator before collector dispatch | “Invalid or unapproved run plan. No collectors ran.” |
| Collector error | Orchestrator after dispatch | Names failed source position and adapter, reason code and number of attempts. The detailed receipt is available locally. |
| Process did not start, crashed, or got stuck | Independent watchdog checks the heartbeat | Missing, unreadable, or overdue heartbeat. The operator checks the scheduler or stuck process. |
| Slack delivery itself fails | Sender or watchdog | Generic local diagnostic. No repeated retry inside the collector, no secret printed. |

## Check it without Slack

From the repo root:

```sh
mkdir -p runs
python3 -m social_media_agent.orchestrator --plan examples/orchestrator-demo.json \
  --week 2026-11-23 --status-file runs/demo-status.json
python3 -m social_media_agent.ops --status-file runs/demo-status.json \
  --max-age-minutes 90
```

The watchdog should print `current`. Point it at a nonexistent status file to test the missing case; the watchdog exits 1. To test a collector failure explicitly, substitute `examples/failed-source-demo.json` in the first command (exit 1 expected). A recent failed run is not a missed run; it gets its own alert.

## Enable Slack only after selecting the operations channel

Configure an [incoming webhook](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/) for a designated private operations channel. Supply its URL in the runtime environment as `SOCIAL_MEDIA_AGENT_SLACK_WEBHOOK_URL`, then add `--notify-slack` to the orchestrator and watchdog commands. The webhook is the **notification credential**, not a collector credential. Never put it in Git, a run plan, scheduler command arguments, or logs. Alerts use fixed messages and sanitized source failure codes; no posts, IDs, links to sources, raw errors or report data are sent.

Schedule the watchdog independently of the collector, preferably from a monitor that can still run if the collector host fails and can read the status file or its replicated equivalent. Use a separate heartbeat file for each planned job and one watchdog instance per file. Set max age to the schedule interval plus a grace period, for example 26 hours for a daily job. Start the watchdog when the first heartbeat is due; missing files otherwise alert immediately. The watchdog alerts once for an unchanged overdue state after successful delivery. If the host and watcher are on the same machine and both go offline, neither can send. This repo does not install a scheduler, deploy a monitor, or send to a configured channel by default.

Slack is the first adapter. Discord or email can be added to the same notification boundary later; neither is implemented.
