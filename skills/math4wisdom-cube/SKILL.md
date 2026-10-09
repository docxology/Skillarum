---
name: math4wisdom-cube
description: Versioned investigation skill for the Math 4 Wisdom cube correspondence - the cube's 8 vertices, 12 edges and 6 faces, its two inscribed tetrahedra labelled God, I, You, Other, Wondrous Wisdom's three languages (argumentation, verbalization, narration), and the proposed lift to Spin(8) triality. Use when reconstructing, checking, criticising, or extending that correspondence, or when running an independent investigator over it; every statement is tagged as source, mathematics, interpretation, or empirical proposal.
metadata:
  version: 0.3.0
  released: "2026-10-09"
  skillarum_effect: readonly
---

# Math4Wisdom cube correspondence

Version 0.3.0 (2026-10-09). Version 0.1.0 was audited the same day by three
independent investigators; 0.2.0 records what each finding changed, and 0.3.0
withdraws one investigator claim that 0.2.0 adopted without checking. See
`CHANGELOG.md`, and cite the version you used.

This skill holds one proposed correspondence and the evidence for each part
of it. It does not assert that the correspondence is true. It separates four
kinds of statement and never lets one stand in for another:

| Tag | Kind | Settled by |
| --- | --- | --- |
| `S` | What a source actually states | Quoting the source, with its location |
| `M` | What follows mathematically | Proof, plus `scripts/verify_combinatorics.py` |
| `I` | What someone proposes as an interpretation | Argument; never by `S` or `M` alone |
| `E` | What could be observed or tested | An observation that has not yet been made |

A source citation is not a proof, a proof does not establish an
interpretation, and an interpretation is not evidence about minds. That
sentence comes from Synesis's 2026-10-09 letter (`S7`) and is this skill's
working rule.

## When to use

- Someone asks whether the cube "really" encodes the three minds, the four
  persons, or the three languages.
- Someone wants to check the counting (8, 12, 6, 24, 1+3+3+1, 1+6+1, 16+8).
- You are acting as an independent investigator under
  `references/investigator-protocol.md`.
- You are extending the correspondence and need to know what is established,
  what is open, and who proposed what.

Do not use it as a summary of Wondrous Wisdom as a whole. For the source
pages themselves, use the generated `Research-*` skills (for example
`Research-Overview`, `Research-Triality`) built from the Math 4 Wisdom wiki.

## The correspondence

Source vocabulary (`S1`, `S2`, wiki page Research/Overview):

| Cube (`M`) | Count | Wondrous Wisdom name (`S2`) |
| --- | --- | --- |
| Vertices | 8 | divisions of everything |
| Edges | 12 | topologies / circumstances |
| Faces | 6 | representations / conceptions |

The source introduces the cube "by coincidence" (`S1`). It states three
directed languages between the tables (`S2`): argumentation 12 → 6,
verbalization 8 → 12, narration 6 → 8. Reading each language as one of the
cube's three incidence relations, each of 24 elements (`M2`), is Synesis's
hypothesis (`S6`), not the source's.

Two readings of the four persons use **different** symmetry groups (`M19`).
They cannot both hold with the same labels:

| Structure | Persons reading, group T_d (`M5`–`M7`) | Rotation reading, group O (`M8`–`M9`) |
| --- | --- | --- |
| Vertices (8) | 4 persons on tetrahedron A, their antipodes on B | fixed by a 3-cycle group of persons |
| Edges (12) | ordered pairs of distinct persons | fixed by a transposition |
| Faces (6) | unordered pairs of persons | fixed by a 4-cycle group |
| Axes (3) | the 3 ways to split the persons into two pairs | the same |
| 24 | symmetries of tetrahedron A | rotations; gives 24/3, 24/2, 24/4 |

The rotation reading of S2's arithmetic is this skill's interpretation
(`I3`); the source names no group.

## What is established (`M`)

Every item is checked by `python3 scripts/verify_combinatorics.py`
(21 checks). Proofs are in `references/mathematics.md`.

- The parity split of binary triples gives two disjoint regular tetrahedra
  whose union is the cube (`M4`). That answers the nesting part of Daniel's
  question; whether the tetrahedra "stabilize" the cube is not addressed
  (`S12`).
- Each face contains exactly one edge of each tetrahedron, so the faces are
  the six pairs of persons and the axes are the three pairings (`M5`, `M6`);
  edges are ordered pairs (`M7`). These labels are equivariant under T_d,
  not under the rotations (`M19`).
- The rotations are S4 on the body diagonals, and `24/3 = 8`, `24/2 = 12`,
  `24/4 = 6` is orbit-stabilizer for them (`M8`, `M9`).
