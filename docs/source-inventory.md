# Social intake skill and agent inventory

## BearBrown.co

Searched the [Agents](https://www.bearbrown.co/agents), [Skills](https://www.bearbrown.co/skills) and audited-component snapshots in the existing site checkout at a07f454a7e8c800c5684cdf8f06f2f5b79e3c487. The agent index had 1,877 listings, skills 71, and the audit index 1,646. Examined likely matches with platform and collection keywords, then inspected selected templates' node graphs without running them. The in-house skills list did not have a dedicated social collector. Its [research skill](https://www.bearbrown.co/skills/research) and [agent loop patterns](https://www.bearbrown.co/agents/loops) inform source notes and stop conditions.

| Catalog candidate | Useful pattern | Disposition |
| --- | --- | --- |
| [Read items from an RSS feed](https://www.bearbrown.co/agents/n8n/read-items-from-an-rss-feed) and [YouTube RSS feed buddy](https://www.bearbrown.co/agents/n8n/advanced-youtube-rss-feed-buddy-for-your-favorite-channels) | Known publisher feed, bounded batches | Add a feed adapter only after an approved publisher and collection terms are agreed. |
| [Recent posts from a Reddit community](https://www.bearbrown.co/agents/n8n/retrieves-recent-posts-from-specific-reddit-community-subreddit), [Reddit search](https://www.bearbrown.co/agents/n8n/search-reddit-and-edit-open-ai-and-open-ai) and [Reddit business-opportunity analysis](https://www.bearbrown.co/agents/n8n/analyze-reddit-posts-with-ai-to-identify-business-opportunities) | API acquisition, field selection, fetch separate from interpretation | Reference only. Remove LLM, spreadsheet and commentary sinks. Any future adapter needs authorized API access and source-specific terms. |
| [X mentions](https://www.bearbrown.co/agents/n8n/scrape-twitter-for-mentions-of-company) | Explicit time window and selected fields | Reference only. Do not copy its Slack forwarding; use authorized official access if approved later. |
| [Facebook Page comments](https://www.bearbrown.co/agents/n8n/get-comments-from-facebook-page) | Separate fetch and normalization | Reference only. No comment collection in this MVP. |
| [YouTube comment sentiment](https://www.bearbrown.co/agents/n8n/youtube-comment-sentiment-analyzer) | Track fetch status before producing outputs | Reference only. No sentiment scoring, spreadsheet sink or comment collection. |
| [Generic webpage scraper agent](https://www.bearbrown.co/agents/n8n/ai-agent-that-can-scrape-webpages) | Separate acquisition tool from reviewer | Do not use model-selected arbitrary URLs, hosted scraping tools or unbounded browser workflows. |
| Bluesky posting and welcome-message templates | Not collection | Excluded; this project is read-only. |

## Hetzner corpus

Queried the local Gitskills metadata snapshot (2026-08-18; 282,200 repository rows and 3,797,117 artifact rows) for paths containing Reddit, Mastodon, Bluesky, social listening or monitoring, YouTube comments, X/Twitter scraping, and RSS. Cross-checked names from the BearBrown audited catalog. Metadata is a discovery lead, not a validation, licensing determination, or deployment recommendation.

- [ScrapeCreators social media research skills](https://github.com/ScrapeCreators/social-media-research-skills): indexed a social-listening brief. The sample-to-brief split is relevant; hosted service and access terms not vetted.
- [Agentic Awesome Skills](https://github.com/sickn33/agentic-awesome-skills): indexed three Reddit-related skill paths; general source-specific candidates, not approved adapters.
- [Awesome Copilot](https://github.com/github/awesome-copilot): indexed an X/Twitter scraper path. Reference only; not an approved access method.
- [last30days](https://github.com/mvanhorn/last30days-skill) and [SocialClaw](https://github.com/ndesv21/socialclaw): adjacent discovery/orchestration candidates from the BearBrown audit catalog, not wired into the MVP.

No third-party skill, scraped data, credentials, or workflow was copied or installed. Catalog links preserve provenance. The new skill and role instructions distill useful patterns using a deterministic collector and an independent human review step.

## Orchestrator follow-up

The second pass screened 66 collection-related title candidates across the 1,877-entry agent catalog, including false matches such as publishers or video editing workflows. In addition to the sources above, these node graphs were inspected in the local catalog:

| Workflow | Useful design choice | Decision |
| --- | --- | --- |
| [Hey Siri, Ask Agent](https://www.bearbrown.co/agents/hey-siri-ask-agent-workflow) | Explicit trigger and separate response node | Split triggers from dispatch and output; no webhook or hosted model port in this version. |
| [Hacker News AI Tracker](https://www.bearbrown.co/agents/n8n/hacker-news-ai-tracker) | Scheduled/manual trigger, calls a separate feed workflow, merges results | Strongest orchestration precedent; use named collector calls and one gated merge. |
| [Read two RSS feeds](https://www.bearbrown.co/agents/n8n/read-rss-feed-from-two-different-sources) | Iterate independent feed inputs | Implemented a local RSS/Atom agent. |
| [Only new RSS](https://www.bearbrown.co/agents/n8n/get-only-new-rss-with-photo) | Scheduled intake and duplicate filtering | Deduplicate exact IDs inside a bounded run; don't fetch or store images. |
| [YouTube searcher](https://www.bearbrown.co/agents/n8n/youtube-searcher) | Explicit invocation and separate record selection | Implemented a narrower [official channel feed](https://developers.google.com/youtube/data/guides/push_notifications) agent, no database or full search. |
| Reddit, X and Facebook workflows above | Separate platform acquisition from processing | Diagnostic references only; approval and adapter tests required before use. |
