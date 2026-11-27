# Three reporting examples

The orchestrator sits on both sides of collection: it dispatches the collectors, then decides what the available data support. A collector's success or failure is operational information. A source-specific count answers a question about one source. A combined count answers a different question about the whole planned sample.

All examples below are fictional. Commands run from the repository root.

## 1. One source: no reason to wait

**Question:** How often does this social export mention community support? The operator chooses only the JSONL collector. RSS, Bluesky, and YouTube aren't called.

```sh
python3 -m social_media_agent.orchestrator --plan examples/single-source-demo.json --week 2026-11-23
```

The JSONL collector reads four rows. One is an exact duplicate. The report includes three distinct items and **one support-resource mention**. It is a count about the social export alone, not about all available channels.

## 2. Two sources: wait only for the combined total

**Question:** How many distinct items across the social export and the publisher feed mention community support?

```sh
python3 -m social_media_agent.orchestrator --plan examples/orchestrator-demo.json --week 2026-11-23
```

The RSS fixture repeats one of the posts in the social export and contains one new post. After filtering and deduplication the combined report has four distinct items, two duplicate rows, and **two support-resource mentions**. You can't obtain the distinct-item total by adding the two source totals if they share identifiers. Different IDs on different platforms aren't automatically recognized as cross-posts.

## 3. One source fails: report the failure, not a lower total

**Question:** Can we compute that same two-source number if the publisher feed is unavailable?

```sh
python3 -m social_media_agent.orchestrator --plan examples/failed-source-demo.json --week 2026-11-23
```

Exit code 1 is expected. The JSON says the social export was `ok` and the publisher feed `failed`. It shows no combined counts. The publisher feed is **missing, not zero**. You can run Example 1 separately to answer a narrower question; don't compare its number to the prior two-source total as though coverage were unchanged.

## Current behavior and next design choice

The CLI returns all receipts at the end of a run. It already supports separate one-source runs; it doesn't yet emit incremental progress or successful-source aggregates automatically when a multi-source run fails. For scheduled operations I'd add per-collector status as each source finishes, keep source-only reports distinctly labeled, and gate only the combined result on all required sources. An optional source should not hold up an independently defined report. Review overlapping live outputs before releasing them so withheld counts can't be reconstructed by subtraction.
