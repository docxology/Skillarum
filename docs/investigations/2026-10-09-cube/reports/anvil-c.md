# Investigator report: anvil-c

## Provenance
- **Investigator:** the "Anvil" persona running on Claude Opus 5.5 (`claude-opus-5-5`). The Kimi/Moonshot pipeline was **not** used. All reasoning and scratch code are Claude-family, the same lineage as the skill's author ("Claude, an Anthropic model"). That is the strongest coupling in this report.
- **Date:** 2026-10-09
- **Skill version read:** math4wisdom-cube 0.1.0
- **Inputs, in order:** `investigator-protocol.md`; `sources.md` up to "## S7". This **included S4**, because my `awk` printed everything before S7, which the protocol excluded. Only after recording Phase 1 did I open `SKILL.md`, `mathematics.md`, `interpretations.md`, S7–S8, `CHANGELOG.md` and the script.
- **Leakage before Phase 1:**
  - The task brief named "directed cycle 8→12→6→8", "triality assignment of Father/Son/Spirit" and the IDs M7/M10/M15/M17.
  - `ls` showed the filenames.
- **Shared with other investigators:** the same brief, the same files, and probably overlapping training data. Scratch code is in `$TMPDIR/anvilc/`. The repo was not modified.

## 1. Blind reconstruction
- **Structure:** a cube, with divisions = 8 vertices, circumstances = 12 edges, conceptions = 6 faces. S2's `24/3, 24/2, 24/4` read to me as orbit-stabilizer for the order-24 rotation group: stabilizers of order 3 for vertices, 2 for edges, 4 for faces.
- **Languages:** each language is the incidence relation between its two ranks. Verbalization = vertex–edge, argumentation = edge–face, narration = face–vertex. Each has 24 elements. The direction comes from S2's wording, not from the cube.
- **Persons:** God, I, You, Other go on one inscribed tetrahedron (as in S5 and S6). Then:
  - faces = unordered pairs;
  - edges = (person, antipode-of-another-person), i.e. ordered pairs;
  - the other tetrahedron = the four "faces opposite each person", which is S3's four transcendings.
- **S3 arithmetic:** 1+3+3+1 and 1+4+6+4+1 read as the face lattices (all subsets) of a triangle and of a tetrahedron. So "the fourth bit makes a tetrahedron" is literally true at the level of face lattices. Unanims then see the even subsets (1+6+1), and the Father sees the odd subsets (4+4).
- **An alternative placement of persons:** project the 4-bit odd layer onto 3 bits by deleting God's bit. That puts the persons on a God-centred claw, not on a parity tetrahedron.

This matches I2's pairing and the S6 labelling. It diverges on C2 (the fourth bit) and on where the persons go.

## 2. Verification
`python3 scripts/verify_combinatorics.py` passed every check with exit 0. Note that the M10 check prints no evidence.

My own checks, all in scratch code:
- **M7:** the edge-to-ordered-pair bijection holds. But it is equivariant under T_d (the 24 symmetries that keep tetrahedron A) and **not** under O (the rotation group). The M5 face labelling behaves the same way.
- **M10:** confirmed. O acts simply transitively on vertex–edge, vertex–face and edge–face pairs. Under T_d, only edge–face stays a single orbit of 24; vertex–edge and vertex–face split 12+12.
- **M15:** T is orthogonal, has order exactly 3, and maps v→c→s→v. Confirmed.
- **M16:** all three table rows reproduced.
- **M17:** no hits over all 50,624 nonzero integer directions in [−7,7]⁴. I also checked the proof step by step and it is sound. The step "six equal values of ±c_i force 0" holds because a nonzero c_i gives two different values. I could not break M17. Its scope is one-parameter gradings only, which the skill says.
- **The cycle 8→12→6→8:** I composed the three incidence matrices.
  - The composite is symmetric, so going forward equals going backward.
  - Entries by Hamming distance 0/1/2/3 are 6/4/2/0.
  - Eigenvalues are 24, 8 (three times) and 0 (four times). The parity character is in the kernel.
