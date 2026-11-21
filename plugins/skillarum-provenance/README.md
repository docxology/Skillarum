# Skillarum Provenance

Review generated Agent Skills before distribution. Skillarum Provenance helps maintainers trace a skill to its recorded sources, judge which claims the supplied evidence supports, and spot instructions or dependencies that make a skill unsafe or difficult to install.

## Choose a skill

| Skill | What you get |
| --- | --- |
| `audit-skill-provenance` | A trace from selected skill claims to acquisition, preparation, and render records, with gaps and contradictions called out. |
| `review-generated-skill` | A distribution review covering the skill trigger, required context, bundled references, and disclosed effects, with targeted fixes. |

Add the plugin in Claude. Paste only the relevant Markdown, manifest fields, source excerpts, or receipt excerpts that you are allowed to share. Ask for either workflow in plain language. In Claude Code, you can also invoke `/skillarum-provenance:audit-skill-provenance` or `/skillarum-provenance:review-generated-skill`.

## Example prompts

1. “Audit this generated skill claim: ‘Open hours are 9–5 daily.’ My acquisition record says `origin: fixture` and the excerpt says ‘Weekdays 9–5.’ The render receipt lists that page. Which part is supported, and what can I say about freshness?”
2. “Compare the provenance of these two snapshots. April reports `origin: live` and `status: complete`. May reports `origin: unknown`, `status: partial`, and `failed_pages: 2`. May’s index calls the package current. What can I conclude from these fields?”
3. “Review this generated skill excerpt for distribution. Its `description` says ‘Use for all writing.’ Its instructions say ‘Read `references/guide.md` and run `scripts/check.py`.’ The package inventory lists only `SKILL.md`. What needs to change before I can ship it?”

## Troubleshooting

- If the provenance audit reports a gap, paste the relevant source passage or the exact missing receipt fields. Include their origin and retrieval date if known.
- If a reference comes back as unverified, paste the matching package inventory entry and any relevant excerpt. A pathname or URL alone establishes only that the skill mentions it.
- If Claude selects the wrong workflow, ask for a provenance audit to check evidence and lineage, or a distribution review to check skill behavior and packaging.

## Privacy policy

Skillarum Provenance analyzes only excerpts you intentionally paste into your current request. A review can use limited public attribution, such as an author or publisher name, when it is relevant to assessing an excerpt. Use public material you are allowed to share and remove secrets and other personal or sensitive details before pasting it.

The bundle contains Markdown instructions and listing metadata. It makes no external requests and keeps no publisher-side records. The publisher receives none of the pasted text or analysis, and the plugin sends neither to third parties. Claude processes the conversation according to your account settings and Anthropic's applicable terms and privacy practices. [Anthropic Privacy Policy](https://www.anthropic.com/legal/privacy)

## Support

For usage questions or bugs, use the public issue tracker and share a synthetic or redacted example. [Skillarum support](https://github.com/docxology/Skillarum/issues)

Report vulnerabilities through GitHub's private reporting form. [Private security report](https://github.com/docxology/Skillarum/security/advisories/new)

Released under the [MIT License](LICENSE).
