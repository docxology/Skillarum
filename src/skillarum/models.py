"""Typed contracts for configuration, crawl records, and generated skills."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal
from urllib.parse import urlparse

from .utils import is_safe_artifact_label, jsonable, sha256_json, slugify


def _strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


@dataclass(frozen=True)
class ExtractionConfig:
    """Site-specific HTML extraction rules."""

    main_selector: str | None = None
    remove_selectors: tuple[str, ...] = (
        "script",
        "style",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
    )
    max_chars_per_page: int = 40_000
    # Opt-in refinements. Both default off so existing profile fingerprints,
    # caches, and rendered packages are unchanged unless a profile asks.
    preserve_blocks: bool = False
    title_separator: str | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> "ExtractionConfig":
        data = value or {}
        separator = data.get("title_separator")
        result = cls(
            main_selector=data.get("main_selector"),
            remove_selectors=_strings(
                data.get("remove_selectors", cls.remove_selectors)
            ),
            max_chars_per_page=int(
                data.get("max_chars_per_page", cls.max_chars_per_page)
            ),
            preserve_blocks=bool(data.get("preserve_blocks", False)),
            title_separator=str(separator) if separator else None,
        )
        if result.max_chars_per_page <= 0:
            raise ValueError("extraction.max_chars_per_page must be positive")
        return result

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical mapping, omitting opt-in fields left at default."""
        data = jsonable(asdict(self))
        if not self.preserve_blocks:
            data.pop("preserve_blocks")
        if self.title_separator is None:
            data.pop("title_separator")
        return data

    def clean_title(self, title: str) -> str:
        """Keep the final separator-delimited segment of a page title."""
        if not self.title_separator or self.title_separator not in title:
            return title
        tail = title.rsplit(self.title_separator, 1)[1].strip()
        return tail or title


@dataclass(frozen=True)
class RetryConfig:
    """Bounded retry policy shared by network and provider requests."""

    max_attempts: int = 2
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 4.0

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> "RetryConfig":
        data = value or {}
        result = cls(
            max_attempts=int(data.get("max_attempts", cls.max_attempts)),
            base_delay_seconds=float(
                data.get("base_delay_seconds", cls.base_delay_seconds)
            ),
            max_delay_seconds=float(
                data.get("max_delay_seconds", cls.max_delay_seconds)
            ),
        )
        if result.max_attempts <= 0:
            raise ValueError("retry.max_attempts must be positive")
        if result.base_delay_seconds < 0:
            raise ValueError("retry.base_delay_seconds must be non-negative")
        if result.max_delay_seconds < result.base_delay_seconds:
            raise ValueError("retry.max_delay_seconds must be >= base_delay_seconds")
        return result

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class CrawlConfig:
    """Network and crawl safety limits."""

    respect_robots: bool = True
    same_origin_only: bool = True
    allow_private_hosts: bool = False
    follow_links: bool = False
    max_pages: int = 50
    max_requests: int = 100
    max_depth: int = 1
    max_redirects: int = 10
    request_timeout_seconds: float = 20.0
    min_delay_seconds: float = 0.0
    max_response_bytes: int = 2_000_000
    robots_cache_ttl_seconds: float = 3600.0
    user_agent: str = "Skillarum/0.2 (+https://github.com/docxology/projects)"
    retry: RetryConfig = field(default_factory=RetryConfig)

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> "CrawlConfig":
        data = value or {}
        result = cls(
            respect_robots=bool(data.get("respect_robots", cls.respect_robots)),
            same_origin_only=bool(data.get("same_origin_only", cls.same_origin_only)),
            allow_private_hosts=bool(
                data.get("allow_private_hosts", cls.allow_private_hosts)
            ),
            follow_links=bool(data.get("follow_links", cls.follow_links)),
            max_pages=int(data.get("max_pages", cls.max_pages)),
            max_requests=int(data.get("max_requests", cls.max_requests)),
            max_depth=int(data.get("max_depth", cls.max_depth)),
            max_redirects=int(data.get("max_redirects", cls.max_redirects)),
            request_timeout_seconds=float(
                data.get("request_timeout_seconds", cls.request_timeout_seconds)
            ),
            min_delay_seconds=float(
                data.get("min_delay_seconds", cls.min_delay_seconds)
            ),
            max_response_bytes=int(
                data.get("max_response_bytes", cls.max_response_bytes)
            ),
            robots_cache_ttl_seconds=float(
                data.get("robots_cache_ttl_seconds", cls.robots_cache_ttl_seconds)
            ),
            user_agent=str(data.get("user_agent", cls.user_agent)),
            retry=RetryConfig.from_mapping(data.get("retry")),
        )
        if result.max_pages <= 0:
            raise ValueError("crawl.max_pages must be positive")
        if result.max_requests <= 0:
            raise ValueError("crawl.max_requests must be positive")
        if result.max_depth < 0:
            raise ValueError("crawl.max_depth must be non-negative")
        if result.max_redirects < 0:
            raise ValueError("crawl.max_redirects must be non-negative")
        if result.request_timeout_seconds <= 0:
            raise ValueError("crawl.request_timeout_seconds must be positive")
        if result.min_delay_seconds < 0:
            raise ValueError("crawl.min_delay_seconds must be non-negative")
        if result.max_response_bytes <= 0:
            raise ValueError("crawl.max_response_bytes must be positive")
        if result.robots_cache_ttl_seconds < 0:
            raise ValueError("crawl.robots_cache_ttl_seconds must be non-negative")
        return result


