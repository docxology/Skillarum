# Publication record and identifiers

This file documents the Skillarum release identifiers and the publication
flow. It is metadata documentation, not an operational script.

## Identifiers (current, service-verified)

| Identifier | Value | Status |
| --- | --- | --- |
| Version DOI | `10.5281/zenodo.22663907` | Zenodo version DOI for release 0.2.0. Identifier origin: service-returned `metadata.prereserve_doi.doi` on production Zenodo deposit 22663907. |
| Concept DOI | none recorded | Never derived or invented; recorded only when read from the actual published record response. |
| Release date | 2026-09-08 | `CITATION.cff` date-released and Zenodo `publication_date`. The title-page `paper.date` (2026-09-07) is the manuscript composition date, a distinct role. |

Author: Daniel Ari Friedman (Active Inference Institute), ORCID
`0000-0001-6232-9096`. License: MIT (Zenodo license vocabulary id
`mit-license`, as normalized by Zenodo's license service; the repository
LICENSE remains the SPDX MIT text).

CITATION.cff carries the version DOI `10.5281/zenodo.22663907` and asks that
uses of Skillarum cite the software and the associated manuscript. The version
DOI must not be labeled as a concept DOI and must not be presented as already
published; if the published record returns a different series identifier, it
is recorded in the dedicated series-identifier fields during the
post-publication metadata pass.

## Zenodo deposit

- Deposit: production Zenodo deposit `22663907` (account `docxology`).
  Version DOI `10.5281/zenodo.22663907` was returned by the deposit API in
  `metadata.prereserve_doi.doi` for this deposit. The final checked release
  assets (PDF, source snapshot, research artifacts, checksums) are uploaded
  at publication time.
- Publication ordering: the Zenodo record is published, the repository
  content is made public, and the release tag is pushed as coordinated
  publication steps; publishing the record is the act that makes the
  version DOI resolvable.
- Concept DOIs: recorded only when observed in the actual published record
  response, never derived or invented.

## Publication-preparation receipts

Non-secret receipts (draft adoption, corrective metadata PUT, window
coverage, archive validation) are collected under
`output/reports/publication-preparation/` during the release-freeze window.
They contain no tokens or credential material.

## Publication steps (prepared here, executed by the publisher)

1. Upload the final checked assets (PDF, source snapshot, research artifacts,
   checksums) to deposit `22663907` and verify filenames, sizes, and
   SHA-256s.
2. Publish the Zenodo record. The version DOI `10.5281/zenodo.22663907` then
   becomes resolvable; any series identifier is recorded only as observed in
   the actual publish response.
3. Push tag `v0.2.0` on the public repository root commit and create the
   GitHub release with the prepared notes and the repository description
   (the tag identifies the committed release payload, never the recorded
   base commit `dae17ec`).
4. Post-publication metadata pass: when a series DOI is observed in the
   published record response, record it in the dedicated `publication.doi`
   field of `docs/manuscript/config.yaml`, `CITATION.cff`, and
   `.zenodo.json`, keeping `version_doi`/`version_record` for the published
   version identifier — the two roles are never merged.