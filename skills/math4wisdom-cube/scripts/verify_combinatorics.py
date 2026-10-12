#!/usr/bin/env python3
"""Recompute every mathematical claim in the math4wisdom-cube skill.

Standard library only. Each check has a stable id (M1, M2, ...) that the
skill's references cite. Run it, read the JSON, and treat any ``false`` as a
defect in the skill rather than in the mathematics.

    python3 scripts/verify_combinatorics.py          # JSON report, exit 1 on failure
    python3 scripts/verify_combinatorics.py --brief  # one line per check
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from fractions import Fraction
from itertools import combinations, permutations, product

PERSONS = ("God", "I", "You", "Other")
HALF = Fraction(1, 2)

# --------------------------------------------------------------------------
# The 3-cube as a combinatorial object on binary triples
# --------------------------------------------------------------------------

VERTICES = tuple(product((0, 1), repeat=3))


def hamming(a, b):
    return sum(x != y for x, y in zip(a, b))


EDGES = tuple(
    frozenset((a, b)) for a, b in combinations(VERTICES, 2) if hamming(a, b) == 1
)
# A face fixes one coordinate to one value.
FACES = tuple(
    frozenset(v for v in VERTICES if v[axis] == value)
    for axis in range(3)
    for value in (0, 1)
)


def face_axis(face):
    for axis in range(3):
        if len({v[axis] for v in face}) == 1:
            return axis
    raise ValueError("not a face")


def sq_dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b))


EVEN = tuple(v for v in VERTICES if sum(v) % 2 == 0)  # tetrahedron A
ODD = tuple(v for v in VERTICES if sum(v) % 2 == 1)  # tetrahedron B


def antipode(v):
    return tuple(1 - x for x in v)


# Symmetries: signed permutation matrices acting on centred coordinates.
def _apply(matrix, v):
    centred = [2 * x - 1 for x in v]
    image = [sum(matrix[i][j] * centred[j] for j in range(3)) for i in range(3)]
    return tuple((x + 1) // 2 for x in image)


def _det3(m):
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def cube_symmetries():
    out = []
    for perm in permutations(range(3)):
        for signs in product((1, -1), repeat=3):
            m = [[0] * 3 for _ in range(3)]
            for i, j in enumerate(perm):
                m[i][j] = signs[i]
            out.append(m)
    return out


SYMMETRIES = cube_symmetries()
ROTATIONS = [m for m in SYMMETRIES if _det3(m) == 1]


def vertex_map(m):
    return {v: _apply(m, v) for v in VERTICES}


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------


def check(results, cid, claim, ok, **evidence):
    results.append({"id": cid, "claim": claim, "ok": bool(ok), "evidence": evidence})


def cube_checks(results):
    check(
        results,
        "M1",
        "The 3-cube has 8 vertices, 12 edges, 6 faces; Euler characteristic 2.",
        (len(VERTICES), len(EDGES), len(FACES)) == (8, 12, 6)
        and len(VERTICES) - len(EDGES) + len(FACES) == 2,
        counts=[len(VERTICES), len(EDGES), len(FACES)],
    )
    ve = sum(1 for v in VERTICES for e in EDGES if v in e)
    vf = sum(1 for v in VERTICES for f in FACES if v in f)
    ef = sum(1 for e in EDGES for f in FACES if e <= f)
    flags = sum(1 for v in VERTICES for e in EDGES for f in FACES if v in e and e <= f)
    check(
        results,
        "M2",
        "Three distinct incidence relations each have 24 elements: "
        "vertex-edge 8x3=12x2, vertex-face 8x3=6x4, edge-face 12x2=6x4; flags 48.",
        (ve, vf, ef, flags) == (24, 24, 24, 48),
        vertex_edge=ve,
        vertex_face=vf,
        edge_face=ef,
        flags=flags,
    )
    check(
        results,
        "M3",
        "Correction: 8x3 does not count edge-face incidences. The triple equation "
        "24 = 8x3 = 12x2 = 6x4 holds numerically, but its three products count "
        "three different incidence relations (or, see M8, one group order).",
        ef == 12 * 2 == 6 * 4 and ve == 8 * 3 and vf == 8 * 3,
        edge_face_as_8x3=False,
    )
    tet_ok = all(sq_dist(a, b) == 2 for a, b in combinations(EVEN, 2)) and all(
        sq_dist(a, b) == 2 for a, b in combinations(ODD, 2)
    )
    check(
        results,
        "M4",
        "Splitting vertices by coordinate-sum parity gives two disjoint regular "
        "tetrahedra (all six pairwise squared distances 2) whose union is the cube.",
        tet_ok and set(EVEN) | set(ODD) == set(VERTICES) and not set(EVEN) & set(ODD),
        even=[list(v) for v in EVEN],
        odd=[list(v) for v in ODD],
    )
    tet_a_edges = [frozenset(p) for p in combinations(EVEN, 2)]
    tet_b_edges = [frozenset(p) for p in combinations(ODD, 2)]
    per_face_a = [sum(1 for e in tet_a_edges if e <= f) for f in FACES]
    per_face_b = [sum(1 for e in tet_b_edges if e <= f) for f in FACES]
    check(
        results,
        "M5",
        "Every tetrahedron edge is a face diagonal, and each cube face contains "
        "exactly one edge of each tetrahedron: a canonical bijection between "
        "the 6 unordered pairs of 4 labels and the 6 faces.",
        per_face_a == [1] * 6 and per_face_b == [1] * 6,
        edges_of_A_per_face=per_face_a,
        edges_of_B_per_face=per_face_b,
    )
    label = dict(zip(EVEN, PERSONS))
    face_pair = {}
    for f in FACES:
        (edge,) = [e for e in tet_a_edges if e <= f]
        face_pair[f] = frozenset(label[v] for v in edge)
    axis_matchings = []
    for axis in range(3):
        opposite = [face_pair[f] for f in FACES if face_axis(f) == axis]
        axis_matchings.append(sorted(sorted(p) for p in opposite))
    matchings_ok = all(
        len(m) == 2 and set(m[0]) | set(m[1]) == set(PERSONS) for m in axis_matchings
    )
    check(
        results,
        "M6",
        "Opposite faces carry complementary pairs, so the 3 axes of the cube are "
        "the 3 ways to split the 4 labels into two pairs.",
        matchings_ok,
        axes=axis_matchings,
    )
    edge_relation = {}
    for e in EDGES:
        a, b = sorted(e, key=lambda v: sum(v) % 2)
        source = label[a]
        target = label[antipode(b)]
        edge_relation[e] = (source, target)
    ordered_pairs = sorted(edge_relation.values())
    check(
        results,
        "M7",
        "Labelling tetrahedron B by antipodes (each body diagonal joins a label "
        "to its antipodal copy), the 12 cube edges are exactly the 12 ordered "
        "pairs of distinct labels; the 8 vertices are the 4 labels and their "
        "antipodal copies.",
        sorted(set(ordered_pairs)) == sorted(permutations(PERSONS, 2))
        and len(ordered_pairs) == 12,
        edges_as_ordered_pairs=[list(p) for p in ordered_pairs],
    )


def group_checks(results):
    diagonals = [frozenset((v, antipode(v))) for v in EVEN]

    def diagonal_perm(m):
        vm = vertex_map(m)
        return tuple(diagonals.index(frozenset(vm[v] for v in d)) for d in diagonals)

    perms = {diagonal_perm(m) for m in ROTATIONS}
    preserving = [m for m in ROTATIONS if {vertex_map(m)[v] for v in EVEN} == set(EVEN)]
    full_preserving = [
        m for m in SYMMETRIES if {vertex_map(m)[v] for v in EVEN} == set(EVEN)
    ]
    check(
        results,
        "M8",
        "The cube has 48 symmetries and 24 rotations; the rotations act on the 4 "
        "body diagonals as all 24 permutations (S4), so with diagonals labelled "
        "God, I, You, Other every rotation is a permutation of the four labels.",
        len(SYMMETRIES) == 48 and len(ROTATIONS) == 24 and len(perms) == 24,
        symmetries=len(SYMMETRIES),
        rotations=len(ROTATIONS),
        distinct_diagonal_permutations=len(perms),
        rotations_preserving_each_tetrahedron=len(preserving),
        symmetries_preserving_each_tetrahedron=len(full_preserving),
    )

    def orbit_stab(items, act):
        sizes = []
        for x in items:
            stab = sum(1 for m in ROTATIONS if act(m, x) == x)
            orbit = {act(m, x) for m in ROTATIONS}
            sizes.append((len(orbit), stab))
        return sorted(set(sizes))

    act_v = lambda m, v: vertex_map(m)[v]  # noqa: E731
    act_e = lambda m, e: frozenset(vertex_map(m)[v] for v in e)  # noqa: E731
    act_f = lambda m, f: frozenset(vertex_map(m)[v] for v in f)  # noqa: E731
    os_v, os_e, os_f = (
        orbit_stab(VERTICES, act_v),
        orbit_stab(EDGES, act_e),
        orbit_stab(FACES, act_f),
    )
    check(
        results,
        "M9",
        "Orbit-stabilizer for the 24 rotations: vertices 8 = 24/3, edges "
        "12 = 24/2, faces 6 = 24/4. This reproduces the source's 24/3, 24/2, "
        "24/4 as one group order divided by three stabilizer orders.",
        os_v == [(8, 3)] and os_e == [(12, 2)] and os_f == [(6, 4)],
        vertices=os_v,
        edges=os_e,
        faces=os_f,
    )

    def regular(pairs, act):
        orbit = {act(m, pairs[0]) for m in ROTATIONS}
        return len(orbit) == len(pairs) == 24

    ve = [(v, e) for v in VERTICES for e in EDGES if v in e]
    vf = [(v, f) for v in VERTICES for f in FACES if v in f]
    ef = [(e, f) for e in EDGES for f in FACES if e <= f]
    act_ve = lambda m, p: (act_v(m, p[0]), act_e(m, p[1]))  # noqa: E731
    act_vf = lambda m, p: (act_v(m, p[0]), act_f(m, p[1]))  # noqa: E731
    act_ef = lambda m, p: (act_e(m, p[0]), act_f(m, p[1]))  # noqa: E731
    check(
        results,
        "M10",
        "The rotation group acts simply transitively on each of the three "
        "24-element incidence sets, so each is a copy of the same 24-element "
        "group once a base incidence is chosen. In that precise sense the three "
        "products in M2 do count 'the same 24'.",
        regular(ve, act_ve) and regular(vf, act_vf) and regular(ef, act_ef),
        orbit_sizes={
            name: len({act(m, pairs[0]) for m in ROTATIONS})
            for name, pairs, act in (
                ("vertex_edge", ve, act_ve),
                ("vertex_face", vf, act_vf),
                ("edge_face", ef, act_ef),
            )
        },
    )


def _cycle_type(perm):
    seen, lengths = set(), []
    for start in range(len(perm)):
        if start in seen:
            continue
        length, x = 0, start
        while x not in seen:
            seen.add(x)
            x = perm[x]
            length += 1
        lengths.append(length)
    return tuple(sorted(lengths, reverse=True))


def two_groups_checks(results):
    """Rotations O versus the tetrahedral group T_d acting on the persons."""
    label = dict(zip(EVEN, range(4)))

    def person_perm(m):
        vm = vertex_map(m)
        perm = [0] * 4
        for v in EVEN:
            image = vm[v]
            perm[label[v]] = label[image if image in label else antipode(image)]
        return tuple(perm)

    def edge_label(e):
        a, b = sorted(e, key=lambda v: sum(v) % 2)
        return (label[a], label[antipode(b)])

    def face_label(f):
        (edge,) = [frozenset(p) for p in combinations(EVEN, 2) if frozenset(p) <= f]
        return frozenset(label[v] for v in edge)

    def failures(group):
        bad_edges = bad_faces = 0
        for m in group:
            vm, pi = vertex_map(m), person_perm(m)
            for e in EDGES:
                x, y = edge_label(e)
                if edge_label(frozenset(vm[v] for v in e)) != (pi[x], pi[y]):
                    bad_edges += 1
            for f in FACES:
                if face_label(frozenset(vm[v] for v in f)) != frozenset(
                    pi[x] for x in face_label(f)
                ):
                    bad_faces += 1
        return bad_edges, bad_faces

    td = [m for m in SYMMETRIES if {vertex_map(m)[v] for v in EVEN} == set(EVEN)]
    minus = lambda m: [[-x for x in row] for row in m]  # noqa: E731
    keys = lambda ms: {str(m) for m in ms}  # noqa: E731
    td_orbits = sorted(len({vertex_map(m)[v] for m in td}) for v in (EVEN[0], ODD[0]))
    stab_types = {}
    for name, items, act in (
        ("vertex", VERTICES, lambda m, v: vertex_map(m)[v]),
        ("edge", EDGES, lambda m, e: frozenset(vertex_map(m)[v] for v in e)),
        ("face", FACES, lambda m, f: frozenset(vertex_map(m)[v] for v in f)),
    ):
        x = items[0]
        stab = [m for m in ROTATIONS if act(m, x) == x]
        stab_types[name] = sorted({_cycle_type(person_perm(m)) for m in stab})
    rot_fail, td_fail = failures(ROTATIONS), failures(td)
    check(
        results,
        "M19",
        "Two different S4s act on the persons. The tetrahedral group T_d (24 "
        "symmetries preserving tetrahedron A, reflections included) acts "
        "equivariantly on the person labels of M5 and M7; the rotation group O "
        "does not (its 12 odd elements swap A and B, reversing ordered pairs and "
        "complementing unordered ones). The full group is T_d x {±I}, with "
        "central inversion swapping a person and its antipode. Under T_d the "
        "vertices form two orbits of 4, so 24/3 = 8 (M9) is an O-statement only. "
        "Under O the stabilizers act on persons as a 3-cycle group (vertex), a "
        "transposition (edge), and a 4-cycle group (face).",
        td_fail == (0, 0)
        and rot_fail[0] > 0
        and rot_fail[1] > 0
        and keys(td) | keys(minus(m) for m in td) == keys(SYMMETRIES)
        and not keys(td) & keys(minus(m) for m in td)
        and td_orbits == [4, 4]
        and stab_types["vertex"] == [(1, 1, 1, 1), (3, 1)]
        and stab_types["edge"] == [(1, 1, 1, 1), (2, 1, 1)]
        and stab_types["face"] == [(1, 1, 1, 1), (2, 2), (4,)],
        td_equivariance_failures={"edges": td_fail[0], "faces": td_fail[1]},
        rotation_equivariance_failures={"edges": rot_fail[0], "faces": rot_fail[1]},
        td_vertex_orbits=td_orbits,
        rotation_stabilizer_cycle_types={
            k: [list(t) for t in v] for k, v in stab_types.items()
        },
    )


def coarsening_checks(results):
    v0 = VERTICES[0]
    layers = Counter(hamming(v0, v) for v in VERTICES)
    by_distance = [layers[k] for k in range(4)]
    spirit = [layers[0], layers[1] + layers[2], layers[3]]
    father = [layers[0] + layers[2], layers[1] + layers[3]]
    s8 = [w for w in product((HALF, -HALF), repeat=4) if sum(x < 0 for x in w) % 2 == 0]
    graded = Counter(w[0] + w[1] + w[2] for w in s8)
    levels = [graded[k] for k in sorted(graded, reverse=True)]
    check(
        results,
        "M20",
        "All three patterns are coarsenings of one grading. In the cube, distance "
        "from one chosen vertex gives 1+3+3+1; merging the two middle layers gives "
        "1+6+1 (the chosen body diagonal against the rest); grouping by parity "
        "gives 4+4 (the two tetrahedra). On a single half-spin 8, c=(1,1,1,0) "
        "gives 1+3+3+1 and the same two coarsenings give 1+6+1 and 4+4. M17 "
        "forbids the three patterns on three different 8s under one grading; it "
        "does not forbid them as three coarsenings of one 8.",
        by_distance == [1, 3, 3, 1]
        and spirit == [1, 6, 1]
        and father == [4, 4]
        and levels == [1, 3, 3, 1]
        and [levels[0], levels[1] + levels[2], levels[3]] == [1, 6, 1]
        and [levels[0] + levels[1], levels[2] + levels[3]] == [4, 4],
        cube=by_distance,
        half_spin=levels,
    )


def line_graph_checks(results):
    pairs = [frozenset(p) for p in combinations(PERSONS, 2)]
    adjacent = {(a, b) for a, b in combinations(pairs, 2) if a & b}
    degrees = Counter(x for edge in adjacent for x in edge)
    non_neighbours = {
        a: [
            b
            for b in pairs
            if b != a and (a, b) not in adjacent and (b, a) not in adjacent
        ]
        for a in pairs
    }
    complementary = all(
        len(v) == 1 and v[0] == frozenset(PERSONS) - k
        for k, v in non_neighbours.items()
    )
    check(
        results,
        "M18",
        "The line graph of the tetrahedron (one node per pair of persons, adjacent "
        "when the pairs share a person) is the octahedron graph K(2,2,2): 6 nodes, "
        "12 edges, every node of degree 4, each node's only non-neighbour its "
        "complementary pair.",
        len(adjacent) == 12 and set(degrees.values()) == {4} and complementary,
    )


def pascal_checks(results):
    def row(n):
        out = [1]
        for k in range(n):
            out.append(out[-1] * (n - k) // (k + 1))
        return out

    r3, r4 = row(3), row(4)
    even4 = [r4[k] for k in range(0, 5, 2)]
    odd4 = [r4[k] for k in range(1, 5, 2)]
    check(
        results,
        "M11",
        "Pascal rows: 1+3+3+1 = 8 and 1+4+6+4+1 = 16; 16 + 8 = 24. Row 4 splits by "
        "parity of weight into 1+6+1 (even) and 4+4 (odd): the dimensions of the "
        "even and odd parts of the exterior algebra of a 4-dimensional space.",
        r3 == [1, 3, 3, 1]
        and r4 == [1, 4, 6, 4, 1]
        and sum(r3) + sum(r4) == 24
        and even4 == [1, 6, 1]
        and odd4 == [4, 4],
        row3=r3,
        row4=r4,
        even=even4,
        odd=odd4,
    )

    def layers(n):
        pts = list(product((0, 1), repeat=n))
        return {k: [p for p in pts if sum(p) == k] for k in range(n + 1)}

    l3, l4 = layers(3), layers(4)

    def regular_simplex(points):
        return len({sq_dist(a, b) for a, b in combinations(points, 2)}) == 1

    octa = l4[2]
    octa_dists = Counter(sq_dist(a, b) for a, b in combinations(octa, 2))
    check(
        results,
        "M12",
        "Weight layers: in the 3-cube the middle layers (3 points each) are "
        "equilateral triangles; in the 4-cube the layers are point, regular "
        "tetrahedron (4), regular octahedron (6), regular tetrahedron (4), point. "
        "A fourth bit yields a 4-cube (16 vertices), not a tetrahedron; the "
        "tetrahedron appears as one layer of it.",
        regular_simplex(l3[1])
        and regular_simplex(l3[2])
        and regular_simplex(l4[1])
        and regular_simplex(l4[3])
        and octa_dists == Counter({2: 12, 4: 3}),
        octahedron_squared_distances=dict(octa_dists),
    )


def four_d_checks(results):
    v8 = [
        tuple(Fraction(s) if j == i else Fraction(0) for j in range(4))
        for i in range(4)
        for s in (1, -1)
    ]
    s8 = [w for w in product((HALF, -HALF), repeat=4) if sum(x < 0 for x in w) % 2 == 0]
    c8 = [w for w in product((HALF, -HALF), repeat=4) if sum(x < 0 for x in w) % 2 == 1]
    cell24 = v8 + s8 + c8

    def norm2(w):
        return sum(x * x for x in w)

    def cross_polytope(points):
        if len(points) != 8 or len(set(points)) != 8:
            return False
        pairs = {frozenset((p, tuple(-x for x in p))) for p in points}
        if len(pairs) != 4 or any(tuple(-x for x in p) not in points for p in points):
            return False
        axes = [next(iter(pair)) for pair in pairs]
        return all(
            sum(a * b for a, b in zip(p, q)) == 0 for p, q in combinations(axes, 2)
        )

    check(
        results,
        "M13",
        "The 24 unit vectors {±e_i} ∪ {(±1/2)^4} are the 24-cell's vertices "
        "(16 + 8 = 24). They split into three 8-point cross-polytopes (16-cells): "
        "the ±e_i, and the two parity halves of the 16 half-integer points. These "
        "are the weights of the vector and the two half-spin representations of "
        "Spin(8). In 3D, the cube's parity halves are two tetrahedra (M4); in 4D "
        "the tesseract's parity halves are two 16-cells, and a third 16-cell "
        "completes the 24-cell.",
        len(set(cell24)) == 24
        and all(norm2(w) == 1 for w in cell24)
        and all(cross_polytope(part) for part in (v8, s8, c8)),
    )
    roots = {
        tuple((s if k == i else 0) + (t if k == j else 0) for k in range(4))
        for i, j in combinations(range(4), 2)
        for s in (1, -1)
        for t in (1, -1)
    }
    check(
        results,
        "M14",
        "The D4 root system has 24 roots ±e_i±e_j = 2·4·3, matching the 24-cell.",
        len(roots) == 24,
    )

    # An explicit order-3 orthogonal map cyclically permuting the three 8-sets.
    t = [
        [HALF, HALF, HALF, HALF],
        [HALF, HALF, -HALF, -HALF],
        [HALF, -HALF, HALF, -HALF],
        [-HALF, HALF, HALF, -HALF],
    ]

    def apply(m, w):
        return tuple(sum(m[i][j] * w[j] for j in range(4)) for i in range(4))

    def matmul(a, b):
        return [
            [sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)
        ]

    identity = [[Fraction(int(i == j)) for j in range(4)] for i in range(4)]
    transpose = [list(r) for r in zip(*t)]
    sets = {"vector": set(v8), "spinor_even": set(s8), "spinor_odd": set(c8)}
    image = {
        name: next(
            (other for other, pts in sets.items() if {apply(t, w) for w in src} == pts),
            None,
        )
        for name, src in sets.items()
    }
    check(
        results,
        "M15",
        "A specific orthogonal matrix T (entries ±1/2) permutes the three "
        "8-point sets cyclically. T preserves the 24-cell, lies outside the "
        "symmetry group of D4 (W(D4) preserves each set), and so realizes on "
        "weights the order-3 triality symmetry of the D4 diagram.",
        matmul(t, transpose) == identity
        and None not in image.values()
        and len(set(image.values())) == 3
        and all(image[k] != k for k in image),
        cycle=image,
    )

    def pattern(points, c):
        counts = Counter(sum(a * b for a, b in zip(w, c)) for w in points)
        return [counts[k] for k in sorted(counts, reverse=True)]

    examples = {}
    for c in ((1, 1, 1, 1), (0, 0, 0, 1), (1, 1, 1, 0)):
        examples[str(c)] = {
            "vector": pattern(v8, c),
            "spinor_even": pattern(s8, c),
            "spinor_odd": pattern(c8, c),
        }
    check(
        results,
        "M16",
        "One-parameter gradings (a U(1) direction c) split the three 8s "
        "differently: c=(1,1,1,1) gives 4+4, 1+6+1, 4+4 (the exterior-algebra "
        "model); c=(0,0,0,1) gives 1+6+1, 4+4, 4+4 (Spin(6)xSpin(2)); "
        "c=(1,1,1,0) gives 3+2+3, 1+3+3+1, 1+3+3+1. Which representation is "
        "'1+6+1' depends on the chosen subgroup, not on the representation alone.",
        examples["(1, 1, 1, 1)"]
        == {"vector": [4, 4], "spinor_even": [1, 6, 1], "spinor_odd": [4, 4]}
        and examples["(0, 0, 0, 1)"]
        == {"vector": [1, 6, 1], "spinor_even": [4, 4], "spinor_odd": [4, 4]}
        and examples["(1, 1, 1, 0)"]
        == {
            "vector": [3, 2, 3],
            "spinor_even": [1, 3, 3, 1],
            "spinor_odd": [1, 3, 3, 1],
        },
        examples=examples,
    )
    wanted = sorted([[4, 4], [1, 3, 3, 1], [1, 6, 1]])
    hits = []
    box = range(-4, 5)
    for c in product(box, repeat=4):
        if any(c):
            pats = sorted([pattern(v8, c), pattern(s8, c), pattern(c8, c)])
            if pats == wanted:
                hits.append(c)
    check(
        results,
        "M17",
        "No single grading gives the three patterns 4+4, 1+3+3+1, 1+6+1 at once. "
        "Proof: if some 8 is 1+6+1, apply T (M15) until it is the vector set; "
        "then six of ±c_i vanish, so c is a multiple of one e_k, and both "
        "half-spin sets split 4+4, never 1+3+3+1. Exhaustive search over integer "
        "directions in [-4,4]^4 agrees.",
        not hits,
        searched=9**4 - 1,
        hits=[list(h) for h in hits],
    )
    generic = (5, 3, 2, 1)
    special = (3, 1, 1, 1)
    all_three = [
        c
        for c in product(box, repeat=4)
        if any(c) and all(pattern(p, c) == [1, 3, 3, 1] for p in (v8, s8, c8))
    ]
    check(
        results,
        "M21",
        "1+3+3+1 is not the generic grading (supersedes a 0.2.0 note). A "
        "generic c such as (5,3,2,1) splits every 8 into eight distinct values; "
        "c=(3,1,1,1) gives 1+3+3+1 on the vector and even half-spin sets but "
        "3+2+3 on the odd one; no integer direction in [-4,4]^4 gives 1+3+3+1 "
        "on all three 8s.",
        all(pattern(p, generic) == [1] * 8 for p in (v8, s8, c8))
        and [pattern(p, special) for p in (v8, s8, c8)]
        == [[1, 3, 3, 1], [1, 3, 3, 1], [3, 2, 3]]
        and not all_three,
        generic={str(generic): [pattern(p, generic) for p in (v8, s8, c8)]},
        special={str(special): [pattern(p, special) for p in (v8, s8, c8)]},
        all_three_hits=[list(c) for c in all_three],
    )


def transverse_triples():
    return [
        (v, e, f)
        for v in VERTICES
        for e in EDGES
        for f in FACES
        if v in e and v in f and not e <= f
    ]


def transverse_checks(results, triples=None):
    triples = transverse_triples() if triples is None else triples
    fibres = [Counter(t[i] for t in triples) for i in range(3)]
    pairs = [
        Counter((t[i], t[j]) for t in triples) for i, j in combinations(range(3), 2)
    ]
    valid = all(
        v in VERTICES and e in EDGES and f in FACES and v in e and v in f and not e <= f
        for v, e, f in triples
    )
    orbit = set()
    if triples:
        v, e, f = triples[0]
        for m in ROTATIONS:
            vm = vertex_map(m)
            orbit.add((vm[v], frozenset(vm[x] for x in e), frozenset(vm[x] for x in f)))
    check(
        results,
        "M22",
        "Synesis's transverse triples form one 24-element set, with vertex, edge, "
        "face fibres 3, 2, 4. Every compatible pair uniquely completes a triple; "
        "the rotation action is regular. These are not ordinary flags.",
        valid
        and len(set(triples)) == len(triples) == 24
        and [set(c) for c in fibres] == [set(VERTICES), set(EDGES), set(FACES)]
        and [set(c.values()) for c in fibres] == [{3}, {2}, {4}]
        and all(set(c.values()) == {1} for c in pairs)
        and orbit == set(triples),
        count=len(triples),
        fibre_sizes=[sorted(set(c.values())) for c in fibres],
        pair_counts=[len(c) for c in pairs],
        rotation_orbit=len(orbit),
    )


def sl3_groupings():
    """Basis tokens: sector W/dual/exterior and a subset of (L,u1,u2,u3)."""
    w = {("W", (i,)) for i in range(4)}
    dual = {("dual", (i,)) for i in range(4)}
    ext = {k: {("exterior", s) for s in combinations(range(4), k)} for k in range(5)}
    odd = [
        {("exterior", (0,))},
        {("exterior", (i,)) for i in range(1, 4)},
        {("exterior", (0, *s)) for s in combinations(range(1, 4), 2)},
        {("exterior", (1, 2, 3))},
    ]
    return {"vector": [w, dual], "odd": odd, "even": [ext[0], ext[2], ext[4]]}


def sl3_checks(results, groupings=None):
    groupings = sl3_groupings() if groupings is None else groupings
    expected = sl3_groupings()
    weights = ((0, 0), (1, 0), (0, 1), (-1, -1))

    def weight(token):
        sector, subset = token
        sign = -1 if sector == "dual" else 1
        return tuple(sign * sum(weights[i][j] for i in subset) for j in range(2))

    def invariant(block):
        # Six elementary root operators generate sl(3) together with their
        # diagonal commutators. Diagonal operators preserve every basis line.
        for sector, subset in block:
            for a, b in permutations(range(1, 4), 2):
                if b in subset and a not in subset:
                    target = tuple(sorted((set(subset) - {b}) | {a}))
                    if (sector, target) not in block:
                        return False
        return True

    character = Counter(
        {
            (0, 0): 2,
            (1, 0): 1,
            (0, 1): 1,
            (-1, -1): 1,
            (-1, 0): 1,
            (0, -1): 1,
            (1, 1): 1,
        }
    )
    dims = {name: [len(b) for b in blocks] for name, blocks in groupings.items()}
    partitions = all(
        set().union(*blocks) == set().union(*expected[name])
        and sum(map(len, blocks)) == len(set().union(*blocks))
        for name, blocks in groupings.items()
    ) and set(groupings) == set(expected)
    invariant_blocks = all(
        invariant(b) for blocks in groupings.values() for b in blocks
    )
    characters = {
        name: Counter(weight(t) for b in blocks for t in b)
        for name, blocks in groupings.items()
    }
    check(
        results,
        "M23",
        "For W=L+U with SL(3,C) fixing L, V, odd spin, and even spin admit "
        "selected invariant groupings 4+4, 1+3+3+1, 1+6+1 simultaneously. All "
        "refine to 1+1+3+3*, not three different irreducible branchings.",
        partitions
        and invariant_blocks
        and dims == {"vector": [4, 4], "odd": [1, 3, 3, 1], "even": [1, 6, 1]}
        and all(c == character for c in characters.values()),
        dimensions=dims,
        invariant_blocks=invariant_blocks,
        characters={
            name: {str(k): v for k, v in c.items()} for name, c in characters.items()
        },
    )


def run():
    results: list[dict] = []
    cube_checks(results)
    group_checks(results)
    two_groups_checks(results)
    line_graph_checks(results)
    pascal_checks(results)
    four_d_checks(results)
    coarsening_checks(results)
    transverse_checks(results)
    sl3_checks(results)
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--brief", action="store_true")
    args = parser.parse_args(argv)
    results = run()
    ok = all(r["ok"] for r in results)
    if args.brief:
        for r in results:
            print(f"{r['id']:>4} {'ok  ' if r['ok'] else 'FAIL'} {r['claim'][:90]}")
    else:
        print(
            json.dumps(
                {"ok": ok, "checks": results},
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