- **Handedness along the cycle:** I moved round the cycle through chiral flags, choosing a handedness at each step. The holonomy has order 1, 2, 3 or 4, depending on where the handedness flips. All results are O-equivariant.
- **The God-centred alternative:** deleting God's bit maps the persons and their opposite faces onto Hamming layers {G} | {I, Y, O} | {faces opposite I, Y, O} | {face opposite G}. Neither parity class consists only of persons.

## 3. Identification audit

| Item | Classification | Evidence (S/M IDs) | Note |
|---|---|---|---|
| Vertices ↔ divisions | numerical only | S1 "by coincidence" | |
| Vertices = persons on A, antipodes on B | canonical given a choice | S6, M4 | The choice is the tetrahedron plus a labelling. A competing placement fits S3's arithmetic (X-3). |
| Edges ↔ circumstances | numerical only | S2 | S2's note counts 12 as 3×4 ("threesome has four conceptions"). |
| Edges = ordered pairs | canonical given three choices | M7 | Choices: A, the antipode labelling, and the A→B orientation. Equivariant under T_d only (X-1). |
| Faces ↔ conceptions | numerical only | S2 | |
| Faces = unordered pairs | canonical given the choice of A | M5 (verified) | |
| Axes = pairings | forced, given the face labels | M6 | |
| Rotations (24) = permutations of persons | **wrong as a joint reading** | M8, M9, X-1 | The group that respects rows 1–3 is T_d. Under T_d the vertices form two orbits of 4 (24/6), so 24/3 = 8 is lost. Each half is true separately. |
| Each language = an incidence relation | forced given I1, undirected | S2, M2 | The direction is not supplied. |
| C1 | forced (correct) | S6, M3 | |
| C2 | unsupported as a correction | S3, X-4 | |
| I1 | numerical only | S1 | |
| I2 "structurally indistinguishable" | holds under O; wrong under T_d | X-2 | |
| I3, and M9's persons paragraph | **wrong** | X-1 | See below the table. |
| I4 | partly unsupported | X-5, X-6 | Unoriented incidence gives no direction. With handedness, the cube gives a non-trivial holonomy. |
| I5, person ↔ opposite-face pairing | forced (tetrahedral duality) | I5 | |
| I5, Four Zoas proposed by Daniel and Synesis | **unsupported by the ledger** | S5, S6 | Neither quotation mentions the Zoas. |
| I6 | constrained, correctly | M16, M17 (verified) | |
| I7 | open | M15 | |
| I8, octahedron model | canonical given a choice | M18 | The face-lattice reading is more direct (X-4). |
| I8, "an atlas of views does" | unsupported | S5 | Not in the S5 quotation. |
| E4, "Andrius proposed three modes" | unsupported provenance | S3, S8 | Not in either quotation. |
| S8 table reconstruction | canonical given the Cl(W⊕W*) model | S8 | Correctly tagged I. |

On I3 and M9's persons paragraph:
- Under O, an edge's stabilizer is the transposition of its own two persons. That reverses the ordered pair it is supposed to fix.
- A face's stabilizer is C4, and its 4-cycles do not preserve the face's label {X, Y}.
- Under T_d, the edge (G, I) is fixed by (Y O), and the face {G, I} by ⟨(G I), (Y O)⟩.

## 4. Discriminating consequences

**D1 — Which symmetry group: O or T_d (X-1, X-2).** The two groups predict different structure.
- **T_d** (persons are not interchangeable with their transcendings):
  - the 8 divisions split 4+4 inside the cube itself, which is the Father's pattern;
  - argumentation is a single regular orbit;
  - verbalization and narration each split 12+12, into a person-anchored half and a transcendence-anchored half.
- **O:**
  - all three languages are regular and indistinguishable;
  - the equivariant labels change: faces ↔ the six 4-cycles (cyclic orders of all four persons, with opposite faces as reversed orders); vertices ↔ the eight 3-cycles (one person fixed, the other three cycled one way); edges ↔ ordered pairs of the complementary persons.
- **The test:** in Wondrous Wisdom, are conceptions pairs of persons, or cyclic orders of all four? Do divisions come as 4 + 4 (person / transcending), or as 4 triads × 2 orientations?

**D2 — The directed cycle (X-5, X-6).**
- **If the languages are unoriented incidence relations (I2):**
  - a full cycle is symmetric, so forward and reverse look the same;
  - it never takes a division to its antipode, so it never takes a person to their own transcending;
  - it erases the person/anti-person distinction, because parity is in its kernel.