@dataclass(frozen=True)
class GenerationConfig:
    """Declarative provider defaults; secrets remain environment-only."""

    backend: str = "deterministic"
    fallback_backend: str | None = None
    model: str = "gpt-4o-mini"
    ollama_model: str = "llama3.2"
    ollama_url: str | None = None
    ollama_timeout_seconds: float = 300.0
    ollama_num_ctx: int = 8192
    ollama_max_prompt_chars: int | None = None
    retry: RetryConfig = field(default_factory=RetryConfig)

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> "GenerationConfig":
        data = value or {}
        max_prompt_chars = data.get("ollama_max_prompt_chars")
        result = cls(
            backend=str(data.get("backend", cls.backend)),
            fallback_backend=(
                str(data["fallback_backend"]) if data.get("fallback_backend") else None
            ),
            model=str(data.get("model", cls.model)),
            ollama_model=str(data.get("ollama_model", cls.ollama_model)),
            ollama_url=(str(data["ollama_url"]) if data.get("ollama_url") else None),
            ollama_timeout_seconds=float(
                data.get("ollama_timeout_seconds", cls.ollama_timeout_seconds)
            ),
            ollama_num_ctx=int(data.get("ollama_num_ctx", cls.ollama_num_ctx)),
            ollama_max_prompt_chars=(
                int(max_prompt_chars) if max_prompt_chars is not None else None
            ),
            retry=RetryConfig.from_mapping(data.get("retry")),
        )
        if result.backend not in {
            "deterministic",
            "openai",
            "ollama",
            "command",
            "auto",
        }:
            raise ValueError(f"unknown generation backend: {result.backend}")
        if result.fallback_backend not in {
            None,
            "deterministic",
            "openai",
            "ollama",
            "command",
        }:
            raise ValueError(f"unknown fallback backend: {result.fallback_backend}")
        if result.backend == result.fallback_backend:
            raise ValueError("generation fallback backend must differ from backend")
        if result.backend == "auto" and result.fallback_backend is not None:
            raise ValueError("auto backend chooses its own fallback chain")
        if result.ollama_timeout_seconds <= 0:
            raise ValueError("generation.ollama_timeout_seconds must be positive")
        if result.ollama_num_ctx <= 0:
            raise ValueError("generation.ollama_num_ctx must be positive")
        if (
            result.ollama_max_prompt_chars is not None
            and result.ollama_max_prompt_chars <= 0
        ):
            raise ValueError("generation.ollama_max_prompt_chars must be positive")
        if result.ollama_url:
            raw_url = (
                result.ollama_url
                if "://" in result.ollama_url
                else f"http://{result.ollama_url}"
            )
            parsed_url = urlparse(raw_url)
            if (
                parsed_url.scheme not in {"http", "https"}
                or not parsed_url.netloc
                or parsed_url.username
                or parsed_url.password
                or any(character.isspace() for character in raw_url)
            ):
                raise ValueError(
                    "generation.ollama_url must be an absolute http(s) URL without credentials"
                )
        return result

    def with_overrides(self, **overrides: Any) -> "GenerationConfig":
        """Return this configuration with only explicitly supplied values changed."""
        data = self.to_dict()
        for key, value in overrides.items():
            if value is not None:
                data[key] = value
        return GenerationConfig.from_mapping(data)

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))

    def fingerprint(self) -> str:
        return sha256_json(self.to_dict())


