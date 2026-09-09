# Case studies {#sec:case-studies}

## Math 4 Wisdom

The canonical `Three-Minds` target selects one exact page from the Math 4
Wisdom wiki and uses the `#wikitext` extraction boundary [@math4wisdom-source].
The expanded matrix adds a related exposition bundle and a small research-minds
bundle. The resulting skills retain source URLs and content hashes, and they
state that source-page instructions are reference text rather than executable
guidance.

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