- **If each language step carries a handedness** (cf. S4's "oppositely handed"), the cube does supply a direction:
  - the holonomy has order 2, 4 or 3 when the handedness flips at the circumstance, conception or division junction;
  - for orders 3 and 4, the forward cycle gives g and the reverse gives g⁻¹, so the two directions differ.
- **The test:** in a worked cycle of three source examples, does the reading return to its start, return changed with period 3 (which selects a flip at the divisions), or land on the antipode (which refutes the incidence model)?

**D3 — Where the persons go (X-3).**
- **The S6 parity tetrahedron:** no two persons are adjacent.
- **The God-centred claw from S3:** God is adjacent to I, You and Other. The 1+3+3+1 layers are the Father's 4+4 refined by singling out God, which is S8's W = L ⊕ U with L as God's line.
- **The test:** does any single circumstance relate God and I directly? A yes favours the claw, and it would also answer E3: God is the structurally distinguished person.

## 5. My additions

| ID | Tag | Statement | Basis |
|---|---|---|---|
| X-anvil-c-1 | M | M5 and M7 labels are T_d-equivariant, not O-equivariant. Under O, edges ↔ ordered pairs of the complementary persons, faces ↔ 4-cycles, vertices ↔ 3-cycles. T_d has 2 orbits on vertices. | verified computationally |
| X-anvil-c-2 | M | Under T_d, edge–face pairs form one regular orbit, while vertex–edge and vertex–face split 12+12. Under A4 all three split 12+12. | verified |
| X-anvil-c-3 | M/I | Deleting God's bit from the 4-bit odd layer gives a 1+3+3+1 placement with God at the centre and no person-only parity class (M). That this is the intended placement is I. | verified (M part); argued (I part) |
| X-anvil-c-4 | M/I | The 2³ and 2⁴ subset lattices are the face lattices of a triangle and a tetrahedron, matching S3's "1 center, 3 vertices, 3 sides, 1 face" (M). Read this way, Unanims see the even faces (1+6+1) (I). | argued |
| X-anvil-c-5 | M | The composite of the three incidence relations equals its reverse, takes values 6/4/2/0 by distance, has eigenvalues 24, 8³, 0⁴, and has parity in its kernel. | verified |
| X-anvil-c-6 | M | With a handedness at each step, the holonomy round the cycle has order 1, 2, 3 or 4, set by which junction flips (the Coxeter relations of [4,3]). | verified |
| X-anvil-c-7 | E | D1–D3 above. | proposal |
| X-anvil-c-8 | M | M17 has no hits in [−7,7]⁴, and its proof is sound. | verified and argued |

## 6. Disagreements with the skill

1. **The persons column and the rotation row use two different S4s.** Table row 5, the persons paragraphs of M8 and M9, and I3 are inconsistent with rows 1–3. The concrete failures are in the note under the §3 table, and the evidence is X-1. The fix is to state that the persons reading is a T_d structure, and that under T_d S2's 24/3 = 8 does not come out as an orbit count.
2. **C2 overclaims.** S3 counts the parts of a triangle (1+3+3+1) and of a tetrahedron (1+4+6+4+1). Those are exactly the face lattices of 2³ and 2⁴, so "a fourth bit makes a tetrahedron" is correct read that way (X-4). C2 is a correction only under the vertex-set reading.
3. **I2 says the three languages are indistinguishable.** That holds only for O. Once persons are pinned to A (X-2), argumentation is distinguished.
4. **I4 says the cube does not supply the cycle.** Unoriented incidence does not, and X-5 strengthens that: forward and reverse are identical. But with handedness, the cube does give an order-3 cycle (X-6), so "not supplied" should be qualified.
5. **Provenance gaps.**
   - The Four Zoas attribution (I5) has no support in the S5 or S6 quotations.
   - "An atlas of views does" (I8) is not in the S5 quotation.
   - The "three modes" proposal (E4) is not in the S3 or S8 quotations.
   - These should be quoted with their locations, or retagged as the skill's own additions.
6. **Uniqueness of the person placement.** The S6 parity-tetrahedron labelling is presented as *the* persons reading. X-3 is an alternative that follows from S3's arithmetic and should be listed beside it.
