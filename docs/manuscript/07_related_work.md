# Related work and scholarly context {#sec:related-work}

Skillarum is a source compiler with a research ledger, not a claim that a
language model has understood a website. Its nearest literatures therefore
need to be kept distinct: retrieval and grounding, interactive web agents,
skill or program synthesis, provenance and documentation, and security of
systems that process retrieved text.

## Retrieval, form, and bounded source compilation

Retrieval-augmented generation makes the generator/evidence separation
explicit [@rag]. Skillarum shares that separation with a different artifact
boundary: a declarative profile selects pages, a deterministic preparation
stage records page-local text, and the rendered skill carries URLs, hashes,
retrieval times, and warnings. Retrieval is therefore an acquisition input,
not a license to treat every retrieved sentence as an instruction or as
verified truth.

This distinction also follows the form/meaning caution in Bender and Koller
[@bender-koller-form-meaning]. A well-formed or fluent generated paragraph is
not, by itself, evidence that the source claim is true or that the system has
acquired the source author’s intended meaning. The deterministic backend is
accordingly extractive and source-bounded; provider backends are useful
convenience layers whose semantic quality remains an empirical question. The
paper does not use linguistic fluency as a proxy for truth.

Data Statements provide a particularly relevant documentation precedent:
they ask researchers to state what data and populations support a claim and to
avoid ungrounded generalization [@bender-friedman-data-statements].
Skillarum operationalizes an analogous run-level statement for website
compilation: source origin, profile and target identity, page selection,
content hashes, truncation, generator trace, and validation status are
machine-readable. This is an engineering analogue, not a claim that a cache
manifest replaces ethical review or domain expertise.

Datasheets for Datasets and Model Cards broaden the same documentation
lineage. Datasheets make motivation, collection, composition, recommended use,
and limits part of the artifact contract [@datasheets-for-datasets]. Model
Cards make intended use, evaluation procedure, and known limitations visible
alongside a model release [@model-cards]. Skillarum applies that
documentation pattern to compiled skill packages: it records intended source
scope, source selection, retrieval conditions, generator attempts, validation
status, and limitations. The analogy is deliberately bounded. A generated
skill is neither a dataset datasheet nor a model card; it is a source-bounded
reference artifact that borrows their reporting discipline.

## Web agents and executable skills

ReAct couples reasoning with acting [@react], and WebArena evaluates agents in
realistic browser environments [@webarena]. These lines of work motivate
explicit action boundaries and evaluation environments, but Skillarum v1
does not click, execute JavaScript, submit forms, or infer a browser policy.
Its fetcher is static HTTP/HTML and its output is a document for later agent
use.

SkillWeaver is the closest comparison. Its paper and implementation focus on
web-agent exploration, practice trajectories, skill discovery, and reusable
API or browser-agent behavior [@skillweaver-repo; @skillweaver-paper].
Skillarum borrows the useful conceptual separation among knowledge,
procedure, and verification, but changes the object being produced: a
portable, source-bounded `SKILL.md` with a provenance manifest rather than an
executable web interaction API. Thus the systems are complementary rather
than direct baselines. Skillarum does not claim to reproduce SkillWeaver’s
interactive capabilities or to outperform them.

Portable Agent Skills documentation specifies filesystem-oriented skills with
a `SKILL.md` entry point [@agent-skills-docs]. Skillarum follows that
portable surface and makes the frontmatter name Codex-compatible, while
preserving human-facing area and target names in the package path and
manifest. The package includes installation and drift tracking for supported local
harness roots; these are operational conveniences, not evidence of semantic
quality across harnesses.

Implementation surfaces also follow named open-source precedents, credited in
the source docstrings: cross-runtime frontmatter compilation adapts tripleyak's
SkillForge [@skillforge-tripleyak], repository-as-source ingestion adapts
xiaokillua's SkillForge [@skillforge-xiaokillua], and installation with drift
tracking plus declarative policy packs adapt attebury's SkillPress
[@skillpress-attebury]. In the same problem space, xiaokillua's SkillPress
compiles websites, documents, and repositories into SKILL.md packs
[@skillpress-xiaokillua]. These tools are attribution lineage and design
comparison points, not evaluation baselines; no performance comparison is
claimed against them.