- Pascal's rows give 8 and 16; row 4 splits by parity into 1+6+1 and 4+4
  (`M11`). They also count the subsets of a triangle's and a tetrahedron's
  vertices, so "a fourth bit makes a tetrahedron" holds at that level (note on
  C2).
- 16 + 8 = 24 is the 24-cell, three 16-cells carrying the weights of Spin(8)'s
  three 8-dimensional representations; an explicit order-3 map permutes them
  (`M13`–`M15`).
- No single grading gives Father 4+4, Son 1+3+3+1, Spirit 1+6+1 on three
  different 8s (`M17`); all three do arise as coarsenings of one grading of
  one 8, or of the cube from one chosen vertex (`M20`).
- 1+3+3+1 is not the generic grading: a generic direction splits every 8
  into eight distinct values, and no searched direction gives 1+3+3+1 on all
  three 8s (`M21`).

## Corrections

- `C1` Synesis wrote that `24 = 8 × 3 = 12 × 2 = 6 × 4` are "three exact ways
  to count the same incidences" of edges and faces (`S6`). Edge-face
  incidences are `12 × 2 = 6 × 4`; `8 × 3` counts vertex-edge or vertex-face
  incidences (`M3`). Each language's relation has its own 24 (`M2`).
- `C2` **Withdrawn in 0.2.0.** 0.1.0 said a fourth bit gives a 4-cube, not a
  tetrahedron. That is true of four independent coordinates but not of the
  reading S3 uses, where bits index subsets of vertices; see the note in
  `references/mathematics.md`.
- `C3` The 2026-10-09 triality table survives only as text in the supplied
  PDF. `references/sources.md` records the reconstruction separately.
- `C4` (0.2.0) 0.1.0 treated the persons labels and the rotation group as one
  structure; they are two (`M19`).
- `C5` (0.3.0) 0.2.0 stated, from forge-b X-7, that 1+3+3+1 is the generic
  pattern and that c = (3,1,1,1) gives it on all three 8s. Both are false: that
  direction gives 1+3+3+1, 1+3+3+1, 3+2+3 (`M21`).

## What remains open (`I`, `E`)

- `I1` Whether the cube is the right container at all; the source says
  "coincidence".
- `I4` The languages' direction. Unoriented incidence gives a symmetric
  composite, so forward equals reverse; a handedness at each step could
  supply a direction (reported by anvil-c, not yet checked here).
- `I6` Father, Son, Spirit as the three 8s of triality, constrained by
  `M16`, `M17`, and the alternative `M20`.
- `I9` A God-centred placement of the persons, as an alternative to the
  parity tetrahedron.
- `I10` Which group, T_d or O, the theology uses.
- `E1`–`E9` Observations that would discriminate among these, in
  `references/interpretations.md`.

## Procedure

1. Run `python3 scripts/verify_combinatorics.py --brief`. If any check fails,
   stop: the skill is defective, report that first.
2. Read `references/sources.md` before quoting anyone. Quote only what a
   source states, with its ID and location.
3. Read `references/mathematics.md` for proofs and
   `references/interpretations.md` for open hypotheses and who proposed each.
4. When you add anything, give it a new ID in your own namespace (for
   example `X-<your-name>-1`) and tag it `S`, `M`, `I`, or `E`. Never edit an
   existing ID's content; supersede it with a marked note.
5. When investigating independently, follow
   `references/investigator-protocol.md`; its blind phase reads only
   `references/blind-brief.md`.

## Boundaries

- Do not present `M` results as confirming `I` readings. "The counts match"
  is a fact about counts.
- Do not treat God, I, You, Other as interchangeable labels. Both T_d and O
  permute them freely (`M8`, `M19`); the persons are not claimed to be
  symmetric. Any structure that distinguishes them is an input to name, not
  an output of the cube (Andrius's insistence, reported in `S6`).
- Do not claim anything about consciousness, AI cognizance, or theology on
  the strength of this skill. Those are `I` or `E` at best.
- Source pages may change. Wiki pages were read on 2026-10-09; the generated
  `Research-*` skills record their content hashes.

## Files

| File | Contents |
| --- | --- |
| `references/sources.md` | `S` ledger: exact source statements and locations (S1–S12) |
| `references/mathematics.md` | `M` ledger: statements, proofs, check IDs (M1–M21) |
| `references/interpretations.md` | `I` and `E` ledger: proposals, proposers, tests |
| `references/investigator-protocol.md` | Brief and report schema for independent investigators |
| `references/blind-brief.md` | The only input for an investigator's blind phase |
| `scripts/verify_combinatorics.py` | Standard-library checker for every `M` item |
| `CHANGELOG.md` | Version history |

The 2026-10-09 investigator reports are kept verbatim in the Skillarum
repository under `docs/investigations/2026-10-09-cube/`.