@dataclass(frozen=True)
class GenerationAttempt:
    """One provider attempt, safe to persist as provenance."""

    backend: str
    model: str | None
    status: Literal["success", "failure"]
    started_at: str
    duration_ms: int
    retries: int = 0
    cache_key: str = ""
    error_type: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {"success", "failure"}:
            raise ValueError("generation attempt status must be success or failure")
        if self.duration_ms < 0 or self.retries < 0:
            raise ValueError(
                "generation attempt duration and retries must be non-negative"
            )
        if self.status == "success" and (self.error or self.error_type):
            raise ValueError("successful generation attempts cannot contain errors")

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GenerationAttempt":
        """Restore one persisted attempt while retaining the typed contract."""
        return cls(
            backend=str(value.get("backend", "")),
            model=str(value["model"]) if value.get("model") is not None else None,
            status=str(value.get("status", "failure")),  # type: ignore[arg-type]
            started_at=str(value.get("started_at", "")),
            duration_ms=int(value.get("duration_ms", 0)),
            retries=int(value.get("retries", 0)),
            cache_key=str(value.get("cache_key", "")),
            error_type=str(value["error_type"]) if value.get("error_type") else None,
            error=str(value["error"]) if value.get("error") else None,
        )


@dataclass(frozen=True)
class GenerationTrace:
    """Provider attempts and the backend that ultimately supplied a draft."""

    attempts: tuple[GenerationAttempt, ...] = ()
    selected_backend: str | None = None
    fallback_used: bool = False
    fallback_chain: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempts": [attempt.to_dict() for attempt in self.attempts],
            "selected_backend": self.selected_backend,
            "fallback_used": self.fallback_used,
            "fallback_chain": list(self.fallback_chain),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "GenerationTrace | None":
        if value is None:
            return None
        attempts = value.get("attempts", [])
        if not isinstance(attempts, list):
            raise ValueError("generation trace attempts must be a list")
        return cls(
            attempts=tuple(
                GenerationAttempt.from_dict(attempt)
                for attempt in attempts
                if isinstance(attempt, dict)
            ),
            selected_backend=(
                str(value["selected_backend"])
                if value.get("selected_backend") is not None
                else None
            ),
            fallback_used=bool(value.get("fallback_used", False)),
            fallback_chain=tuple(
                str(item)
                for item in value.get(
                    "fallback_chain",
                    [
                        attempt.get("backend")
                        for attempt in attempts
                        if attempt.get("backend")
                    ],
                )
                if item
            ),
        )


