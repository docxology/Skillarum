# skillarum package

The whole implementation: a flat set of Python modules, no subpackages.

## Quick start

```python
from skillarum import SourceProfile, PreparedCorpus, SkillDraft
from skillarum.config import load_profile

profile = load_profile("data/sources/math4wisdom.yaml")
print(profile.id, [target.id for target in profile.targets])
```

From a shell, at the project root:

```bash
uv run python -m skillarum run \
  --profile data/sources/math4wisdom.yaml --backend deterministic
```

## Module map

| Group | Modules |
| --- | --- |
| Entry points | `__init__.py`, `__main__.py`, `cli.py` |
| Contracts | `models.py`, `config.py`, `urls.py`, `utils.py`, `exit_codes.py` |
| Pipeline stages | `crawler.py`, `prepare.py`, `generators.py`, `render.py`, `pipeline.py` |
| Alternative source | `repo_source.py` |
| Website inventory | `site_snapshot.py` |
| Package lifecycle | `install.py`, `packdiff.py`, `signature.py`, `runtimes.py`, `quarantine.py` |
| Safety | `policies.py`, `redaction.py` |
| Surfaces | `mcp_server.py`, `serve.py` |
| Research layer | `research.py`, `statistics.py`, `manuscript.py`, `figures.py`, `publication.py`, `evals.py` |

## Key features

- Five inspectable stages: `acquire → prepare → process → parse → render`.
- The deterministic generator works offline, with no credentials, daemon, or
  downloaded model. OpenAI, Ollama, and external-command backends are optional.
- Scraped HTML is untrusted reference data. Generated code is never executed.
- Every rendered package carries page, corpus, generator, run, and artifact
  identities so staleness and tampering are detectable.

## Exit codes

`exit_codes.py` is the public contract: `0` success, `1` validation or
verification failure, `2` usage or configuration error, `3` environment or
network failure.

## Common commands

```bash
uv run python -m skillarum doctor --profile data/sources/math4wisdom.yaml --no-network --json
uv run python -m skillarum validate output/skills/Math4Wisdom/Three-Minds/SKILL.md
uv run python -m skillarum index --skills-dir output/skills
uv run pytest tests/ --cov=src --cov-fail-under=90
```

## More information

See [AGENTS.md](AGENTS.md) for per-module responsibilities and the layer
contract, and [`../../docs/architecture.md`](../../docs/architecture.md) for
stage and trust boundaries.

`publication.py` coordinates the offline `research build` command and its receipt.

The research layer separates numerical methods in `statistics.py`, evidence
collection and ledgers in `research.py`, manuscript binding in `manuscript.py`,
and ordered construction in `publication.py`.
