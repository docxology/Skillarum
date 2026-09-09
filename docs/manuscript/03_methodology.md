# Methodology and system architecture {#sec:methodology}

## Declared acquisition design

Profiles declare {{CONFIGURED_TARGET_COUNT}} target bundles across
{{CONFIGURED_PROFILE_COUNT}} source areas. The following table is generated
from the current profile files. Its limits describe configured upper bounds;
they are not counts of retrieved or available website pages. Target bundles
may select overlapping source pages.

{{PROFILE_CONFIGURATION_TABLE}}

## Compilation and orchestration

Figure [-@fig:pipeline-trust-boundaries] summarizes the stage topology: untrusted source data enters at acquisition and stays delimited through preparation, generation, parsing, and rendering.

![{{FIGURE_PIPELINE_TRUST_BOUNDARIES_CAPTION}}](../output/figures/pipeline-trust-boundaries.png){#fig:pipeline-trust-boundaries}

The acquisition layer owns network behavior. It normalizes URLs, checks origin
and public-host policy, reads `robots.txt`, applies shared rate limits, follows
bounded redirects, streams response bodies under a byte limit, and records
rejection reasons. It does not interpret page text as commands.

The preparation layer removes configured presentation selectors, bounds each
page, preserves source URLs and hashes, and wraps source material in a corpus
contract — the bounded transformation of [@eq:preparation]. The process layer
chooses a provider. Deterministic generation is
the default; `auto` is explicitly opt-in and follows configured provider
precedence before deterministic fallback. Provider retries cover only
transient transport and HTTP failures. Malformed or unsafe output is not
silently retried as if it were a network problem.

The parse and render layers validate required portable sections, enforce the
requested target name, append provenance, produce the package contract of
[@eq:rendering], validate the package, and publish it transactionally. The
discovery index is rebuilt only from complete packages.

Figure [-@fig:run-state-machine] shows the persisted run lifecycle; failure is a diagnosable terminal state with sanitized diagnostics.

![{{FIGURE_RUN_STATE_MACHINE_CAPTION}}](../output/figures/run-state-machine.png){#fig:run-state-machine}

The filesystem layout is part of the method. Acquired bundles, prepared
corpora, drafts, run state, failures, manifests, and rendered skills remain
inspectable. This makes a run useful as both an operational artifact and an
evaluation observation.

The scholarly build has a separate dependency order: validate claims and
bibliography, collect completed observations, derive statistics, generate
figures, verify retained website archives, and bind the manuscript. A failed
step prevents a successful build receipt. Rendering and final artifact
validation follow that build. The pipeline contract version is
`{{PIPELINE_VERSION}}` and the package version is `{{PACKAGE_VERSION}}`;
these identifiers are injected from the implementation.

## Agent access and operator instructions

The local MCP adapter exposes discovery, package inspection and validation,
policy checks, and the current evaluation summary through an explicit filesystem
root. Index reconstruction requires a server started with write access. The
default adapter does not acquire websites or launch generators. Its tool,
resource, and prompt surfaces follow the corresponding MCP interaction types
[@mcp-spec]; this implementation is a bounded adapter, without a claim of
exhaustive protocol conformance.

An authored operator `SKILL.md` supplies the workflow for using Skillarum itself.
It is maintained with the software and bundles its command reference. This
operator artifact has a different role from the generated website skills:
it directs local operation, whereas a generated skill records source-derived
reference material. The MCP review prompt preserves that distinction by
requiring source text to be inspected as untrusted data.
