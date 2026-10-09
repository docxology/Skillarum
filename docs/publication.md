# Publication record and identifiers

This file documents the Skillarum release identifiers and the publication
flow. It is metadata documentation, not an operational script.

## Identifiers (current, service-verified)

| Identifier | Value | Status |
| --- | --- | --- |
| Version DOI (0.3.1) | `10.5281/zenodo.23271010` | Published 2026-10-09 as record 23271010 (new version of 23269108). Identifier origin: service-returned `metadata.prereserve_doi.doi`, confirmed by the publish response and the public record. |
| Version DOI (0.3.0) | `10.5281/zenodo.23269108` | Published 2026-10-09 as record 23269108 (new version of 22663907). Identifier origin: service-returned `metadata.prereserve_doi.doi`, confirmed by the publish response and the public record. |
| Version DOI (0.2.0) | `10.5281/zenodo.22663907` | Published 2026-09-10 (record 22663907). |
| Concept DOI | `10.5281/zenodo.22663906` | Read on 2026-10-09 from the published 0.2.0 record's `conceptdoi` field; resolves to the latest version. |
| Release date | 2026-10-09 | `CITATION.cff` date-released and Zenodo `publication_date` for 0.3.1 (0.3.0 was released the same day). |

Author: Daniel Ari Friedman (Active Inference Institute), ORCID
`0000-0001-6232-9096`. License: MIT (Zenodo license vocabulary id
`mit-license`, as normalized by Zenodo's license service; the repository
LICENSE remains the SPDX MIT text).

CITATION.cff carries the 0.3.1 version DOI `10.5281/zenodo.23271010` as its
primary DOI, lists the concept DOI `10.5281/zenodo.22663906` and the 0.3.0
and 0.2.0 version DOIs as further identifiers, and asks that
uses of Skillarum cite the software and the associated manuscript. A version
DOI must not be labeled as a concept DOI, and a reserved DOI must not be
presented as published until the record is public.

## Release 0.3.1

Deposit 23271010 is the new-version draft of record 23269108. It is a
correction release with the same four-asset set as 0.3.0: the rendered
manuscript PDF, a source snapshot of tag `v0.3.1`, a research-artifacts
archive, and `CHECKSUMS.sha256`. It carries `math4wisdom-cube` 0.3.0, which
withdraws a claim the 0.2.0 skill in the 0.3.0 archive still contains. The
tag `v0.3.1` names the released commit `08e0177`. All four files were
re-downloaded from the draft and matched `CHECKSUMS.sha256` before
publication; the same four files are attached to the GitHub release.

## Release 0.3.0

Deposit 23269108 is the new-version draft of record 22663907. Its assets
follow the 0.2.0 set: the rendered manuscript PDF, a source snapshot of the
tagged commit, a research-artifacts archive (reports, evaluation, figures,
data, hydrated manuscript, web and EPUB renders), and `CHECKSUMS.sha256`.
The tag `v0.3.0` names the released commit `a8c55d9`. All four files were
re-downloaded from the draft and matched `CHECKSUMS.sha256` before
publication; the same four files are attached to the GitHub release.

## Zenodo deposit (0.2.0)

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