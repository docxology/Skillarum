# Changelog

All notable changes to Skillarum are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-09-08

### Added
- **Tutorial documentation** - Complete walkthrough from clone to first rendered skill installed in a harness
- **Architecture refresh** - Updated module documentation covering redaction, policies, install, evals, runtimes, serve, quarantine, mcp_server, and repo_source
- **Serve command** - Read-only HTTP discovery server exposing rendered skills via REST API
- **Repository-as-source ingestion** - Support for local git repositories as skill sources with commit-SHA provenance  
- **MCP stdio server** - Zero-dependency Model Context Protocol server for agent integration
- **Quarantine-then-promote** - Safety mechanism for refreshed drafts that differ from cached canonical versions
- **Cross-runtime frontmatter compilation** - Per-target field allowlists for claude, codex, and agentskills compatibility
- **Fixture evaluation gates** - Release-blocking numeric gates with dated baseline scorecard
- **Install manifest and drift detection** - Sidecar tracking for installed vs canonical skill comparison
- **Security policy packs** - Declarative regex-based validation for rendered skill content
- **Secret redaction** - Two-pass credential scrubbing with non-leakage verification gates

### Improved  
- **Documentation accuracy** - All command examples in AGENTS.md and README.md verified working
- **Test coverage** - Hermetic scholarship fixes and comprehensive edge case testing
- **Manuscript outputs** - Regenerated with updated figure captions and cross-references
- **Formal model** - Numbered display equations with proper cross-referencing
- **Security model** - Formal adversary model and fail-closed composition propositions

### Fixed
- **Manuscript restoration** - Restored the docs/manuscript/ directory
- **Unused locals cleanup** - Removed flagged variables in runtimes and quarantine modules
- **Citation synchronization** - Updated concurrent-work and intro context citations with verification

### Documentation
- Added complete tutorial covering doctor, pack, verify --policy security, install --harness claude, drift
- Refreshed architecture.md with new module responsibilities and trust boundaries  
- Verified all README.md and AGENTS.md command examples execute successfully
- Added comprehensive troubleshooting guidance for common issues

## Prior Releases

See git log for detailed commit history prior to formal changelog adoption.