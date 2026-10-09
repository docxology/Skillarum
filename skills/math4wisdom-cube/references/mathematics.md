# Mathematics ledger (`M`)

Each item states a result, gives a proof or a standard reference, and names
the check in `scripts/verify_combinatorics.py` that recomputes it. A failing
check means this file is wrong.

Conventions. The cube's vertices are binary triples `(x, y, z) ∈ {0,1}³`.
Two vertices share an edge when they differ in one coordinate. A face fixes
one coordinate. Tetrahedron A is the even-weight vertices
`000, 011, 101, 110`; tetrahedron B is the odd-weight vertices
`111, 100, 010, 001`. The antipode of `v` is `1 − v`.

## M1 — Counts

8 vertices, 12 edges (`8 · 3 / 2`), 6 faces (`3 axes × 2 sides`).
`8 − 12 + 6 = 2`.

## M2 — Three incidence relations of size 24

| Relation | Count from the left | Count from the right |
| --- | --- | --- |
| vertex–edge | 8 vertices × 3 edges | 12 edges × 2 vertices |
| vertex–face | 8 vertices × 3 faces | 6 faces × 4 vertices |
| edge–face | 12 edges × 2 faces | 6 faces × 4 edges |

Full flags (vertex ⊂ edge ⊂ face) number `8 · 3 · 2 = 48`.

## M3 — Correction to S6

S6 calls `24 = 8 × 3 = 12 × 2 = 6 × 4` three counts of the edge-face
incidences. Edge-face incidences are counted by `12 × 2` and `6 × 4` only;
`8 × 3` counts vertex-edge or vertex-face incidences. Each pair of ranks has
its own 24 (M2). M10 gives the sense in which they are nevertheless "the
same".

## M4 — Two tetrahedra

Two even-weight triples differ in exactly two coordinates, so their squared
distance is 2; likewise for odd. Hence A and B are regular tetrahedra of edge
`√2`, disjoint, with union the cube's vertex set. This is the stella
octangula answer to S5.

## M5 — Faces ↔ unordered pairs

Each face is a square whose two diagonals join vertices of equal parity, so
each face contains exactly one edge of A and one edge of B. A has 6 edges and
the cube 6 faces, so this is a bijection. Labelling A's vertices
God, I, You, Other indexes the faces by the six unordered pairs, with no
further choice (S6 says "once we choose one of the two tetrahedra and a
consistent labeling"; M5 shows the face indexing needs no choice beyond
that).

## M6 — Axes ↔ pairings

Opposite faces contain opposite (skew) edges of A, which use complementary
pairs of labels. So the cube's 3 axes correspond to the 3 ways to split
{God, I, You, Other} into two pairs: {God, I | You, Other},
{God, You | I, Other}, {God, Other | I, You}.

## M7 — Edges ↔ ordered pairs; vertices ↔ persons and antipodes

Label each vertex of B by the label of its antipode in A (each body diagonal
joins a person to its antipodal copy). A cube edge joins `a ∈ A` and
`b ∈ B`. Write `b = antipode(c)` with `c ∈ A`. Then `d(a, b) = 3 − d(a, c)`,
so `a, b` are adjacent exactly when `d(a, c) = 2`, i.e. when `c ≠ a`. Hence
each edge is an ordered pair `(a, c)` of distinct persons and all 12 occur.
The face for the unordered pair `{X, Y}` contains the four edges
`(X, Z), (X, W), (Y, Z), (Y, W)` where `{Z, W}` is the complement.

## M8 — Rotations are permutations of the persons

The cube has 48 symmetries (signed permutation matrices), 24 of them
rotations. Rotations permute the 4 body diagonals, and the induced map to S4
is an isomorphism (standard; the check recovers all 24 permutations). Since
each diagonal carries one person (M7), every rotation is a permutation of
God, I, You, Other and every permutation is a rotation. The 12 rotations
preserving each tetrahedron are the even permutations (A4); the 24
symmetries preserving each tetrahedron form the tetrahedral group T_d ≅ S4.

Consequence: the cube's symmetry treats the four persons as interchangeable.
Distinguishing them (S3) needs structure the cube does not have.

## M9 — Orbit-stabilizer: 24/3, 24/2, 24/4

The rotation group (order 24) acts transitively on vertices, edges, and
faces, with stabilizers of order 3 (rotations about a body diagonal), 2
(half-turn about an edge-midpoint axis), and 4 (quarter-turns about a face
axis). So `8 = 24/3`, `12 = 24/2`, `6 = 24/4`, which is S2's arithmetic. In
the persons reading (M8), a vertex stabilizer fixes one person and cycles the
other three, an edge stabilizer is a transposition, and a face stabilizer is
a 4-cycle.

S2's further factors, `12 = 3 × 4`, `8 = 4 × 2`, `6 = 2 × 3`, are products of
the other two stabilizer orders, since `24 = 2 · 3 · 4`.

## M10 — One 24, three copies

The rotation group acts simply transitively on each of the vertex-edge,
vertex-face, and edge-face incidence sets (each orbit has 24 elements and
the group has order 24). After fixing a base incidence, each set is in
bijection with the group, hence with the permutations of the four persons.
This is the precise sense in which S6's "three ways to count the same
incidences" can be repaired: three regular actions of one group.

