# Social Media Agent

A read-only **orchestrator** for Humanitarians AI’s lexicon pilots. Give it a run plan and a week. It calls the configured collector agents, checks each response, combines duplicate items, and returns a vocabulary report for human review. If any source fails, it withholds the report instead of treating that source as having zero results.

## Start here

- [Three runnable reporting examples](examples/reporting.md): a single-source count, a combined count, and a missing-feed case.
- [Agent workflow and Mermaid diagram](agents/README.md): triggers, collector calls, the review gate and failure paths.
- [Workflow specification](docs/workflow-specification.md): inputs, outputs, limits and what is tested.
- [Operational alerts and missed-run watchdog](docs/operations.md): opt-in Slack and local status files.
- [Triggers](triggers/README.md): manual, optional offline timer, and test entry points.
- [Source inventory](docs/source-inventory.md): BearBrown.co and Hetzner candidates, and what we reused.
- [Grant pilots](docs/grant-pilots.md): separate applications of the workflow for I3-03, I3-04 and I3-08.
- [Operator skill](skills/social-media-intake/SKILL.md): optional instructions for Codex or Claude Code, not the runtime.

## Run the two-agent demo

Python 3.10 or later; no dependencies or credentials.

```sh
python3 -m social_media_agent.orchestrator \
  --plan examples/orchestrator-demo.json --week 2026-11-23
python3 -m unittest discover -s tests -v
```

The orchestrator calls the JSONL agent and the RSS agent in one run. The demo returns four distinct fictional items, two duplicates and three themes with two mentions each. The result is marked `review-required`.

The Bluesky publisher and YouTube channel agents use official feeds. Both are implemented and fixture-tested, but live collection is not running. A live plan must be manually approved, restricted to organizational publishers and kept out of the repo. Social posts are public-language evidence, not case records, diagnoses or prevalence estimates. No raw post text, handles, IDs or quotes are included in live reports.
