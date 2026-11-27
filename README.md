# Social Media Agent

A shared, read-only collector and coding-agent skill for Humanitarians AI's lexicon pilots. Start with fictional examples. When a project owner has approved a source and its use, collect a bounded sample of organizational public posts through its official API. Report broad vocabulary mentions for human review, not facts about individual people or health events.

## What's here

- [Python collector](social_media_agent/README.md): local JSONL and an official Bluesky publisher-feed adapter; no credentials or dependencies for the demo.
- [Coding-agent skill](skills/social-media-intake/SKILL.md): how to approve, collect, validate and report a sample.
- [Agent roles](agents/README.md): intake operator and vocabulary reviewer, with no posting, messaging or model calls in the collector.
- [Workflow and skill catalog](docs/source-inventory.md): what was found on BearBrown.co and Hetzner, what to reuse, and what stays out.
- [Grant pilot notes](docs/grant-pilots.md): one shared layer for I3-03, I3-04 and I3-08, with separate evaluation questions.

## Try it

Python 3.10 or later. From the repo:

```sh
python3 -m social_media_agent --config examples/fictional-themes.json \
  --week 2026-11-23 --fixture examples/fictional-posts.jsonl --min-count 1
python3 -m unittest discover -s tests -v
```

The demo returns three unique posts and one duplicate, with two care-access mentions, two public-information mentions and one support-resource mention. Themes can overlap. The threshold of 1 is for this fictional fixture only.

## Scope and release status

- Start with approved public organizational publishers. No firehose, arbitrary URL scraping, account discovery, geolocation, personal profiling or private sources. No post text, handles, IDs, or quotes are emitted by the live mode. Do not infer health status, demographic traits or incident counts from mentions.
- Do not mix social posts with clinical or case records. Social mentions are candidate public-language evidence only. They are not diagnoses, cases, prevalence estimates or automatic alerts.
- Live collection is off until a responsible owner approves the platform terms, publishers, purpose, retention and release. No collection job is deployed. Reddit, YouTube, Facebook and X are references, not installed adapters or claims of current access.
- Treat suppression as a minimum filter, not a privacy guarantee. Do not release overlapping runs that let readers infer suppressed counts by subtraction. Do not publish results or texts without review.
