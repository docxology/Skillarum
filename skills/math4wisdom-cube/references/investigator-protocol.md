# Independent investigator protocol

This implements Synesis's proposal (S7): independently operating
investigators reconstruct the correspondence, verify the combinatorics,
identify unsupported identifications, and propose observations or
mathematical consequences that would discriminate among interpretations,
each preserving provenance and identifying its own additions.

## Independence

- Each investigator works alone, from the same brief, without seeing other
  investigators' reports. Record which model or person ran it, when, and
  what it was given.
- Distinct names do not establish independence. Shared training data,
  shared prompts, and shared source files all couple investigators; say what
  each one shared.
- An investigator may disagree with this skill. Disagreement with evidence
  is the point of running more than one.

## Phases

### 1. Blind reconstruction (do this before reading the skill's ledgers)

Read only `references/sources.md` sections S1–S3 and S5–S6. Without reading
`mathematics.md` or `interpretations.md`, write down:

- which structure you would use to carry 8 divisions, 12 circumstances, and
  6 conceptions, and why;
- how you would pair the three languages with that structure;
- where, if anywhere, the four persons go.

Record this before phase 2. It is the E1 observation.

### 2. Verify

Run `python3 scripts/verify_combinatorics.py`. Then check at least three
`M` items by hand or with your own code, choosing at least one of M7, M10,
M15, M17. Report any check you believe is wrong, with a counterexample.

### 3. Audit identifications

For every row of the correspondence table in `SKILL.md` and every `I` entry,
classify the link as one of:

- **forced** — the mathematics leaves no alternative once the stated inputs
  are fixed;
- **canonical given a choice** — unique after one named choice (say which);
- **numerical only** — the counts match and nothing more is shown;
- **unsupported** — the skill or a source asserts more than its evidence;
- **wrong** — contradicted by mathematics or by the cited source.

Quote the source text you rely on, by S-ID.

### 4. Propose discriminating consequences

Propose at least two observations or mathematical consequences that would
come out differently under different interpretations. For each, say which
interpretations it separates and what result would favour which.

## Report format

Write Markdown with these sections, in order:

```markdown
# Investigator report: <investigator id>

## Provenance
- Investigator: <model or person, version if known>
- Date: <YYYY-MM-DD>
- Skill version read: <e.g. math4wisdom-cube 0.1.0>
- Inputs: <files and pages read; anything else given>
- Shared with other investigators: <prompt, files, training lineage>

## 1. Blind reconstruction
## 2. Verification
## 3. Identification audit
| Item | Classification | Evidence (S/M IDs) | Note |
## 4. Discriminating consequences
## 5. My additions
| ID | Tag (S/M/I/E) | Statement | Basis |
## 6. Disagreements with the skill
```

Every statement in sections 3–6 that did not come from a source or the skill
must appear in section 5 with an ID of the form `X-<investigator id>-<n>`.
If a section has nothing to report, write "None" rather than omitting it.
