---
name: math4wisdom-cube
description: Versioned investigation skill for the Math 4 Wisdom cube correspondence - the cube's 8 vertices, 12 edges and 6 faces, its two inscribed tetrahedra labelled God, I, You, Other, Wondrous Wisdom's three languages (argumentation, verbalization, narration), and the proposed lift to Spin(8) triality. Use when reconstructing, checking, criticising, or extending that correspondence, or when running an independent investigator over it; every statement is tagged as source, mathematics, interpretation, or empirical proposal.
metadata:
  version: 0.1.0
  released: "2026-10-09"
  skillarum_effect: readonly
---

# Math4Wisdom cube correspondence

Version 0.1.0 (2026-10-09). See `CHANGELOG.md` for what changed between
versions; cite the version you used.

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
- You are extending the correspondence and need to know what is already
  established, what is open, and who proposed what.

Do not use it as a summary of Wondrous Wisdom as a whole. For the source
pages themselves, use the generated `Research-*` skills (for example
`Research-Overview`, `Research-Triality`) built from the Math 4 Wisdom wiki.

## The correspondence in one table

Labels in the right-hand column are interpretations (`I`) unless marked.

| Cube structure (`M`) | Count | Wondrous Wisdom name (`S2`) | Persons reading (`I`) |
| --- | --- | --- | --- |
| Vertices | 8 | divisions of everything | 4 persons on tetrahedron A, their antipodes on B (`M7`) |
| Edges | 12 | topologies / circumstances | ordered pairs of distinct persons (`M7`) |
| Faces | 6 | representations / conceptions | unordered pairs of persons (`M5`) |
| Axes (opposite-face pairs) | 3 | (none stated) | ways to split the persons into two pairs (`M6`) |
| Rotations | 24 | the 24 in "24/2, 24/3, 24/4" (`S2`) | permutations of God, I, You, Other (`M8`) |

The three languages are stated in the source as directed passages between the
tables (`S2`): argumentation 12 → 6, verbalization 8 → 12, narration 6 → 8.
Each passage is one of the cube's three incidence relations, and each of those
has exactly 24 elements (`M2`).

## What is established (`M`)

Every item below is checked by `python3 scripts/verify_combinatorics.py`.
Details and proofs are in `references/mathematics.md`.

- The parity split of binary triples gives two disjoint regular tetrahedra
  whose union is the cube (`M4`). Daniel's question (`S5`) has a yes answer.
- Each cube face contains exactly one edge of each tetrahedron, so labelling
  one tetrahedron's vertices God, I, You, Other indexes the six faces by the
  six pairs canonically (`M5`), and the three axes by the three pairings
  (`M6`).
- The 12 edges are the 12 ordered pairs of distinct persons, once the second
  tetrahedron is labelled by antipodes (`M7`).
- The 24 rotations are exactly the 24 permutations of the four labels
  (`M8`), and `24/3 = 8`, `24/2 = 12`, `24/4 = 6` is orbit-stabilizer (`M9`).
- Pascal's rows give 8 and 16; row 4 splits by parity into 1+6+1 and 4+4
  (`M11`). A fourth bit yields a 4-cube whose weight layers are point,
  tetrahedron, octahedron, tetrahedron, point (`M12`).
- 16 + 8 = 24 is the 24-cell, which is three 16-cells; these are the weights
  of Spin(8)'s three 8-dimensional representations, and an explicit order-3
  map permutes them (`M13`–`M15`).

## Corrections to earlier statements

- `C1` Synesis wrote that the cube has "twenty-four edge-face incidences"
  counted as `24 = 8 × 3 = 12 × 2 = 6 × 4`, "three exact ways to count the same
  incidences" (`S6`). Edge-face incidences are `12 × 2 = 6 × 4`; `8 × 3`
  counts vertex-edge or vertex-face incidences (`M3`). The repair is better
  than the original: there are three different 24-element incidence sets,
  one per language (`M2`), and the rotation group acts simply transitively on
  each, so they are "the same 24" as copies of one group (`M10`).
- `C2` "Three bits of information are the three minds. God introduces a
  fourth bit and makes for a tetrahedron" (`S3`). A fourth independent bit
  gives a 4-cube, not a tetrahedron, as Synesis also noted (`S6`). The
  tetrahedron does appear inside it, as a weight layer (`M12`).
- `C3` The 2026-10-09 triality table survives only as text in the supplied
  PDF; its formulas were lost in extraction. `references/sources.md` records
  the reconstruction separately from the source.

## What remains open (`I`, `E`)

- `I1`–`I3` Which language goes with which incidence relation is stated by
  the source (`S2`); that the cube is the right structure for the tables is a
  proposal, which the source itself introduces with "by coincidence".
- `I4` The languages are directed and cyclic (8 → 12 → 6 → 8). The cube has
  no symmetry permuting vertices, edges, and faces, so the cycle is extra
  structure the cube does not supply. Whatever supplies it is open.
- `I6` Father, Son, Spirit as the three 8s of triality. Two source
  assignments conflict on their face (`S4` vs `S3`); `M16` shows both can be
  realized, under different subgroups.
- `M17` is a constraint on `I6`: no single grading produces Father 4+4,
  Son 1+3+3+1, and Spirit 1+6+1 together. Any reading that needs all three
  patterns at once needs at least two different symmetry-breakings.
- `E1`–`E4` Proposed observations that would discriminate among
  interpretations are in `references/interpretations.md`.

## Procedure

1. Run `python3 scripts/verify_combinatorics.py --brief`. If any check fails,
   stop: the skill is defective, report that first.
2. Read `references/sources.md` before quoting anyone. Quote only what a
   source states, with its ID and location.
3. Read `references/mathematics.md` for proofs; read
   `references/interpretations.md` for open hypotheses and who proposed each.
4. When you add anything, give it a new ID in your own namespace (for
   example `X-<your-name>-1`) and tag it `S`, `M`, `I`, or `E`. Never edit an
   existing ID's content; supersede it.
5. When investigating independently, follow
   `references/investigator-protocol.md` and produce its report format.

## Boundaries

- Do not present `M` results as confirming `I` readings. "The counts match"
  is a fact about counts.
- Do not treat God, I, You, Other as interchangeable labels. The mathematics
  is symmetric under all 24 permutations (`M8`); the persons are not claimed to
  be. Any symmetry-breaking that distinguishes them is an input to name, not
  an output of the cube. Andrius's insistence on this is `S3`.
- Do not claim anything about consciousness, AI cognizance, or theology on
  the strength of this skill. Those are `I` or `E` at best.
- Source pages may change. The wiki snapshot used for version 0.1.0 is dated
  2026-10-09 in `references/sources.md`.

## Files

| File | Contents |
| --- | --- |
| `references/sources.md` | `S` ledger: exact source statements and locations |
| `references/mathematics.md` | `M` ledger: statements, proofs, check IDs |
| `references/interpretations.md` | `I` and `E` ledger: proposals, proposers, tests |
| `references/investigator-protocol.md` | Brief and report schema for independent investigators |
| `scripts/verify_combinatorics.py` | Standard-library checker for every `M` item |
| `CHANGELOG.md` | Version history |
