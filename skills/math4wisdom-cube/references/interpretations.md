# Interpretation and test ledger (`I`, `E`)

Every entry names its proposer and its status. "Proposer" is who first put
the reading forward in the sources (S-IDs), or "skill 0.1.0" for readings
added by this skill's author (Claude, an Anthropic model, working in Daniel
Friedman's Skillarum session on 2026-10-09). Status is one of:

- **open** — neither supported nor refuted beyond its numerical match;
- **constrained** — some mathematics limits the forms it can take;
- **refuted as stated** — the stated form is false; a repaired form may live
  on as a new entry.

## Interpretations

### I1 — The cube is the right container for the three static tables

Proposer: Andrius (S1), Daniel's question (S5), Synesis (S6).
Status: open.
The source introduces the cube "by coincidence" (S1). M1–M10 show the cube
carries a great deal of structure matching the counts, but matching counts
is all the mathematics establishes. Whether other structures with the
same counts fit the tables as well is part of E1.
What would count as support: a reason, internal to Wondrous Wisdom, why
divisions contain circumstances and circumstances bound conceptions in the
way vertices, edges, and faces do.

### I2 — Each language is one incidence relation

Proposer: Synesis (S6, undirected, explicitly as a hypothesis).
**[0.2.0: 0.1.0 also credited Andrius (S2). S2 states directed passages
between tables, not incidence relations; attribution corrected (forge-b X-10,
sonnet-a §6.1).]**
Status: open.
Argumentation ↔ edge–face, verbalization ↔ vertex–edge, narration ↔
vertex–face. M2 confirms each has 24 elements. Under M10 each is the same
group acting regularly, which makes the three languages structurally
indistinguishable inside the cube. Any difference between them has to come
from outside the cube. **[0.2.0: that holds under the rotation group O. Under
T_d, which respects the person labels, edge–face stays one regular orbit while
the other two split 12+12, so argumentation is distinguished (anvil-c X-2,
M19).]**

### I3 — The 24 in S2 is the rotation group, i.e. permutations of persons

Proposer: skill 0.1.0, from S2's "24/3, 24/2, 24/4" and M8–M9.
Status: constrained (0.2.0). M19: the rotation group O is the S4 for this
reading, but it is not the S4 under which the M5/M7 person labels hold. I3
and the persons column of SKILL.md's table cannot both be read with the same
labels. Under O the natural labels are cyclic structures instead: a vertex is
fixed by a 3-cycle group, an edge by a transposition, a face by a 4-cycle
group (anvil-c X-1).
This reading says the 24 is not an incidence count but the group of ways to
re-assign God, I, You, Other. If right, the static tables are orbits of
person-permutations: a division is fixed by "one person stays, the other
three cycle", a circumstance by a transposition, a conception by a 4-cycle.

### I4 — The languages form a directed cycle 8 → 12 → 6 → 8

Proposer: Andrius (S2, implicit in "taking us from … to …").
Status: constrained.
**[0.2.0: anvil-c X-5 strengthens the first half: composing the three
unoriented incidence relations gives a symmetric operator, so forward and
reverse are identical, and parity is in its kernel. Anvil-c X-6 qualifies the
second half: if each step carries a handedness (a chiral flag), the cube's
Coxeter relations give a holonomy of order 1–4 depending on where the
handedness flips, and orders 3 and 4 distinguish the two directions. Reported
by anvil-c; not recomputed by this skill's checker.]**
The cube's face lattice orders vertices < edges < faces; no symmetry of the
cube permutes the three ranks (their counts differ). So a cycle
vertex → edge → face → vertex is not supplied by the cube. Candidates for what
supplies it: a duality (the cube's dual is the octahedron, which swaps
vertices and faces, 8 ↔ 6, and fixes edges, 12 — an order-2 map, not
order-3); the order-3 triality symmetry (M15) acting on some other triple
of structures. Neither is established.

### I5 — Vertices of the tetrahedron are God, I, You, Other; faces are the
transcendings of body, mind, heart, will

Proposer: Andrius (S3).
Status: constrained by M8.
All 24 permutations of the labels are cube rotations, so nothing in the cube
distinguishes God from I. Andrius's insistence that the labels are not
interchangeable (S3, reported in S6) is therefore an additional input. Blake's
Four Zoas (Tharmas, Urizen, Luvah, Urthona) were connected to the four persons
by Daniel (S9) and proposed by Synesis as closer to "aspects of human life",
and so possibly to the faces rather than the vertices (S9; quotations added
in 0.2.0). The tetrahedron's vertices and faces are dual (vertex ↔ opposite
face), which gives one canonical pairing of each person with one
transcending; which pairing the sources intend is not stated.

