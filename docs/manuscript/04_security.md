# Threat model, provenance, and safety {#sec:security}

The principal adversary is untrusted source content. A page may contain text
that looks like a system instruction, attempts to exfiltrate secrets, requests
unsafe redirection, or embeds misleading navigation. This is the indirect
prompt-injection setting in which retrieved data can alter the behavior of an
LLM-integrated application [@greshake-indirect-prompt-injection]. Skillarum
therefore keeps source content inside a corpus delimiter, preserves it as
evidence, and requires generated skills to distinguish source claims from
agent reasoning.

The security taxonomy is intentionally aligned with practitioner guidance
without treating a checklist as proof of safety. OWASP's LLM application risks
name prompt injection and insecure output handling as distinct failure modes
[@owasp-llm-top-10]. NIST's AI RMF frames AI risk management as voluntary,
context-specific work across design, development, use, and evaluation
[@nist-ai-rmf]. Skillarum therefore states controls as local invariants and
residual risks rather than as a certification claim.

The network boundary rejects unsafe redirects, private hosts by default,
non-HTML responses, excessive bodies, cross-origin pages, and disallowed
robots paths. DNS checks precede connection establishment; the transport does
not pin the checked address, so rebinding between resolution and connection
remains a residual risk. Network egress controls are needed where this threat
is material. The request budget counts robots, redirects, retries, and page
requests separately from the accepted-page limit. This distinction prevents a
large failure or redirect sequence from being hidden by a page-count metric.

The provider boundary excludes credentials from cache keys and manifests.
External command generators receive JSON through a non-shell subprocess call.
Generated code is never executed. Error messages are sanitized before they
enter provenance. Redaction detects configured credential patterns and is not
a guarantee against every possible secret representation. The configured
command backend executes trusted operator-supplied code; argument arrays avoid
implicit shell expansion but do not sandbox that executable.

The publication boundary protects consumers from partial state. A package
contains source hashes, retrieval metadata, request events, generator traces,
cache identity, artifact hashes, warnings, and limitations. A hash proves
identity of the recorded bytes; it does not prove the truth of the source
claim. That distinction is central to the claim ledger and to the data-statement
discipline of limiting claims to the observed source and run population
[@bender-friedman-data-statements].

The security guarantee is intentionally compositional and limited. The
pipeline labels source text as untrusted and keeps application instructions
separate, but these controls do not guarantee that a model ignores injected
instructions. It also cannot control a downstream harness that
chooses to execute generated text, follow a newly changed URL, or grant the
skill broad tool permissions. We therefore publish both positive invariants
and residual boundary conditions rather than claiming immunity.

Figure [-@fig:cache-integrity-flow] traces the hash-dependency chain from profile and target configuration to the published discovery index.

![{{FIGURE_CACHE_INTEGRITY_FLOW_CAPTION}}](../output/figures/cache-integrity-flow.png){#fig:cache-integrity-flow}

Pack checksums bind recorded archive members to hashes. The `packer` field is
self-asserted metadata: no signing key or trusted identity authority is involved,
so checksum verification must not be described as signer authentication.
