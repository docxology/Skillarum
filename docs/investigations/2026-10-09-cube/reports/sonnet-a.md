# Investigator report: sonnet-a

## Provenance
- Investigator: Claude Sonnet 5.5 (`claude-sonnet-5-5`), working alone.
- Date: 2026-10-09.
- Skill version read: math4wisdom-cube 0.1.0.
- Inputs: `references/investigator-protocol.md`, `references/sources.md` S1–S6 (phase 1), then SKILL.md, mathematics.md, interpretations.md, sources.md S7–S8 and `scripts/verify_combinatorics.py` output. I also fetched the wiki pages Research/Overview and Research/Triality. I wrote no files into the repo; scratch code is in `$TMPDIR`.
- Phase-order honesty: I wrote the blind reconstruction in my reasoning before opening SKILL.md, mathematics.md or interpretations.md. I did not see those files first. I then read them together with the S7–S8 section in one tool call, so everything after section 1 is informed by them.
- Shared with other investigators: the same brief and skill files, and probably the same model lineage. I have not seen any other report.

## 1. Blind reconstruction (E1 observation)
- **Structure:** I would use the cube as the face lattice of {0,1,*}³. Vertices are the 8 three-bit strings, edges are the 12 strings with one `*` (3×4), and faces are the 6 strings with two `*` (3×2). S1 itself calls the match a "coincidence", so the counts are the only input.
- **Languages:** I would pair them with the three pairwise incidence relations. Verbalization (8→12) is vertex-edge, argumentation (12→6) is edge-face, and narration (6→8) is face-vertex. The counts 24 = 8×3 = 12×2 = 6×4 are the fan-outs 3, 2, 4. I did not see any reason to pair them differently.
- **Persons:** The four persons sit on the four vertices of one inscribed tetrahedron (the other four are its antipodes). The six pairs of persons then correspond to the six faces, because each tetrahedron edge is a face diagonal. The choice of tetrahedron and the labelling are free, and I expected nothing canonical about which person is which.

## 2. Verification
- **Skill script (computation):** `verify_combinatorics.py` returned `ok: true` for M1–M18.
- **M7 (computation):**
  - All 12 cube edges map to 12 distinct ordered pairs of persons.
  - The 6 faces map to 6 distinct unordered pairs, using A-edge labels. M5 and M7 are confirmed.
- **M15 (computation, exact `Fraction` arithmetic):**
  - T is orthogonal.
  - T maps 8_v→8_o, 8_e→8_v and 8_o→8_e, a 3-cycle on the three sets.
  - T³ = I.
  - T also preserves the 24 vectors ±e_i±e_j, so it is a genuine symmetry of the root system and not only of the weight set.
- **M17 (reasoning plus computation):**
  - Reasoning: the 1+6+1 pattern forces c to be a multiple of e_k, and then both half-spin sets split 4+4. I re-derived this; it needs the middle value to be 0 because the value set is symmetric.
  - Computation: I scanned 390,624 directions with half-integer coordinates in [−6,6]⁴ and found no counterexample, which is a wider net than the skill's integer search in [−4,4]⁴.
  - I found no counterexample to M17.
- **M10 and M9 (computation, rotation group):**
  - Stabilizers on edges and faces have the orders the skill states.
  - Under the 24-element group of proper symmetries of the cube, simple transitivity on the three incidence sets holds.
- **Check I believe the skill gets subtly wrong (computation):**
  - **Rotations do not act on the person labelling as the skill implies.**
    - I labelled A by persons and B by antipodal persons, per M5 and M7, and tested the person-permutation action of each symmetry.
    - Under the 12 odd-permutation rotations, the M5/M7 identifications are not equivariant: 144 edge cases and 72 face cases failed.
    - Reason: an odd rotation swaps tetrahedra A and B. This reverses the ordered pair on edges and replaces a pair by its complement on faces.
    - Under T_d (the 24 symmetries preserving A), the identifications are fully equivariant, with 0 failures.
    - But T_d has vertex orbits of size 4, so the orbit-stabilizer computation 24/3 = 8 (M9) cannot be carried out in T_d.
  - So "the rotations are S4 acting on persons" (M8) and "the static tables are orbits of person-permutations" (I3) use two different S4s. Each works, but not simultaneously with the M5/M7 identifications.

## 3. Identification audit

