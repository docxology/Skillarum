# math4wisdom-cube changelog

Versions follow semantic versioning. A minor version adds or supersedes
ledger entries; a patch version fixes wording without changing any claim.
Ledger IDs are never reused: a superseded entry is marked, not deleted.

## 0.4.0 — 2026-10-12

- **S13, S14.** Synesis's October 10 reply, the live draft poster, and Woit's
  exterior-algebra notes are recorded with separate evidence scopes.
- **M22.** Recompute transverse triples, all projection fibres, unique pair
  completion, and the regular rotation action. Ordinary flags remain 48.
- **M23, C6.** Recompute the three simultaneous SL(3, C) invariant groupings
  with exterior bases, root-operator closure, and characters. All refine to
  two singlets, the standard 3, and its dual. Supersede the overbroad M17/I6/E8
  consequences; the single-grading theorem itself remains intact.
- **I11, E10, E11.** Add semantic completion and triality compatibility tests.
- **Protocol.** Record prior exposure and situated contributions; a letter
  reporting a calculation is not an inspected script or an independent audit.
- Preserve the October 10 letter verbatim and document poster feedback.
- Checker: 23 checks (M1–M23), with real negative controls in the test suite.

## 0.3.0 — 2026-10-09

Supersedes one mathematics note, so this is a minor version.

- **M21, C5.** 0.2.0 adopted forge-b X-7 without recomputing it: "1+3+3+1 is
  generic: c = (3,1,1,1) gives it in all three 8s." A post-release check found
  both parts false. That direction gives 1+3+3+1 on 8_v and 8_s but 3+2+3 on
  8_c; a generic direction such as (5,3,2,1) splits every 8 into eight
  distinct values; and no integer direction in [−4,4]⁴ gives 1+3+3+1 on all
  three. The 0.2.0 note under M17 is struck through and kept, and the new
  check M21 tests the corrected statement. M17 and its consequence for I6 are
  unchanged.
- Checker: 21 checks (M1–M21).

## 0.2.0 — 2026-10-09

Revision after three independent investigators (forge-b, sonnet-a, anvil-c)
audited 0.1.0 under its own protocol. Their reports are kept verbatim in
`docs/investigations/2026-10-09-cube/reports/` of the Skillarum repository.
Two of the three ran on Claude models (anvil-c was requested as a Kimi-backed
agent but reports running on Claude Opus 5.5); forge-b reports OpenAI lineage.

- **C4 / M19 (all three investigators).** The person labels of M5–M7 are
  equivariant under T_d, not under the rotation group O; M8–M9's
  orbit-stabilizer reading uses O. The two readings are now shown side by
  side, and the M9 persons sentence and I3 are marked.
- **M20 (from sonnet-a).** All three Father/Son/Spirit patterns arise as
  coarsenings of one grading, of the cube or of one 8; added with a check,
  and I6 now carries both readings.
- **C2 withdrawn (all three).** "A fourth bit makes a tetrahedron" holds when
  bits index subsets of vertices.
- **Attribution fixes (forge-b, sonnet-a, anvil-c).** The incidence pairing of
  languages is Synesis's (S6), not the source's (S2); the rotation row no
  longer sits under the source column; the Zoas, the atlas of views, and the
  Seed Crystal's three modes are now quoted (S9–S11); S4 is an unsigned wiki
  note; Daniel's "stabilize" is recorded as unanswered (S12).
- **Mathematics notes.** M10 is true but weak (any two regular G-sets are
  isomorphic); T is a root-system automorphism with T³ = I; M17's reduction
  to the torus is stated; 1+3+3+1 is the generic grading pattern
  (false; withdrawn in 0.3.0).
- **New interpretations and tests.** I9 (God-centred placement), I10 (T_d or
  O), E5–E9.
- **Protocol.** The blind phase now reads only `references/blind-brief.md`;
  0.1.0's blind phase leaked the cube. Investigators record the model that
  actually ran.
- Checker: 20 checks (M1–M20); M10 now prints its orbit sizes.

## 0.1.0 — 2026-10-09

First version, written in response to Synesis's proposal (S7) and Daniel
Friedman's cube question (S5).

- Source ledger S1–S8 from the Math 4 Wisdom wiki (Research/Overview,
  Research/Triality, Research/Divisions) and the compiled 2026-10-09
  conversation among Andrius Kulikauskas, Synesis, and Daniel Friedman.
- Mathematics ledger M1–M18 with a standard-library checker.
- Corrections C1 (which incidences 8 × 3 counts), C2 (a fourth bit gives a
  4-cube), C3 (the lost triality table).
- New results from this version's author: the rotation-group reading of
  24/3, 24/2, 24/4 (M8–M10); compatibility of the two Spirit assignments
  (M16); no single grading yields Father, Son, and Spirit patterns together
  (M17); the line graph of the persons' tetrahedron is the octahedron (M18).
- Interpretation ledger I1–I8 and test proposals E1–E4.
- Independent investigator protocol.