### I6 — Father, Son, Spirit are the three 8s of Spin(8) triality

Proposer: Andrius (S3), Synesis (S8); earlier as an unsigned question on the
Research/Triality page of Andrius's wiki (S4).
Status: constrained by M16 and M17.
- S4 asks whether the Spirit is the vector representation; S3 says the
  Spirit sees 1+6+1. M16: both hold under Spin(6)×Spin(2), so they are not
  in conflict about the Spirit. **[0.2.0: in that same frame the Son is 4+4,
  not 1+3+3+1, so the conflict about the Son remains (sonnet-a §6.4).]**
- S3 assigns Father 4+4, Son 1+3+3+1, Spirit 1+6+1. M17: no single
  one-parameter symmetry-breaking produces all three. A reading that needs
  all three needs at least two breakings, and the theology must say what
  each breaking is.
- Triality permutes the three representations (M15). Any assignment that
  privileges one of them (calls it "vector") is a choice of frame, not a
  property of the representation.

- **[0.2.0]** M20 offers a second reading: Father, Son, Spirit as three
  coarsenings of one grading of one 8 (or of the cube from one chosen
  vertex), rather than as three different 8s. M17 obstructs the first
  reading under a single symmetry-breaking and permits the second.

**[0.4.0 supplement to I6: M17 requires exact complete eigenspace patterns
under one grading. The preceding requirement for at least two breakings is
superseded for arbitrary invariant groupings by Synesis's M23: one SL(3, C)
subgroup retains all three selected groupings on different 8s. Its complete
branching is the same `1+1+3+3*` on each. This does not prove that triality
preserves those groupings or the theological interpretation.]**

### I7 — Theological operations are preserved by the triality maps

Proposer: Synesis (S8).
Status: open; the maps on representation spaces are not yet constructed in
this skill. M15 is the shadow on weights. A full test would write the
triality automorphism of Spin(8) (for instance via octonion multiplication,
`V × S₊ → S₋`), state what operation each person performs as a map between
representations, and check equivariance.

### I8 — Unanims see the six edges and the centre but not the vertices or
faces