| Item | Classification | Evidence | Note |
|---|---|---|---|
| Table: vertices 8 ↔ divisions | numerical only | S1 "by coincidence" | The Overview page fetch confirms the word. |
| Table: vertices ↔ persons on A, antipodes on B | canonical given a choice | M7 | The choices are the tetrahedron A and the labelling. 8 divisions = 4 persons × 2 sheets, which is not rotation-invariant (X-sonnet-a-1). |
| Table: edges 12 ↔ circumstances | numerical only | S1, S2, S6 | |
| Table: edges ↔ ordered pairs | canonical given a choice | M7 | The choices are A and the antipodal labelling of B. Not rotation-equivariant for odd rotations (X-sonnet-a-1). |
| Table: faces 6 ↔ conceptions | numerical only | S1 | |
| Table: faces ↔ unordered pairs | canonical given a choice | M5 | The choice of B instead of A gives the complement map. Skill states this. |
| Table: axes 3 ↔ pairings | canonical given a choice | M6 | The only choice is the labelling; the result is independent of A versus B (X-sonnet-a-2, by reasoning). |
| Table: rotations 24, listed under "Wondrous Wisdom name (S2)" | unsupported | S2, I3 | S2 states no group. This is the skill's own I3 reading, placed in a column headed S2. |
| Table: rotations ↔ permutations of persons | canonical given a choice | M8 | The diagonal action is fine. It is not compatible with the M5/M7 labelling for odd elements (X-sonnet-a-1). |
| Three languages ↔ passages between tables (directed) | forced (by the quoted text) | S2 | Fetched page: "argumentation taking us from 12 topologies to 6 representations" etc. |
| Languages ↔ incidence relations (I2) | numerical only | S2, S6, M2 | See section 6: the sources do not say this. |
| SKILL.md "Daniel's question (S5) has a yes answer" (M4) | unsupported | S5, M4 | Daniel asked whether two tetrahedra "stabilize the cube". M4 proves only the parity split, not stabilization. |
| I1 | numerical only | S1 | |
| I2, proposer "Andrius (S2, directed)" | wrong (attribution) | S2, S6 | S2 does not assign languages to incidence relations. |
| I3 | canonical given a choice | M8–M9 | Open as the skill says, but see the non-equivariance caveat. |
| I4 | forced (as stated) | M-level reasoning | A cycle is not supplied by the cube. Correct as the skill states it. |
| I5, Zoas "proposed by Daniel and Synesis ... (S5, S6)" | unsupported | S5, S6 | Neither the S5 quotation nor the S6 quotations in the ledger mention the Zoas. |
| I6 | canonical given a choice (partly constrained) | M16, M17 | The skill's claim "not in conflict" holds only for the Spirit assignment (see section 6). |
| I6, "S4 ... Andrius" attribution | unsupported | S4 | The fetched Triality page notes are unattributed on the page. |
| I7 | numerical only | M15 | Correctly marked open. |
| I8, "Daniel's Fourfold Vision result (... an atlas of views does)" | unsupported | S5 | The S5 quote only says "no single perspective can view all four sides of the Tet at once". |
| C2 (a fourth bit gives a 4-cube, not a tetrahedron) | canonical given a choice | M12 | See section 6 on the competing reading of "bit". |
| M14 note (source slip 48 vs 192) | forced | Triality page | Page does say "2^(n-1) n! = 48". For n = 4 the formula gives 192 and 48 would be n = 3. |

## 4. Discriminating consequences

**D1. Cubic-graph test on the 8 divisions.**
- **Test:** If the 12 circumstances are relations between pairs of the 8 divisions, take the graph they form and check whether it is 3-regular, bipartite, of diameter 3, with a unique antipode per vertex. That is Q₃.
- **Which interpretations it separates:** The cube-as-container reading (I1) versus a pure counting match.
- **Outcome:** If the graph is Q₃, the cube is more than a numerology match. If it is another 3-regular graph on 8 vertices, such as the Wagner graph (non-bipartite), then 8·3 = 24 is only the handshake sum 2E and I1 is merely numerical. The 24 = 2E equality holds for any structure with 12 edges.
- **Status:** This needs the wiki's actual lists of the 8 divisions and 12 topologies and what pairs them. I have not done it.

**D2. Fan-out signature of the languages.**
- **Test:** For each language, record from worked examples whether it is a set-valued relation or a function, and its fan-out.
  - Verbalization: 3 circumstances per division.
  - Argumentation: 2 conceptions per circumstance.
  - Narration: 4 divisions per conception.
