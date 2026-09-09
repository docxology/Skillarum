# Reproducibility, limitations, and future work {#sec:reproducibility}

The default path is offline after acquisition caches exist. Deterministic
generation requires no credentials or model daemon. Ollama and OpenAI checks
are opt-in. Every run can be inspected through its state file, stage payloads,
cache envelopes, provider trace, skill manifest, and discovery index.

The project distinguishes two reproducibility questions. Conditional
repeatability asks whether deterministic rendering gives the same artifact
when the prepared corpus, configuration, and pipeline version are fixed; the
formal model and idempotency tests address that question. Live-run
reproduction asks whether a later acquisition observes the same website and
provider responses; it is not guaranteed because pages, redirects, robots
policies, network conditions, and models can change. The research package
therefore preserves inputs, hashes, retrieval times, and execution metadata so
differences can be diagnosed rather than hidden. This follows reproducible
computational-research practice [@sandve-reproducibility] and treats the FAIR
principles as a stewardship goal [@fair-guiding-principles], without claiming
permanent archival preservation or formal FAIR certification.

Reproduction sequence:

```bash
uv sync --extra dev --extra research
uv run --extra dev --extra research pytest tests/ --cov=src --cov-fail-under=90
uv run python -m skillarum run --profile data/sources/math4wisdom.yaml
uv run python -m skillarum run --profile data/sources/active_inference_institute.yaml
uv run --extra research python -m skillarum research build --output-dir output --json
```

The build command validates inputs, aggregates completed observations, generates
figures, hydrates manuscript tokens, and writes an ordered receipt. It does not
produce PDF/HTML or publish externally. The sibling template renderer must then
render this lifecycle-qualified project; final publication validation requires
the rendered files in its hash inventory. See the operational release checklist
for exact commands.

Run-dependent prose, reporting parameters, configuration tables, and figure
captions are substituted from the evaluation report, executable contracts,
profile declarations, archive receipts, and figure registry. A binding receipt
records each value's source family and the hashes of its inputs and rendered
sections. Validation independently reconstructs the text: editing a value and
recomputing the receipt hash cannot make it agree with unchanged evidence.
Authored metadata and mathematical definitions remain explicit declarations;
they are not estimated results. The numeric-prose guard detects undeclared
numerals outside defined syntax exemptions, but cannot establish the meaning
or truth of a sentence.

The ordered build holds an interprocess lock and compares input hashes before
and after generation. A changed input prevents a successful receipt. Individual
file replacements are atomic; the complete research directory is not published
as one transaction. A final validation must therefore follow the last output
writer, including the renderer and visual-review receipts.

The current fetcher sees server-rendered HTML
only. It does not execute JavaScript or browser automation. The {{CONFIGURED_PROFILE_COUNT}} configured sites are
case studies, not a representative web sample. Human-review agreement is
pending until two independent rating files are supplied. Provider output is
nondeterministic and should not be treated as a gold standard. Source hashes
prove what was retrieved, not that a page’s claims are true.

Future work can add a browser-backed fetcher only if it preserves the existing
origin, robots, request, response, redirect, provenance, and trust-boundary
contracts.
