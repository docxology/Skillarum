"""Website-to-agent-skill generation pipeline."""

__version__ = "0.3.0"

from .models import (
    BundleRecord,
    CrawlConfig,
    ExtractionConfig,
    GenerationAttempt,
    GenerationConfig,
    GenerationTrace,
    PageRecord,
    PreparedCorpus,
    PreparedPage,
    SkillDraft,
    SourceProfile,
    TargetSpec,
    RetryConfig,
)
from .research import (
    AdjudicationRecord,
    ClaimRecord,
    CitationRecord,
    EvaluationCase,
    EvaluationObservation,
    EvaluationReport,
    ReviewRating,
)

__all__ = [
    "BundleRecord",
    "CrawlConfig",
    "ExtractionConfig",
    "GenerationAttempt",
    "GenerationConfig",
    "GenerationTrace",
    "PageRecord",
    "PreparedCorpus",
    "PreparedPage",
    "SkillDraft",
    "SourceProfile",
    "TargetSpec",
    "RetryConfig",
    "ClaimRecord",
    "CitationRecord",
    "AdjudicationRecord",
    "EvaluationCase",
    "EvaluationObservation",
    "EvaluationReport",
    "ReviewRating",
]