@dataclass(frozen=True)
class TargetSpec:
    """A named exact-page or filtered page bundle."""

    id: str
    name: str
    urls: tuple[str, ...] = ()
    include_prefixes: tuple[str, ...] = ()
    include_patterns: tuple[str, ...] = ()
    exclude_patterns: tuple[str, ...] = ()
    max_pages: int | None = None
    # Optional authored frontmatter description. When set it is authoritative
    # over the generator's description; the generator's own text is retained
    # in draft metadata.
    description: str = ""

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "TargetSpec":
        target_id = str(value.get("id", "")).strip()
        if not target_id:
            raise ValueError("target.id is required")
        name = str(value.get("name", target_id)).strip()
        if not name:
            raise ValueError(f"target {target_id!r} has an empty name")
        max_pages = value.get("max_pages")
        parsed_max = int(max_pages) if max_pages is not None else None
        if parsed_max is not None and parsed_max <= 0:
            raise ValueError(f"target {target_id!r}.max_pages must be positive")
        return cls(
            id=target_id,
            name=name,
            urls=_strings(value.get("urls", value.get("start_urls"))),
            include_prefixes=_strings(
                value.get("prefixes", value.get("include_prefixes"))
            ),
            include_patterns=_strings(
                value.get("include_patterns", value.get("include"))
            ),
            exclude_patterns=_strings(
                value.get("exclude_patterns", value.get("exclude"))
            ),
            max_pages=parsed_max,
            description=" ".join(str(value.get("description") or "").split()),
        )

    @property
    def slug(self) -> str:
        return slugify(self.name)

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-shaped target configuration.

        An empty description is omitted so profiles that predate the field keep
        their fingerprints.
        """
        data = jsonable(asdict(self))
        if not self.description:
            data.pop("description")
        return data

    def fingerprint(self) -> str:
        """Fingerprint this target's selection contract."""
        return sha256_json(self.to_dict())