The Model Context Protocol provides a complementary interoperability surface:
servers expose resources, prompts, and tools to clients through a protocol
contract [@mcp-spec]. Skillarum ships a local MCP stdio adapter for index construction and package
validation, alongside a read-only HTTP discovery surface. Neither executes
website-derived behavior. Index construction writes a local discovery file;
MCP access is therefore not universally read-only. This distinction
matters for risk analysis. An MCP tool can cross an execution boundary, while
a Skillarum package is a static instruction document plus provenance. The
shipped adapter exposes maintenance functions around that document contract;
it is not an interactive browser-agent policy.

## Provenance, reproducibility, and human evaluation

The W3C PROV family supplies a vocabulary for entities, activities, and agents
that produce artifacts [@prov-overview]. Skillarum uses the same general
logic without claiming formal PROV interoperability: page and corpus hashes
identify source bytes, generator traces identify attempted activities, and
atomic publication plus index validation constrain what becomes discoverable.
These identities prove what the pipeline recorded, not the truth of a source
claim.

Reproducible computational research emphasizes that a result should be
accompanied by the code, inputs, execution conditions, and records needed to
recreate or inspect it [@sandve-reproducibility]. Skillarum implements this
principle at the artifact level: profile and target fingerprints, prepared
corpora, provider traces, content hashes, validation reports, and publication
manifests make the transformation inspectable. This guarantee is conditional,
not absolute. A deterministic render can be repeated from the same prepared
corpus, whereas a live acquisition can change when a site, robots policy,
redirect, or provider changes.

The FAIR Guiding Principles motivate making research outputs findable,
accessible, interoperable, and reusable [@fair-guiding-principles]. The
project is FAIR-oriented in this operational sense: JSON ledgers, stable
identifiers, portable Markdown, explicit hashes, and documented interfaces
support those goals. It does not claim formal FAIR compliance, long-term
archival preservation, or unrestricted reuse of scraped content. Source terms,
copyright, privacy, and retention decisions remain outside the pipeline's
technical guarantees.

Human evaluation is treated as an instrument that must itself be described.
The Human Evaluation Datasheet (HEDS) argues for structured reporting of
evaluation details to support comparison and reproducibility [@shimorina-belz-human-datasheet].
Skillarum therefore records criterion definitions, {{RATING_MINIMUM}}–{{RATING_MAXIMUM}} ratings, evidence
notes and URLs, rater IDs, paired cases, agreement status, and adjudication
records. The publication gate is deliberately conservative: with no two-rater
dataset, agreement is reported as pending and no empty agreement plot is
presented. This is a reporting design decision, not evidence of high or low
quality.

## Security and responsible use

The threat model is motivated by work showing that instructions embedded in
retrieved data can redirect LLM-integrated applications through indirect
prompt injection [@greshake-indirect-prompt-injection]. Skillarum responds
with layered controls: source text is delimited and labeled untrusted, source
instructions are preserved as evidence rather than promoted to generator
directives, redirects and origins are constrained, credentials are excluded
from manifests, and generated code is never executed. These controls reduce
the attack surface of this static pipeline; they do not prove immunity for a
downstream agent that later loads the skill or visits the source site.

Practitioner security guidance reaches a similar conclusion from a different
direction. OWASP's guidance for large language model applications identifies
prompt injection and insecure output handling as first-order application risks
[@owasp-llm-top-10]. NIST's AI RMF frames risk management as voluntary,
context-specific work across design, development, use, and evaluation
[@nist-ai-rmf]. Skillarum therefore treats security claims as scoped
engineering invariants: the pipeline can bound acquisition, generation, and
publication behavior, but it cannot certify downstream deployment choices.

Robots handling is informed by the published Robots Exclusion Protocol
[@robots-rfc], with deliberately conservative failure handling; no complete RFC
conformance claim is made.
Licensing and terms of use remain responsibilities of the operator and
the source publisher. A public URL is not automatically a grant to republish
all content. The current artifacts are intended for evaluation and
source-bounded reference use, with live results labeled as case studies.

## Scope of comparison

The related work supports design choices and threat-model vocabulary. It does
not establish that Skillarum improves semantic quality, reduces provider
latency, provides complete website coverage, or is safer in every downstream
agent runtime. Those propositions remain hypotheses until an adequately
specified evaluation with independent raters, repeated runs, and a broader
target matrix supplies evidence. The present paper reports implementation
contracts, reproducible artifact checks, and two deliberately bounded public-source configurations.
