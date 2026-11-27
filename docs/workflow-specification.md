# Workflow specification

## Purpose

Run one shared intake workflow over independent collector agents. Start with repeatable offline examples, then allow a human owner to approve manual runs against selected organizational publisher feeds. The three grant pilots share orchestration and review, not person-level data.

## Interfaces

The trigger supplies a run plan and a UTC Monday. The run plan includes mode, vocabulary path, threshold, and named sources with kind and target. Treat it as trusted operator configuration, not data supplied by the feeds. Keep approved live plans local. Target validation prevents passing arbitrary URLs to the live collectors. No commands, destinations or instructions are accepted from input text.

An agent's output is a stream of three string fields. Source limits and required fields are checked before pooling. Identifiers are used only in memory for exact-ID deduplication. This does not establish equivalence of different IDs across platforms. Use versioned approved vocabulary and compare outputs only at the same grain, sampling plan, period, and release threshold. The output JSON contains a vocabulary digest and a per-agent receipt; an offline run includes fixture row counts.

## Example and expected evidence

```sh
python3 -m social_media_agent.orchestrator --plan examples/orchestrator-demo.json --week 2026-11-23
```

Expect both collector receipts to pass, four distinct inputs, two duplicate rows (one repeated within the JSONL file and one shared by both sources), and three themes with two mentions each. No names, URLs, excerpts, or record IDs are emitted. In the failure fixture, one source returns HTTP 429 and the entire aggregate is withheld even though the other source was healthy.

## Source constraints

- Use official platform endpoints only. Respect access denials and do not attempt bypasses.
- One small latest-results sample cannot establish complete historical coverage. It is not a signal of prevalence or clinical conditions.
- Live reporting uses a minimum count floor of 5; require human release review, avoid repeated overlapping runs that reveal withheld counts, and do not put publisher handles or individual data in theme names.
- No consumer accounts, profile enrichment, comments, private groups, demographics inference, geographic or personal tracking, raw egress, or automated actions.
- No live scheduling or account access is configured. Reddit, Facebook and X remain reviewed references until an authorized connector is designed and tested.

## Design precedents

[Hey Siri, Ask Agent](https://www.bearbrown.co/agents/hey-siri-ask-agent-workflow) gives a clear trigger to agent to response boundary. The Hacker News AI Tracker shows manual/scheduled triggers and call-another-workflow separation. The two-feed RSS workflow demonstrates iterating over a configured source list; the YouTube and Reddit workflows illustrate source-specific adapters. See the [source audit](source-inventory.md) for design decisions and exclusions.
