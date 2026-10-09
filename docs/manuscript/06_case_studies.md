# Case studies {#sec:case-studies}

## Math 4 Wisdom

The canonical `Three-Minds` target selects one exact page from the Math 4
Wisdom wiki and uses the `#wikitext` extraction boundary [@math4wisdom-source].
The expanded matrix adds a related exposition bundle and a small research-minds
bundle. The resulting skills retain source URLs and content hashes, and they
state that source-page instructions are reference text rather than executable
guidance.

### Targets derived from a site's own index

Hand-listing every page of a large wiki does not scale and invites silent
omissions. The `profile-from-index` command reads a page the site's author
already maintains as a table of contents, keeps same-origin links under a path
prefix in document order, and writes one exact-page target per link
[@math4wisdom-research-index]. The derived profiles currently hold
{{INDEX_DERIVED_TARGET_COUNT}} targets grouped under
{{INDEX_DERIVED_SECTION_COUNT}} index sections. Each target keeps the index's
own section label in an authored frontmatter description, and the profile
records the index URL, retrieval time, and content hash, so the selection is
itself traceable. Acquisition still goes through the crawler, so robots,
origin, and request-budget rules apply to the index page as to any other.
Block-preserving extraction keeps paragraph and list boundaries for these
pages; it is opt-in so that earlier profiles keep their cache identities.

### An authored investigation skill

Generated skills are deliberately source-bounded: they say what pages state
and nothing else. Some uses need more, such as checking a proposed
mathematical reading of a source. The `math4wisdom-cube` skill is authored
rather than generated. It concerns a correspondence proposed in Math 4 Wisdom
between a cube's vertices, edges, and faces and three tables of perspectives,
together with three "languages" passing between them
[@math4wisdom-overview]. The skill keeps four ledgers that are never allowed
to stand in for one another: what a source states, what follows
mathematically, what someone proposes as interpretation, and what could be
tested. Each mathematical item is recomputed by a standard-library script in
the package. The skill is versioned, and its protocol asks independent
investigators to reconstruct the correspondence before reading the skill's
own analysis, to verify and audit every identification, and to label their
own additions.

Three investigators audited the first version in separate sessions. None
found a failing check. All three independently found that the skill had used
two different symmetry groups as if they were one, and two found claims
credited to the wrong source; the revised version records each change against
the report that prompted it [@cube-investigation-record]. Two of the three
investigators shared a model family with the skill's author, and one had not
run on the model requested, which only its own provenance statement
revealed. The convergence is therefore weak evidence of independence. The
record shows what the ledger structure is for: disagreements arrived as
specific, attributable, checkable statements.

## Active Inference Institute

The canonical `Institute-Overview` target combines the public homepage, about,
active-inference, learning, projects, resources, directory, and get-involved
pages under the `main` selector [@aii-source; @aii-repository]. Additional
declarative bundles separate foundations/ecosystem, programs/participation, and
research/learning projects. This design keeps bundle membership reviewable in
YAML rather than hiding it in crawler heuristics.

Both examples are snapshots. Retrieval timestamps and hashes are the evidence
for what the pipeline saw; they are not assertions that the websites remain
unchanged.

## Dated refresh and website inventories

The completed skill observations span {{OBSERVED_FROM}} to
{{OBSERVED_THROUGH}} (UTC). Observation times identify completed packages;
page-level retrieval times in their manifests identify the corresponding
source acquisitions. A fresh acquisition uses an empty output cache so that
an earlier site's response cannot become evidence for today's refresh.

{{SITE_REFRESH_SUMMARY}}
