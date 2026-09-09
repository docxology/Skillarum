# data/sources/ agent guidance

## Overview

A source profile is the single declarative input that drives a Skillarum run.
It names a site, the safety limits under which its pages may be acquired, how
HTML is reduced to text, which generator backend to use, and which named
targets are rendered as portable skill packages. Profiles are loaded and
validated by [`../../src/skillarum/config.py`](../../src/skillarum/config.py)
into the dataclasses in
[`../../src/skillarum/models.py`](../../src/skillarum/models.py).

## File organization

| File | Purpose |
| --- | --- |
| `math4wisdom.yaml` | Math 4 Wisdom wiki profile, three targets |
| `active_inference_institute.yaml` | Active Inference Institute profile, four targets |
| `README.md` | Quick reference |
| `AGENTS.md` | This file |

## Profile schema

### Top level

| Key | Required | Meaning |
| --- | --- | --- |
| `id` | yes | Stable profile identifier; matched by `cases.yaml` `profile_id` |
| `name` | no | Human label; defaults to `id` |
| `base_url` | no | Origin and path prefix that target `urls` resolve against |
| `area` | no | Output namespace: rendered skills land in `output/skills/<area>/` |
| `crawl` | no | Crawl safety limits |
| `extraction` | no | HTML reduction rules |
| `generation` | no | Provider defaults |
| `targets` | yes | At least one target; an empty list is a load error |

### `crawl`

Defaults come from `CrawlConfig`: `respect_robots: true`,
`same_origin_only: true`, `allow_private_hosts: false`, `follow_links: false`,
`max_pages: 50`, `max_requests: 100`, `max_depth: 1`, `max_redirects: 10`,
`request_timeout_seconds: 20.0`, `min_delay_seconds: 0.0`,
`max_response_bytes: 2000000`, `robots_cache_ttl_seconds: 3600.0`, a
`Skillarum/0.2` user agent, and a `retry` block.

`max_pages` counts accepted, de-duplicated pages. `max_requests` counts every
page, redirect, robots, and retry attempt — the two limits are deliberately
separate so a redirect storm cannot hide behind a page budget.

Both bundled profiles set `follow_links: false` and `max_depth: 0`: they
acquire exactly the enumerated target URLs and never spider.

### `extraction`

`main_selector` (CSS selector for the content root), `max_chars_per_page`
(default `40000`), and `remove_selectors` (defaults to `script`, `style`,
`nav`, `header`, `footer`, `aside`, `form`). `math4wisdom.yaml` selects
`#wikitext`; `active_inference_institute.yaml` selects `main`.

### `generation`

`backend` must be one of `deterministic`, `openai`, `ollama`, `command`, or
`auto`; loading fails otherwise. Other keys: `fallback_backend`, `model`,
`ollama_model`, `ollama_url`, `ollama_timeout_seconds`, `ollama_num_ctx`,
`ollama_max_prompt_chars`, and a `retry` block. Both bundled profiles declare
`deterministic`.

CLI arguments override profile values only when supplied.

### `targets[]`

`id` is required. `name` defaults to `id` and must not be empty — it is the
authoritative human-readable package directory name. Page selection accepts
`urls` (alias `start_urls`), `include_prefixes` (alias `prefixes`),
`include_patterns`, `exclude_patterns`, and an optional positive `max_pages`.

## Usage examples

Run from the project root.

```bash
# Whole profile, offline generator
uv run python -m skillarum run \
  --profile data/sources/math4wisdom.yaml --backend deterministic

# One target
uv run python -m skillarum run \
  --profile data/sources/active_inference_institute.yaml \
  --target institute-programs --backend deterministic

# Re-fetch source pages instead of reusing the acquisition bundle
uv run python -m skillarum run \
  --profile data/sources/math4wisdom.yaml --refresh

# Local-only health check
uv run python -m skillarum doctor \
  --profile data/sources/math4wisdom.yaml --no-network --json
```

## Rules

- ✅ Keep `respect_robots: true` and `same_origin_only: true`.
- ✅ Keep `allow_private_hosts` unset or `false` for any public profile; the
  crawler re-resolves hostnames immediately before acquisition and rejects
  private or reserved answers.
- ✅ Give a target a stable `id`; `data/evaluation/cases.yaml` and cache
  identities are keyed on it.
- ✅ Keep the `area` a human-readable namespace. The two canonical areas are
  `Math4Wisdom` and `Active-Inference-Institute`.
- ❌ Never put an API key, token, or `Authorization` header in a profile.
  Credentials are environment-only (`OPENAI_API_KEY`, `OLLAMA_HOST`,
  `OLLAMA_MODEL`).
- ❌ Never write crawl results or cache state here. Those belong under
  `output/`.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `profile.id is required` | Missing top-level `id` |
| `profile.targets must contain at least one target` | Empty or absent `targets` |
| `target <id> has an empty name` | `name:` present but blank |
| Unknown backend error on load | `generation.backend` outside the five allowed values |
| A run acquires fewer pages than listed | `crawl.max_pages` or a target `max_pages` capped it |

## See also

- [`README.md`](README.md) — quick reference and the bundled-profile table
- [`../AGENTS.md`](../AGENTS.md) — the data tree as a whole
- [`../evaluation/AGENTS.md`](../evaluation/AGENTS.md) — how `profile_id`/`target_id` are consumed
- [`../../docs/architecture.md`](../../docs/architecture.md) — stage boundaries
- [`../../docs/operations.md`](../../docs/operations.md) — cache invalidation and provider budgeting
- [`../../docs/repo-source.md`](../../docs/repo-source.md) — the alternative repository source type