Proposer: Andrius (S3).
Status: open.
Mathematical note: the 6 edges of a tetrahedron are the 6 unordered pairs,
the same as the cube's faces (M5). If each edge is seen with its labelled
endpoints, the vertices are recovered, so "seeing the edges but not the
vertices" must mean seeing the relations without their relata. The natural
model is the line graph of the tetrahedron: one node per relation, two nodes
adjacent when the relations share a person. That graph is the octahedron
(K₂,₂,₂), the middle layer of the 4-cube in M12, and each node's unique
non-neighbour is its complementary pair (M6, M18). This is skill 0.1.0's
addition. Daniel's
Fourfold Vision result (no exterior viewpoint shows all four faces, S5; an
atlas of views does, in Synesis's summary, S10) is a different, geometric
limitation. The octahedron reading is a model choice, not exegesis
(forge-b §3).

### I9 — Persons on a God-centred claw (added in 0.2.0)

Proposer: anvil-c (X-3), from S3's arithmetic. Status: open.
Instead of a parity tetrahedron, delete God's bit from the 4-bit odd layer.
God then sits at a vertex adjacent to I, You, and Other, the Hamming layers
are {God} | {I, You, Other} | {transcendings of I, You, Other} | {transcending
of God}, and the 1+3+3+1 split singles out God, matching S8's further
splitting W = L ⊕ U with L as God's line. Under this placement God is
structurally distinguished, which bears on E3.

### I10 — Which symmetry group the theology uses (added in 0.2.0)

Proposer: all three investigators converge (M19). Status: open.
If persons and their transcendings are not interchangeable, the relevant
group is T_d, the divisions split 4+4 inside the cube (the Father's pattern),
and the languages are no longer interchangeable. If they are interchangeable,
the group is O, the languages are indistinguishable, and the natural labels
are 3-cycles (vertices), transpositions (edges), and 4-cycles (faces), not
pairs of persons.

## Proposed observations and consequences (`E`)

These would discriminate among the interpretations. None has been carried
out.

### E1 — Blind reconstruction

**[0.2.0: in the 2026-10-09 run the blind phase included S1, S3, S5, and S6,
which already name the cube, tetrahedra, and incidences, so convergence was
weak evidence (forge-b X-9). From 0.2.0 the blind phase uses
`references/blind-brief.md`, which states counts and languages only.]**
Give an investigator only the counts and the three directed languages (no
cube). Record whether it proposes the cube, what else it proposes, and how
it pairs languages with incidences. If several independent investigators
converge on the cube and on I2's pairing without being shown it, that is
evidence the correspondence is not only post hoc. If they diverge, the
divergence is the result.

### E2 — Directed-cycle test (for I4)

Ask the source author for three concrete examples of each language with
their input and output. If an example of narration maps one conception to a
division contained in that conception's face, the cube's incidence explains
it; if not, I2 is under strain.

### E3 — Person asymmetry (for I5)

Find a statement in Wondrous Wisdom true of (God, I) and false of (You,
Other). Any such statement is structure the cube lacks (M8) and fixes which
symmetry-breaking the theology uses. If none exists, the claim that the
labels are not interchangeable has no structural content in this model.

### E4 — Seed Crystal comparison (S11, S8)

Andrius proposed three modes for an AI collaborator: answer as usual; learn
Wondrous Wisdom's structural language, then answer; compare and choose.
Record all three outputs for a fixed set of questions, with this skill as
the structural language, and rate (blind to mode) which answers make
distinctions the others miss. This tests whether the structure does work in
reasoning rather than decorating it, Synesis's own criterion (S6, section 4).

### E5 — Group test: pairs or cycles (added in 0.2.0)

From forge-b E-B and anvil-c D1. Ask whether a conception in Wondrous Wisdom
is a pair of persons with its complement (favours T_d and the M5 labels) or a
cyclic order of all four (favours O and 4-cycle labels), and whether
divisions come as 4 persons + 4 transcendings or as 4 triads × 2
orientations. Separates I3 from the persons column; see I10.

### E6 — Holonomy of the language cycle (added in 0.2.0)

From anvil-c D2. Take three worked source examples, one per language, chained
round the cycle. Returning to the start favours unoriented incidence;
returning changed with period 3 selects a handedness flip at the divisions;
landing on the antipode refutes the incidence model.

### E7 — Adjacency of God and I (added in 0.2.0)

From anvil-c D3. Does any single circumstance relate God and I directly? A
yes favours the God-centred claw (I9); a no favours the parity tetrahedron,
under which no two persons are adjacent.

### E8 — Three 8s or three coarsenings (added in 0.2.0)

From forge-b E-C and sonnet-a D3, via M17 and M20. Do Father, Son, and Spirit
act on different spaces (three 8s permuted by triality) or give three views of
one space? Count the independent symmetry-breakings the theology names: M17
needs at least two for the first reading; M20 needs one for the second.

**[0.4.0 supplement to E8: distinguish three requirements before collecting
examples: M17's complete eigenspaces under one grading; M23's selected
invariant groupings on three spaces under one subgroup; M20's coarsenings
of one space. Counting breakings alone does not separate all three.]**

### E9 — Cubic-graph test on the divisions (added in 0.2.0)

From sonnet-a D1. If circumstances relate pairs of divisions, build that
graph from the source lists. If it is Q₃ (bipartite, diameter 3, unique
antipodes) the cube is more than a count; another cubic graph on 8 vertices
(such as the Wagner graph) would reduce I1 to a handshake identity.

## New interpretation and tests (0.4.0)

### I11 — Languages as completion of transverse triples (added in 0.4.0)

Proposer: Synesis (S13). Status: open. M22 supplies unique completion of
compatible pairs. Whether completing the third component models the framing
and direction of Andrius's languages needs source examples (E10). This is a
new proposal, not a silent replacement of I2's ordinary incidence relations.

### E10 — Semantic completion and incompatible pairs (added in 0.4.0)

Ask Andrius for worked examples of each language, identifying two given
components, the missing component, and what frames the transition. Predeclare
the mapping to v,e,f. Include incompatible pairs: a contained edge-face pair
must have no transverse completion; an edge meeting a face at one endpoint
must have exactly one. Record disagreements rather than relabelling after
seeing results. Unique mathematical completion does not supply semantic
direction, introspective correctness, or a privileged theological label.

### E11 — Triality compatibility of selected groupings (added in 0.4.0)

State the common subgroup embedding, polarization W, line L, and blocks.
Construct representation-space intertwiners twisted by an explicit triality
automorphism, specifying its action on the subgroup; test which blocks map
to which and whether dimensions and operations are preserved. M15's weight
permutation and M23's equal restricted characters alone do not settle this.
Record any additional choices. No such test has been completed here.

