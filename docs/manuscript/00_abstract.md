# Abstract {#sec:abstract}

Skillarum is a local pipeline for turning selected server-rendered website
pages into portable `SKILL.md` artifacts for agent harnesses. The system
separates acquisition, preparation, generation (the `03_process` stage),
parsing, and rendering, while
recording page hashes, canonical and final URLs, request events, provider
attempts, fallback history, and artifact integrity metadata.

The project contributes three things. First, it makes website-to-skill
compilation inspectable and resumable through typed contracts and content-aware
cache identities. Second, it treats scraped HTML as untrusted data and makes
provider failure, truncation, and uncertainty visible rather than silently
promoting them to instructions. Third, it defines an evidence-gated evaluation
surface for reproducibility, provenance, fallback behavior, and human review of
semantic and procedural usefulness.

The current report summarizes {{OBSERVATION_COUNT}} persisted observations from
{{PROFILE_COUNT}} source profiles and {{TARGET_COUNT}} target bundles. The
package-valid rate among completed runs is {{PACKAGE_VALID_RATE}}, with
{{FALLBACK_COUNT}} recorded fallback observations and {{TRUNCATED_PAGES}}
truncated pages. These values are conditional on run completion; they are
descriptive observations, not an end-to-end success probability or a population
estimate. Human-review agreement is currently {{RATING_STATUS}}.
