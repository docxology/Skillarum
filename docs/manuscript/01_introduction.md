# Introduction and contributions {#sec:introduction}

Agent skills are a compact way to provide reusable, on-demand context to an
agent. Their practical value depends on more than producing Markdown: the
artifact must be discoverable, bounded, attributable, safe to load, and useful
under changing source conditions. A website-to-skill system therefore has two
different responsibilities. It must acquire and transform public material, and
it must communicate exactly what was observed and what remains uncertain.

Skillarum addresses the second responsibility as a first-class engineering
problem. A profile names an origin, extraction boundary, network policy, and
target bundle. A run then produces a content-addressed chain from page records
to a portable skill package. The canonical artifact remains a plain
`SKILL.md`, so the output can be carried into compatible harnesses without a
provider-specific wrapper.

The contributions are:

1. a declarative, bounded website-to-skill pipeline with same-origin, robots,
   response-size, redirect, rate-limit, canonical, and request/page controls;
2. interchangeable deterministic, OpenAI, Ollama, command, and fallback
   generators with typed retry traces and target-name enforcement;
3. transactional package publication and cache validation based on explicit
   profile, target, corpus, generator, and artifact identities;
4. a source-bounded output contract that preserves prompt-injection text as
   data and never executes scraped or generated code; and
5. an evidence and publication layer that separates measured observations,
   live case studies, source citations, hypotheses, and pending claims.

The {{CONFIGURED_AREA_COUNT}} configured source areas are Math 4 Wisdom and the Active Inference
Institute, with target bundles declared in {{CONFIGURED_PROFILE_COUNT}} profiles. They are intentionally useful
examples rather than a claim to have sampled the web generally.
