# cover/

Publication cover artwork for the Skillarum manuscript.

## Contents

| File | Description |
| --- | --- |
| `skillarum_cover.png` | 1024x1536 RGB PNG editorial cover illustration |

## Key facts

- The image is conceptual artwork. It contains no text, no measured data, and
  no depiction of a real crawl or a real generated skill.
- Its provenance, SHA-256, dimensions, caption, alt text, and limitations are
  recorded in [`../data/cover.yaml`](../data/cover.yaml) — not here.
- [`../docs/manuscript/config.yaml`](../docs/manuscript/config.yaml) points the
  parent template renderer at this file via `paper.cover.image`.

## Common commands

Run from the project root.

### Confirm the tracked hash still matches the file

```bash
shasum -a 256 cover/skillarum_cover.png
grep sha256 data/cover.yaml
```

### Re-hash the cover into the publication manifest

```bash
uv run python -m skillarum research publication \
  --output-dir output --project-root . --json
```

## More information

See [AGENTS.md](AGENTS.md) for the rules that govern replacing this asset, and
[`../docs/manuscript/README.md`](../docs/manuscript/README.md) for how the
manuscript consumes it.
