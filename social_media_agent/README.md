# Collector

The offline adapter accepts one JSON record per line with string fields id, created_at (ISO 8601 with offset), and text. Test only with fictional or explicitly approved data. External connectors should transform to the same three fields only in the approved processing environment; the collector does not persist source data.

Live Bluesky mode uses only the [official publisher feed](https://docs.bsky.app/docs/api/app-bsky-feed-get-author-feed), never arbitrary passed-in URLs or full-network search. Copy the fictional theme configuration to a local ignored filename such as `settings.local.json`, replace the themes with approved broad vocabulary, and add approved organization handles under `publishers`. Use at most five publishers and one or two pages per publisher. The flag attests approval; it cannot verify an organization's identity or terms of use by itself.

```sh
python3 -m social_media_agent --config settings.local.json \
  --week YYYY-MM-DD --bluesky --confirm-approved-publishers
```

Supply a completed UTC week starting Monday. This is a bounded sample of recent pages, not retrieval of a complete historical week. Omit the report when source coverage is unsuitable; absence of a bucket may mean suppression, no matches, or posts outside the sample. Stop on access denial, quota limits, or malformed responses. Never switch to browser scraping to work around an API refusal.

For the shared multi-source path, use the [orchestrator](../docs/workflow-specification.md). This page describes the original single-source CLI.
