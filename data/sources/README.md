# data/sources/

Declarative source profiles. One YAML file describes a whole site: where to
crawl, how to extract, which generator to use, and which named targets to
render.

## Contents

| File | Profile `id` | Area | Targets |
| --- | --- | --- | --- |
| `math4wisdom.yaml` | `math4wisdom` | `Math4Wisdom` | `three-minds`, `three-minds-exposition`, `minds-research` |
| `math4wisdom_research.yaml` | `math4wisdom-research` | `Math4Wisdom` | 528 `research-*` targets, one per page on `Research/Index` (generated) |
| `active_inference_institute.yaml` | `active-inference-institute` | `Active-Inference-Institute` | `institute-overview`, `institute-foundations`, `institute-programs`, `institute-projects` |

## Quick start

From the project root:

```bash
uv run python -m skillarum run \
  --profile data/sources/math4wisdom.yaml \
  --backend deterministic
```

Render a single target instead of the whole profile:

```bash
uv run python -m skillarum run \
  --profile data/sources/math4wisdom.yaml \
  --target three-minds --backend deterministic
```

## Key fields

- `id`, `name`, `base_url`, `area` — identity and the output directory under
  `output/skills/<area>/`.
- `crawl` — `respect_robots`, `same_origin_only`, `follow_links`, `max_pages`,
  `max_requests`, `max_depth`, `request_timeout_seconds`, `min_delay_seconds`,
  `max_response_bytes`, and a `retry` block.
- `extraction` — `main_selector`, `max_chars_per_page`, `remove_selectors`,
  and the opt-in `preserve_blocks` and `title_separator`.
- `generation` — `backend` plus provider settings and a `retry` block.
  Credentials are never stored here; they come from the environment.
- `targets[]` — `id`, `name`, the `urls` list resolved against `base_url`, and
  an optional authored `description` for the rendered frontmatter.

## Regenerating the Research profile

`math4wisdom_research.yaml` is generated from the live index; do not edit its
target list by hand:

```bash
uv run python -m skillarum profile-from-index \
  --profile data/sources/math4wisdom.yaml \
  --index-url https://www.math4wisdom.com/wiki/Research/Index \
  --prefix /wiki/Research/ --output data/sources/math4wisdom_research.yaml \
  --profile-id math4wisdom-research --id-prefix research \
  --name-prefix Research- --title-separator " | "
```

## Common commands

### Check a profile without touching the network

```bash
uv run python -m skillarum doctor \
  --profile data/sources/math4wisdom.yaml --no-network --json
```

### Inspect cache identity for a profile

```bash
uv run python -m skillarum cache inspect \
  --profile data/sources/math4wisdom.yaml --json
```

## More information

See [AGENTS.md](AGENTS.md) for the full field semantics, safety defaults, and
the rules for adding a profile.