@dataclass(frozen=True)
class SourceProfile:
    """Complete source configuration loaded from YAML."""

    id: str
    name: str
    base_url: str
    crawl: CrawlConfig = field(default_factory=CrawlConfig)
    extraction: ExtractionConfig = field(default_factory=ExtractionConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    targets: tuple[TargetSpec, ...] = ()
    area: str = ""

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute http(s) URL")
        if self.area and not is_safe_artifact_label(self.area):
            raise ValueError("profile.area must be a safe directory name")
        ids = [target.id for target in self.targets]
        if len(ids) != len(set(ids)):
            raise ValueError("target ids must be unique")
        id_slugs = [slugify(target.id) for target in self.targets]
        if len(id_slugs) != len(set(id_slugs)):
            raise ValueError("target ids must have unique slugified forms")
        name_slugs = [slugify(target.name) for target in self.targets]
        if len(name_slugs) != len(set(name_slugs)):
            raise ValueError("target names must have unique slugified forms")

    def target(self, target_id: str) -> TargetSpec:
        for target in self.targets:
            if target.id == target_id:
                return target
        raise KeyError(f"unknown target {target_id!r} for profile {self.id!r}")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-shaped profile configuration."""
        data = jsonable(asdict(self))
        data["extraction"] = self.extraction.to_dict()
        data["targets"] = [target.to_dict() for target in self.targets]
        return data

    def fingerprint(self) -> str:
        """Fingerprint all configuration that can affect acquisition or output."""
        return sha256_json(self.to_dict())


@dataclass(frozen=True)
class PageRecord:
    """Normalized content and provenance for one fetched page."""

    requested_url: str
    final_url: str
    canonical_url: str | None
    status_code: int
    title: str
    headings: tuple[str, ...]
    text: str
    links: tuple[str, ...]
    fetched_at: str
    content_sha256: str
    depth: int = 0
    revalidated: bool = False
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PageRecord":
        data = dict(value)
        data["headings"] = _strings(data.get("headings"))
        data["links"] = _strings(data.get("links"))
        data["warnings"] = _strings(data.get("warnings"))
        return cls(**data)


@dataclass(frozen=True)
class BundleRecord:
    """The selected pages that feed one skill generation request."""

    profile_id: str
    profile_name: str
    target_id: str
    skill_name: str
    pages: tuple[PageRecord, ...]
    created_at: str
    warnings: tuple[str, ...] = ()
    events: tuple[dict[str, Any], ...] = ()
    request_count: int = 0
    area: str = ""
    # Refresh-integrity metadata. ``absent_urls`` lists requested URLs whose
    # fetch definitively showed the page is gone (HTTP 404/410);
    # ``incomplete`` marks a crawl whose page set may be short for
    # non-definitive reasons (transient fetch failures, robots rejections,
    # or request/page limits with a non-empty queue). Defaults keep older
    # persisted bundles readable.
    absent_urls: tuple[str, ...] = ()
    incomplete: bool = False

    def __post_init__(self) -> None:
        if self.request_count < 0:
            raise ValueError("bundle request_count must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["pages"] = [page.to_dict() for page in self.pages]
        return jsonable(data)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "BundleRecord":
        data = dict(value)
        data["pages"] = tuple(
            PageRecord.from_dict(page) for page in data.get("pages", [])
        )
        data["warnings"] = _strings(data.get("warnings"))
        data["events"] = tuple(
            dict(event) for event in data.get("events", []) if isinstance(event, dict)
        )
        data["absent_urls"] = _strings(data.get("absent_urls"))
        data["incomplete"] = bool(data.get("incomplete", False))
        return cls(**data)


@dataclass(frozen=True)
class PreparedPage:
    """Page content bounded and delimited for a generator."""

    url: str
    title: str
    headings: tuple[str, ...]
    text: str
    links: tuple[str, ...]
    truncated: bool = False
    requested_url: str = ""
    final_url: str = ""
    canonical_url: str | None = None
    fetched_at: str = ""
    status_code: int = 0
    content_sha256: str = ""
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return jsonable(asdict(self))


@dataclass(frozen=True)
class PreparedCorpus:
    """Generator input after deterministic preparation."""

    profile_id: str
    profile_name: str
    target_id: str
    skill_name: str
    pages: tuple[PreparedPage, ...]
    warnings: tuple[str, ...] = ()
    profile_fingerprint: str = ""
    events: tuple[dict[str, Any], ...] = ()
    request_count: int = 0
    area: str = ""

    def __post_init__(self) -> None:
        if self.request_count < 0:
            raise ValueError("prepared corpus request_count must be non-negative")

    @property
    def source_urls(self) -> tuple[str, ...]:
        return tuple(page.url for page in self.pages)

    def context_text(self) -> str:
        sections: list[str] = []
        for index, page in enumerate(self.pages, start=1):
            headings = ", ".join(page.headings) or "(none)"
            sections.append(
                "\n".join(
                    [
                        f'<source_page index="{index}" url="{page.url}">',
                        f"TITLE: {page.title}",
                        f"HEADINGS: {headings}",
                        "CONTENT_START",
                        page.text,
                        "CONTENT_END",
                        "LINKS: " + ", ".join(page.links),
                        "</source_page>",
                    ]
                )
            )
        return "\n\n".join(sections)

    def generation_payload(self, *, include_retrieval: bool = False) -> dict[str, Any]:
        """Return the stable input contract used to cache generator work.

        Retrieval timestamps are operational provenance, not source content. They
        are excluded by default so refreshing an unchanged page does not repeat
        an expensive generator call. Command generators may opt in because an
        external provider receives the complete payload and may inspect metadata.
        """
        pages: list[dict[str, Any]] = []
        for page in self.pages:
            payload = {
                "url": page.url,
                "title": page.title,
                "headings": list(page.headings),
                "text": page.text,
                "links": list(page.links),
                "truncated": page.truncated,
                "requested_url": page.requested_url,
                "final_url": page.final_url,
                "canonical_url": page.canonical_url,
                "status_code": page.status_code,
                "content_sha256": page.content_sha256,
                "warnings": list(page.warnings),
            }
            if include_retrieval:
                payload["fetched_at"] = page.fetched_at
            pages.append(payload)
        return {
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "target_id": self.target_id,
            "skill_name": self.skill_name,
            "area": self.area,
            "profile_fingerprint": self.profile_fingerprint,
            "warnings": list(self.warnings),
            "request_count": self.request_count,
            "pages": pages,
        }

    def fingerprint(self, *, include_retrieval: bool = False) -> str:
        """Fingerprint the prepared corpus for stage reuse."""
        return sha256_json(self.generation_payload(include_retrieval=include_retrieval))

    def to_payload(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "target_id": self.target_id,
            "skill_name": self.skill_name,
            "area": self.area,
            "profile_fingerprint": self.profile_fingerprint,
            "warnings": list(self.warnings),
            "events": [dict(event) for event in self.events],
            "request_count": self.request_count,
            "pages": [page.to_dict() for page in self.pages],
            "context": self.context_text(),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PreparedCorpus":
        data = dict(value)
        data.pop("context", None)
        data["pages"] = tuple(
            PreparedPage(
                url=str(page["url"]),
                title=str(page.get("title", "")),
                headings=_strings(page.get("headings")),
                text=str(page.get("text", "")),
                links=_strings(page.get("links")),
                truncated=bool(page.get("truncated", False)),
                requested_url=str(page.get("requested_url", "")),
                final_url=str(page.get("final_url", "")),
                canonical_url=page.get("canonical_url"),
                fetched_at=str(page.get("fetched_at", "")),
                status_code=int(page.get("status_code", 0)),
                content_sha256=str(page.get("content_sha256", "")),
                warnings=_strings(page.get("warnings")),
            )
            for page in data.get("pages", [])
        )
        data["warnings"] = _strings(data.get("warnings"))
        data["profile_fingerprint"] = str(data.get("profile_fingerprint", ""))
        data["events"] = tuple(
            dict(event) for event in data.get("events", []) if isinstance(event, dict)
        )
        data["request_count"] = int(data.get("request_count", 0))
        return cls(**data)


@dataclass(frozen=True)
class SkillDraft:
    """Structured skill content before Markdown rendering."""

    name: str
    description: str
    body: str
    source_urls: tuple[str, ...]
    generator: str
    metadata: dict[str, Any] = field(default_factory=dict)
    trace: GenerationTrace | None = None

    @classmethod
    def from_mapping(
        cls,
        value: dict[str, Any],
        *,
        default_name: str,
        source_urls: tuple[str, ...],
        generator: str,
        metadata: dict[str, Any] | None = None,
        trace: GenerationTrace | None = None,
    ) -> "SkillDraft":
        name = str(value.get("name", default_name)).strip()
        description = str(value.get("description", "")).strip()
        body = str(value.get("body", value.get("content", ""))).strip()
        if not name or not description or not body:
            raise ValueError(
                "skill draft requires non-empty name, description, and body"
            )
        merged = dict(metadata or {})
        value_metadata = value.get("metadata")
        if isinstance(value_metadata, dict):
            merged.update(value_metadata)
        parsed_trace = trace
        trace_value = value.get("trace", value.get("generation_trace"))
        if parsed_trace is None and isinstance(trace_value, dict):
            parsed_trace = GenerationTrace.from_dict(trace_value)
        return cls(
            name=name,
            description=description,
            body=body,
            source_urls=tuple(source_urls),
            generator=generator,
            metadata=merged,
            trace=parsed_trace,
        )

    @classmethod
    def from_payload(cls, value: dict[str, Any]) -> "SkillDraft":
        """Restore and validate a draft persisted by the process stage."""
        source_urls = _strings(value.get("source_urls"))
        generator = str(value.get("generator", "")).strip()
        metadata = value.get("metadata", {})
        if not generator:
            raise ValueError("skill draft requires a generator")
        if not isinstance(metadata, dict):
            raise ValueError("skill draft metadata must be a mapping")
        trace_value = value.get("trace", value.get("generation_trace"))
        if trace_value is not None and not isinstance(trace_value, dict):
            raise ValueError("skill draft generation trace must be a mapping")
        return cls.from_mapping(
            value,
            default_name=str(value.get("name", "")),
            source_urls=source_urls,
            generator=generator,
            metadata=metadata,
            trace=GenerationTrace.from_dict(trace_value),
        )

    def to_payload(self) -> dict[str, Any]:
        return jsonable(asdict(self))
