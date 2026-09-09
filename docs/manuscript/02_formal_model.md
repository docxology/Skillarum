# Formal model and invariants {#sec:formal-model}

## Objects and transformation boundary

| Symbol | Meaning and scope |
| --- | --- |
| $S,T,v$ | Source profile, selected target, and pipeline contract version |
| $\omega$ | Realized external responses, failures, and clock readings |
| $B=(P,E,W)$ | Acquired page sequence, request-event trace, and warnings |
| $\ell,C$ | Per-page preparation limit and bounded prepared corpus |
| $G,\Gamma,D$ | Generator, non-secret configuration, and resulting draft |
| $K=(M,F)$ | Rendered Markdown and its provenance manifest |
| $H$ | Hash over an explicitly serialized artifact or contract |

Let a profile be $S$, a named target be $T$, and the pipeline version be
$v$. Acquisition maps a profile and target to a bundle of normalized pages:

$$
A_v(S,T;\omega) = B = (P, E, W),
$$ {#eq:acquisition}

where $P$ is a finite sequence of page records, $E$ is the request-event
trace, and $W$ is a warning set. The realized acquisition environment $\omega$
includes remote responses, request failures, and clock readings. Acquisition
is a partial operation: a failed target need not produce a usable bundle.
Preparation is a bounded transformation

$$
Q(B, \ell) = C,
$$ {#eq:preparation}

where $\ell$ is the per-page context limit and $C$ contains only bounded,
delimited source data. A generator $G$ maps $C$ to a draft $D$, and the
renderer $R$ maps $D$ and $C$ to a package $K$:

$$
K = R(D,C) = (M, F),
$$ {#eq:rendering}

with Markdown artifact $M$ and provenance manifest $F$.

The cache identities are derived as:

$$
\begin{aligned}
I_A &= H(v, S, T), \\
I_G &= H(v, Q(B,\ell), G, \Gamma), \\
I_K &= H(M).
\end{aligned}
$$ {#eq:identities}

where $\Gamma$ is the non-secret provider configuration. Secrets are not
members of any persisted identity. A cached value is reusable only when its
schema, identity, payload hash, and required validation fields all agree.
Here $I_A$ identifies a configuration-specific cache entry; it does not prove
that the remote site is unchanged. Freshness requires a new acquisition or
recorded revalidation. $H$ denotes SHA-256 over the implementation's defined
serialization; hash-based integrity relies on its collision resistance and
does not authenticate a source or operator.

For a schema-{{MANIFEST_SCHEMA_VERSION}} rendered package $K$ from run $r$, let $C_r$ denote the
persisted prepared corpus at `02_prepare`, and let $L(K,C_r)$ be the pagewise
lineage predicate over profile, target, area, ordered source URLs, retrieval
fields, raw-content hashes, prepared-text hashes, truncation flags, and
warnings. Let $\operatorname{PackageProv}(K)$ be the package-level provenance
predicate: it holds when $K$'s manifest carries every required current-schema field
(cache identity, profile and generator fingerprints, generation trace, request
events, and artifact hashes), the recorded artifact hashes match the
materialized `SKILL.md` and manifest bytes, and the manifest's portable skill
name agrees with the rendered frontmatter. Human-facing requested names are
retained separately from that portable slug. Research provenance is complete
only when the package-level provenance predicate and $L(K,C_r)$ both hold:

$$
\begin{aligned}
\operatorname{ProvComplete}(K,r)
  &= \operatorname{PackageProv}(K) \\
  &\quad{}\land L(K,C_r).
\end{aligned}
$$ {#eq:lineage}

This distinction matters because a manifest can be internally self-consistent
after an unauthorized substitution while no longer describing the run that
produced it. Legacy packages do not expose enough lineage fields; their
lineage value is therefore reported as unavailable rather than inferred.

## Implementation properties and assumptions

The following are implementation properties with explicit assumptions and
source-level justifications. They are not machine-checked proofs or empirical
estimates of reliability.

The acquisition map in [@eq:acquisition] includes the environment explicitly;
the conditional rendering statement below fixes all realized input fields.
The identities in [@eq:identities] therefore support comparison of recorded
artifacts without equating determinism with remote-source freshness.

::: {.proposition #prop:deterministic-rendering title="Deterministic rendering"}
For fixed prepared corpus $C$, deterministic generator configuration, and
pipeline version $v$, and identical persisted provenance and generation-trace fields, repeated rendering produces the same Markdown artifact
and artifact hash.

:::

*Justification.*
With timing and retrieval fields held fixed, the deterministic generator extracts from the ordered prepared pages,
configuration, and target name. The renderer serializes the same frontmatter,
sections, and provenance fields in a fixed order; cache-hit retrieval metadata
is read from $C$ rather than regenerated. Therefore both byte strings and
$H(M)$ are equal across repetitions.

::: {.proposition #prop:integrity-publication title="Integrity-preserving publication"}
The built-in renderer validates a staged package before replacing the published
directory. Index construction independently validates the files it advertises.

:::

*Justification.*
The publication transaction writes both files below a private staging path,
validates the staged directory, moves the old directory to a backup, and
renames the staged directory into place. Each rename is atomic on the same
filesystem; the two-rename replacement has a brief absence window.
Index construction rejects absent, malformed, or hash-invalid packages. A
partial staging directory is excluded from index discovery. Crash recovery
can restore a backup on the next run. This is a package-completeness property,
not continuous availability or durability under arbitrary filesystem failure.

::: {.proposition #prop:index-soundness title="Index soundness"}
For every entry advertised by the discovery index, the referenced package is
complete, schema-valid, and hash-valid at the time the index is built.

:::

*Justification.*
Index construction enumerates every non-hidden `manifest.json` below the
skills root. It validates the manifest schema, verifies
the recorded artifact hashes against the materialized files, and checks
$\operatorname{PackageProv}(K)$ before emitting an entry. Package directories
that are missing a file, fail schema validation, or disagree with their hashes
abort the rebuild (fail closed) instead of being advertised; only dot-prefixed
paths are skipped from discovery. The proposition is a soundness claim about
the generated index at
that validation point; it does not prevent an external actor from modifying a
file after publication, which is why publication manifests and later
validation remain necessary.

::: {.proposition #prop:trust-boundary title="Trust-boundary preservation"}
The application constructs provider instructions separately from source text,
derives output paths from the configured target, and never executes generated
content in the renderer.

:::

*Justification.*
Acquisition and preparation represent source text as delimited data; provider
instructions are constructed outside that data region. Output paths come from
the profile-authoritative target name, and subprocess invocation uses argument
arrays without shell evaluation. The renderer writes Markdown and validates
it but never interprets source text as code. These implementation facts do not prove that an LLM will obey the instruction
hierarchy: delimiters and content filters are not an isolation mechanism for
model behavior. Nor do they prove source truth or downstream harness safety.

::: {.proposition #prop:failure-diagnosability title="Failure diagnosability"}
For exceptions caught inside the run state machine, Skillarum attempts to
persist a failed state and sanitized diagnostic record. Recorded provider
failures remain visible when a fallback succeeds.

:::

*Justification.*
Assuming writable storage and that the process reaches its exception handler,
the run state machine writes transitions and failure manifests atomically at
the owning run path. Each provider attempt records backend, model, status,
timing, retry count, and sanitized error text in the generation trace. The
fallback result therefore does not erase the failed attempt history. Process
termination, setup errors before state initialization, and storage failures can
prevent a diagnostic write; this is not a total failure-recording theorem.

These propositions depend on the stated implementation boundary: no browser
JavaScript execution, no generated-code execution, and no shell evaluation by the built-in command invocation. A configured command
is trusted operator code and can perform its own I/O; it is not sandboxed. The deterministic idempotency proposition applies to
the source-bounded skill artifact; evaluation envelopes retain an operational
timestamp, so stable report identity is weaker than byte identity of a full
research report.