- **Which interpretations it separates:** Incidence relation (I2) versus quotient maps (S2's factors 24/2 = 12, 24/3 = 8, 24/4 = 6 read as fibre sizes 2, 3, 4).
- **Outcome:** Observed fan-outs of exactly 3, 2, 4, possibly with multiple outputs per input, favour incidence. Single-valued maps with uniform fibres favour a quotient/coset reading.
- **Relation to E2:** E2 asks for examples. D2 pins down what to measure in them.

**D3. Cube-intrinsic gradings (mathematical consequence, computed).**
- **Claim:** The three patterns Father 4+4, Son 1+3+3+1, Spirit 1+6+1 all occur on the 3-cube's vertex set by three intrinsic gradings.
  - Parity (the A|B split) gives 4+4.
  - Hamming distance from a vertex gives 1+3+3+1.
  - A body diagonal's two ends versus the remaining six gives 1+6+1. The six form a skew hexagon, since each has exactly 2 neighbours among them.
- **Which interpretations it separates:** The Spin(8) weight-grading reading of Father/Son/Spirit (which M17 obstructs) versus a reading inside the cube.
- **Outcome:** If the theology needs all three patterns on one object, the cube reading satisfies it while the Spin(8) reading cannot with one grading. Whether the two readings are related is untested.
- **Note:** The 1+6+1 pattern is relative to the choice of one body diagonal, so the choice of one person.

## 5. My additions

| ID | Tag | Statement | Basis |
|---|---|---|---|
| X-sonnet-a-1 | M | The proper-rotation group (≅S4 via body diagonals) acts non-equivariantly on the M5/M7 person labelling: an odd rotation swaps A and B, reversing ordered pairs on edges and complementing unordered pairs on faces. The equivariant S4 is T_d, but T_d is not transitive on vertices (orbits of size 4), so M9's 24/3 = 8 does not apply to it. | Computation: 144 edge and 72 face failures for rotations, 0 for T_d. |
| X-sonnet-a-2 | M | The axis ↔ pairing bijection of M6 is the same whether A or B is used to label. | Reasoning only (opposite faces carry complementary pairs on both tetrahedra). |
| X-sonnet-a-3 | M | On 8_s the Son's grading (1,1,1,0) gives 1+3+3+1 and the Spirit's (1,1,1,1) gives 1+6+1. The second is a coarsening of the first (levels 1 and 2 merged), since the fourth coordinate's sign is the product of the other three. | Computation (M16 shows both rows; I added the coarsening observation). |
| X-sonnet-a-4 | M | M17 holds on all 390,624 half-integer directions in [−6,6]⁴ checked, in addition to the proof. | Computation. |
| X-sonnet-a-5 | M | T of M15 has order 3 as a matrix and preserves the 24 roots ±e_i±e_j. | Computation. |
| X-sonnet-a-6 | M | The cube's three patterns occur by parity, vertex-distance and diagonal-ends gradings (D3). | Computation. |
| X-sonnet-a-7 | I | 4+4 in the cube's own vertex set is the A|B tetrahedra split, so "Father sees 4+4" can be read as seeing both tetrahedra. | Reasoning. |
| X-sonnet-a-8 | E | D1: Q₃ versus other cubic graphs on the 8 divisions. | Section 4. |
| X-sonnet-a-9 | E | D2: fan-out signature (3, 2, 4) versus fibre sizes. | Section 4. |
| X-sonnet-a-10 | E | D3 as a test of whether the cube readings relate to Spin(8) readings. | Section 4. |

## 6. Disagreements with the skill

1. **SKILL.md overclaims where the sources say less.**
   - It says "Which language goes with which incidence relation is stated by the source (`S2`)" under I1–I3. The fetched Overview page only gives the tables the languages connect, and the page does not mention incidence or tetrahedra at all. The incidence pairing comes from the skill/Synesis (S6, undirected).
   - I2 lists "Andrius (S2, directed)" as proposer of the incidence pairing. That attribution is wrong.
2. **Rotations row of the table.** Rotations appear under "Wondrous Wisdom name (S2)", but S2 names no group. The reading is I3, proposed by the skill.
3. **M8/M9/I3 versus M5/M7.** They use two different S4 actions (X-sonnet-a-1). I3's "a conception is fixed by a 4-cycle" happens to work for face stabilizers, but the underlying identification fails equivariance for odd rotations.
4. **M16 and I6 "not in conflict".** The reconciliation of S4 and S3 holds only for Spirit = vector = 1+6+1 (c = (0,0,0,1)). In that row the Son is 4+4, not S3's 1+3+3+1. The conflict on the Son remains, as M17 implies.
5. **"Daniel's question has a yes answer" (SKILL.md, M4).** M4 proves two disjoint regular tetrahedra whose union is the cube. It does not show that they "stabilize" the cube, which was Daniel's wording.
6. **I5 and I8 attributions** (Zoas, atlas of views) are not supported by the quoted S5/S6 text in the ledger. The ledger would need to quote them.
7. **C2 may be too quick.**
   - A tetrahedron is also the even-parity subset of the 3-cube: three bits plus one dependent parity bit. Four-bit even-parity strings number 8 and split 1+6+1 by weight, the Spirit's pattern.
   - So S3's "God introduces a fourth bit and makes for a tetrahedron" can be read with the fourth bit being determined. The skill's correction fits only the independent-bit reading.
8. **M10 is true but nearly vacuous.** Any three regular G-sets are isomorphic, so "same 24" says little about the languages.
