# Skillarum operations and quality gates

This document is the short operational runbook for repeatable local runs. The
longer data contracts are in [`architecture.md`](architecture.md), and the
research reporting policy is in [`evaluation.md`](evaluation.md).

## Provider and context policy

`deterministic` is the default and has no model-provider cost. `auto` is
explicit opt-in and resolves to OpenAI when `OPENAI_API_KEY` is available,
then Ollama, then deterministic generation. An explicit `--fallback-backend`
creates the same resilient chain for a selected primary provider. CLI values
replace profile generation defaults only when the CLI flag is supplied.

Provider attempts are bounded to two by default. Transport errors, timeouts,
HTTP 408/429/5xx, and transient Ollama daemon failures are retryable; malformed
JSON, invalid output sections, unsafe output, and other deterministic contract
failures are not retried. Every attempt, retry, fallback, sanitized diagnostic,
selected backend, and model name is retained in the run and skill manifests.
Credentials and authorization headers never enter those artifacts.

Fallback is intentionally narrower than a blanket exception handler: typed
provider failures, transport failures, HTTP failures, and output-contract
failures may continue through the configured chain, while ordinary programming
errors such as assertion, type, attribute, key, and unrelated runtime errors
remain visible to the caller.

Ollama uses the official non-streaming `/api/chat` contract with structured JSON
output. `--ollama-context` controls `num_ctx`, while
`--ollama-max-prompt-chars` controls the bounded source context sent to the
model. Prompt truncation is an explicit warning in the draft metadata and
provenance. Local inference latency and token counters, when returned by the
daemon, are observations rather than claims about model quality. Retries can
multiply provider calls, so production runs should inspect `generation_trace`
before comparing latency or cost.

Verify a local installation without making a generation request:

```bash
ollama pull llama3.2
uv run python -m skillarum doctor \
  --profile data/sources/math4wisdom.yaml --ollama-model llama3.2 --json
```

The opt-in integration test requires a real daemon and model:

```bash
SKILLARUM_RUN_OLLAMA=1 uv run pytest tests/test_ollama_integration.py -q
```

## Cache and idempotency gates

`output/.cache` is disposable derived state. Cache envelopes are accepted only
when schema/version, profile fingerprint, target fingerprint, corpus hash,
generator fingerprint, generation configuration, and payload hash all agree.
The `cache inspect` command reports valid, stale, and corrupt entries without
mutating them:

```bash
uv run python -m skillarum cache inspect --output-dir output \
  --profile data/sources/math4wisdom.yaml --json
```

Stale entries after a pipeline or cache contract bump are expected and should
be regenerated. Corrupt entries indicate interrupted or tampered state and
must be regenerated before publication. Per-target locks serialize concurrent
acquisition and generation; package publication uses a staged directory and
a recoverable two-rename replacement (with a brief absence window). The discovery index is rebuilt only from complete,
hash-valid packages. Symlinked cache entries are treated as corrupt rather than
read through to another filesystem location.

## Publication quality gates

Run the gates in this order after a live or offline artifact refresh:

```bash
uv run python -m skillarum validate --json output/skills/*/*/SKILL.md
uv run python -m skillarum index --skills-dir output/skills --json
uv run python -m skillarum research validate --json
uv run python -m skillarum research publication --output-dir output \
  --project-root . --require-rendered --json
```

The v2 package validator requires portable semantic, procedural, verification,
and source-boundary sections, plus page-level provenance, trust metadata,
request events, generation traces, and artifact hashes. Schema 1 packages can
still be read for migration and historical validation, but new rendering emits
schema 2 only.

The publication manifest is an explicit allowlist: it includes complete skills,
figures, rendered manuscript content, the current evaluation report selected by
`evaluation-manifest.json`, and final PDF/HTML outputs. It excludes private
cache/run state, stale evaluation snapshots, local `AGENTS.md`/`README.md`
guidance, credentials, symlinks, and the manifest itself. It materializes the
cover and scholarly metadata when a project root is supplied, records PDF/HTML
render counts, and can fail closed when configured formats are absent. Rerun
publication validation after parent-template rendering so the final output
surface is covered.
The canonical evaluation report must be `evaluation/<report_id>.json`, the
summary must be `reports/evaluation-summary.json`, and the two JSON files must
be byte-identical with valid SHA-256 references. Older absolute or
`output/...` references remain readable only when they resolve to those same
canonical locations.

## Evidence discipline

Fixture-server observations establish implementation behavior and must remain
labelled `fixture`; public-site observations are snapshots labelled `live`.
Counts, rates, medians, ranges, missingness, exact small-sample intervals, and
seeded bootstrap intervals are descriptive. No significance or general web
population claim is justified by the two example domains. Human-review output
is publishable only when two raters independently score overlapping cases and
any disagreements are resolved by an auditable adjudication record.

## Exit-code contract

Every `skillarum` command exits with one of the stable codes defined in
`src/skillarum/exit_codes.py`:

| Code | Meaning |
| ---- | ------- |
| `0` | Success (ok verdicts, including advisory warnings). |
| `1` | Validation/verification failure, or a missing/invalid requested input artifact (e.g. missing profile or SKILL.md). |
| `2` | Usage/config error: argparse rejects the command line (unknown flag, missing required argument). |
| `3` | Environment/network failure: a configured endpoint (e.g. Ollama) could not be reached, or an HTTP request failed. |

Scripts may branch on these codes. Do not introduce ad-hoc codes; the
subprocess-level contract is enforced by `tests/test_exit_codes.py`.
