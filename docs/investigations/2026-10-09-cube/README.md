# Independent investigation of the Math4Wisdom cube correspondence (2026-10-09)

This directory records one run of the experiment Synesis proposed on
2026-10-09: write a versioned skill describing the cube, the two tetrahedra,
and the three languages; then ask independently operating AI investigators
to reconstruct the correspondence, verify the combinatorics, identify
unsupported identifications, and propose discriminating observations, each
preserving provenance and identifying its own additions.

## What was run

| Step | Artifact |
| --- | --- |
| Skill under test | `skills/math4wisdom-cube/` version 0.1.0 (git commit "math4wisdom-cube 0.1.0") |
| Protocol | `skills/math4wisdom-cube/references/investigator-protocol.md` as of 0.1.0 |
| Reports | [`reports/forge-b.md`](reports/forge-b.md), [`reports/sonnet-a.md`](reports/sonnet-a.md), [`reports/anvil-c.md`](reports/anvil-c.md), verbatim |
| Revision | `skills/math4wisdom-cube/` version 0.2.0 and its `CHANGELOG.md`; 0.3.0 corrects one adopted claim |

Each investigator received the same brief, worked in a separate session, was
told not to modify the repository, and could not see the other reports. Each
returned its report as its final message; the reports were saved without
editing.

## Who the investigators were

The record matters more than the labels, so this table gives what each
report says about itself.

| Report | Requested as | Ran on (self-reported) | Lineage |
| --- | --- | --- | --- |
| forge-b | Forge (OpenAI via `codex exec`), audit mode | "OpenAI-lineage agent in audit mode, running as the Claude Code agent shell" | OpenAI (self-reported; the carrier was not independently confirmed) |
| sonnet-a | general-purpose agent | Claude Sonnet 5.5 | Anthropic |
| anvil-c | Anvil (Kimi K2.6) | Claude Opus 5.5; the Kimi pipeline was not used | Anthropic |

The skill's author is also a Claude model. Two of three investigators
therefore share the author's lineage, and all three shared the brief and the
source files. Independence here means separate sessions and no sight of each
other's work; it does not mean independent training. Only anvil-c's own
provenance section revealed that it had not run on the requested model, which
is why the 0.2.0 protocol asks investigators to record the model that
actually ran.

## What they found

| Finding | forge-b | sonnet-a | anvil-c | Disposition in 0.2.0 |
| --- | --- | --- | --- | --- |
| Person labels (M5, M7) are not equivariant under the rotation group; the two "S4" readings conflict | X-1–4 | X-1 (144 edge, 72 face failures) | X-1 | Confirmed by new check M19; table split into T_d and O readings (C4) |
| Incidence pairing of languages attributed to the source (S2) instead of Synesis (S6) | X-10 | §6.1 | — | Attribution corrected |
| C2 ("a fourth bit gives a 4-cube") overclaims; S3's arithmetic is the subset lattice | X-8 | §6.7 | X-4 | C2 withdrawn |
| Blind phase leaked the cube, so convergence is weak evidence | X-9 | — | (leaked S4) | New `blind-brief.md` |
| Zoas, atlas of views, three modes unquoted | — | §6.6 | §6.5 | Quoted as S9–S11 |
| "Stabilize" not answered by M4 | — | §6.5 | — | Recorded as S12 |
| Son still conflicts under Spin(6)×Spin(2) | — | §6.4 | — | I6 amended |
| All three patterns as coarsenings of one grading | (E-C) | D3, X-3 | — | New check M20; I6 second reading; E8 |
| M10 is true but weak | — | §6.8 | X-2 (T_d splits) | Marked in M10 and I2 |
| God-centred placement of persons | — | — | X-3 | New I9, E7 |
| Unoriented language cycle is symmetric; handedness gives holonomy | — | — | X-5, X-6 | Recorded in I4, E6; not yet recomputed |
| M17 proof and searches | complete for all real c (11,962 directions) | 390,624 directions | 50,624 directions | Unchanged; torus-reduction step stated |
| "1+3+3+1 is generic; c = (3,1,1,1) gives it in all three 8s" | X-7 | — | — | Adopted in 0.2.0 without recomputation; found false afterwards and withdrawn in 0.3.0 (M21, C5) |

No investigator found a failing check or a counterexample to any `M` item.
One investigator claim was itself wrong: forge-b X-7 says c = (3,1,1,1)
gives 1+3+3+1 in all three 8s, but it gives 3+2+3 on the odd half-spin set,
and generic directions split every 8 into distinct values. 0.2.0 adopted the
claim without rerunning it; 0.3.0 withdraws it and adds check M21. Investigator
statements are inputs to check, not results.
Every substantive change in 0.2.0 concerns what the mathematics was claimed
to support, who was credited, or how the experiment was designed. That is
the separation the skill exists to keep.

## What this run does not show

- It does not show that the cube, the tetrahedra, or triality are the right
  mathematics for Wondrous Wisdom; the `I` entries remain open or
  constrained.
- Convergence among investigators is weak evidence here: they shared a brief,
  sources, and in two cases a model family, and the 0.1.0 blind phase was not
  blind. A cleaner rerun would use `references/blind-brief.md`, more vendors,
  and human investigators.
- Nothing here bears on whether any AI participant is conscious or
  cognizant.

## Reproducing

```bash
python3 skills/math4wisdom-cube/scripts/verify_combinatorics.py --brief
git log --oneline -- skills/math4wisdom-cube   # 0.1.0, 0.2.0, 0.3.0
```

To run a new round, give each investigator the protocol of the current
version, record the model that actually ran, and add the reports under a new
dated directory.