## M11 — Pascal rows and the exterior algebra

Row 3 is 1, 3, 3, 1 (sum 8); row 4 is 1, 4, 6, 4, 1 (sum 16); `16 + 8 = 24`
(S3). Row 4 by parity: even weights 1+6+1, odd weights 4+4. These are the
dimensions of the even and odd parts of the exterior algebra `ΛW` of a
4-dimensional space `W`.

## M12 — Layers: triangle, tetrahedron, octahedron

The weight-1 and weight-2 layers of the 3-cube are equilateral triangles.
The 4-cube's layers are a point, a regular tetrahedron (4), a regular
octahedron (6, squared distances 2 twelve times and 4 three times), a regular
tetrahedron (4), and a point. So a fourth bit yields a 4-cube (C2); the
tetrahedron is one layer of it, and the octahedron of Fuller's
tetrahedron-octahedron packing is the middle layer.

## M13 — The 24-cell is three 16-cells

The 8 points `±e_i` and the 16 points `(±½, ±½, ±½, ±½)` are the 24 unit
vectors of the 24-cell. They split into three 8-point cross-polytopes
(16-cells): `±e_i`; the half-integer points with an even number of minus
signs; and those with an odd number. These are the weights of the vector
representation `8_v` and the two half-spin representations `8_s`, `8_c` of
Spin(8) (standard; see Baez, "The Octonions", 2002, §2.4, and the Baez
quotation in S4). Dimensional analogy: the 3-cube's parity halves are two
tetrahedra (M4); the tesseract's parity halves (centred) are two 16-cells;
adding `±e_i` gives the third, making the 24-cell. That is S3's `16 + 8`.

## M14 — D4 has 24 roots

`±e_i ± e_j`, `i < j`: `C(4,2) · 4 = 24 = 2 · 4 · 3`. The Research/Triality
page (S4's location) also writes "The Weyl group has order {$2^{(n-1)}n!=
48$}"; for `n = 4` that formula gives `8 · 24 = 192`, the order of W(D4).
Recorded as a probable slip in the source, not computed by the check.

## M15 — An explicit triality map on weights

The matrix

```
T = ½ ⎡ 1  1  1  1⎤
      ⎢ 1  1 −1 −1⎥
      ⎢ 1 −1  1 −1⎥
      ⎣−1  1  1 −1⎦
```

is orthogonal and permutes the three 8-point sets cyclically
(`8_v → 8_c → 8_s → 8_v` in the check's labels). It preserves the 24-cell and
does not preserve any one set, so it lies outside W(D4) and represents the
order-3 element of the diagram symmetry S3 = Out(D4)'s image on weights. This
is triality on weights only. The corresponding maps on the representation
spaces themselves (the "actual triality maps" S8 asks for) are not
constructed here; see I7.

## M16 — Which 8 is 1+6+1 depends on a choice

A one-parameter subgroup is a direction `c` in weight space; it grades each
8 by `⟨w, c⟩`. Three examples:

| c | 8_v | 8_s | 8_c | Subgroup |
| --- | --- | --- | --- | --- |
| (1,1,1,1) | 4+4 | 1+6+1 | 4+4 | centre of U(4); the `ΛW` model |
| (0,0,0,1) | 1+6+1 | 4+4 | 4+4 | Spin(2) in Spin(6)×Spin(2) |
| (1,1,1,0) | 3+2+3 | 1+3+3+1 | 1+3+3+1 | a U(3)-type direction |

So S4 ("the vector representation is the Spirit") and S3 ("Unanims see 1+6+1
which is what the Spirit sees") are compatible: under Spin(6)×Spin(2) the
vector representation is 1+6+1. They describe different symmetry-breakings,
related by T.

## M17 — No single grading gives Father, Son, and Spirit together

Claim: for no direction `c` are the three gradings 4+4, 1+3+3+1, and 1+6+1
in some order.

Proof. Since T is orthogonal, `⟨Tw, Tc⟩ = ⟨w, c⟩`, so replacing `c` by `Tc`
permutes the three patterns. Suppose some 8 is 1+6+1 under `c`; apply T until
that 8 is `8_v`. The values on `8_v` are `±c_1, …, ±c_4`. Six of these eight
values are equal and the other two are distinct and unequal to them, so the
six must be 0 (a nonzero `c_i` contributes the pair `±c_i` with different
values). Hence three of the `c_i` are 0 and `c` is a multiple of some
`e_k`. Then every half-integer weight has `⟨w, c⟩ = ±c_k/2`, four of each,
so `8_s` and `8_c` are both 4+4. Neither is 1+3+3+1. ∎

The check also searches all integer directions in `[−4, 4]⁴` and finds none.

Consequence for I6: a reading needing all three patterns at once needs at
least two different symmetry-breakings, as S8's "further splitting" for the
Son already suggests.

## M18 — The relations among four persons form an octahedron

The line graph of the tetrahedron has one node per pair of persons, with two
nodes adjacent when the pairs share a person. It has 6 nodes and 12 edges,
every node has degree 4, and each node's only non-neighbour is its
complementary pair. That is the octahedron graph K₂,₂,₂, the middle layer of
the 4-cube (M12); its three antipodal pairs are the three pairings of M6.

