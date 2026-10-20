# Justin Sun Prize exposition submission dossier

This directory packages the Hadamard exposition for the Justin Sun Prize entry JSP-000013, Hadamard matrix conjecture, in the Exposition category.

The scientific content is complete enough for content review. It is not a solution of the Hadamard conjecture, a Lean formalization, a prize claim, or evidence of an award.

## Status checked on 20 October 2026

| Gate | Status | Evidence or action |
|---|---|---|
| Exposition content | Ready | [`article.md`](../../article.md) and the standalone [`exposition.html`](../../exposition.html) |
| Fixed private source version | Ready | Commit `5ec28b8f5a0dbed51630fc94e270a2a2462c37f3` and tree `d0490c2647f8c067dfc6b5fde1d69730fa7ab932` |
| Citations and source map | Ready | [`sources.json`](../../sources.json) |
| Reproducible synthetic evidence | Ready | [`results.json`](../../results.json), [`group-results.json`](../../group-results.json), and the retained validation receipt |
| Internal standards and specification review | Ready, with scope limits | Recorded in the merged pull requests and validation directories. These are agent reviews, not prize committee review or external academic peer review. |
| Stable public material link | Blocked | The repository is private as of this check. A public immutable article or public repository release must be created. |
| Public publication date | Blocked | Record the UTC publication time when the fixed material first becomes publicly accessible. A private Git timestamp is not a public publication date. |
| MathDB automatic claim route | Blocked externally | The official pilot register says rollout is `prepared`, not activated. |
| Prize committee exposition decision | Not started | Only the committee can select the first satisfactory exposition. |
| Official candidate review | Not started | The 14 full day review begins only after the prize administrators publish a candidate record. |

## Files in this dossier

- [`jsp-000013-exposition-submission.md`](jsp-000013-exposition-submission.md) is the submission draft. It contains the author, scope, original contributions, citations, review evidence, and claim limits.
- [`jsp-000013-reviewed-content.md`](jsp-000013-reviewed-content.md) maps the material to the official exposition requirements and identifies the two external blockers.
- [`jsp-000013-publication-manifest.json`](jsp-000013-publication-manifest.json) records exact source and artifact identities. Its public URL and public publication date remain null until publication.
- [`jsp-000013-public-release-plan.md`](jsp-000013-public-release-plan.md) defines the bounded safety audit, allowlist, denylist, license gate, immutable release procedure, and release acceptance checks.
- [`../../CITATION.cff`](../../CITATION.cff) supplies citation metadata without asserting a journal publication or award.

## Recommended public release

Publish the existing standalone `exposition.html` without changing its bytes. The recommended first release is a curated public mirror containing the allowlisted article, source, experiment, and dossier files. The private repository includes internal model-campaign evidence and has no committed license, so exposing its entire history adds review and redistribution risk without helping the Exposition claim.

The mirror should have an immutable Git tag or release that points to its first public commit. A separate static host may mirror the same standalone article, but the Git object should remain the primary fixed-version record.

Do not edit the article during publication. Any substantive correction creates a new version and should receive a new review record. Typographical corrections should still be documented so reviewers can identify exactly what they read.

After publication, update only the dossier metadata with:

1. The stable public material URL.
2. The full public release commit or tag.
3. The first public UTC timestamp supported by an independently accessible record.
4. The content review or MathDB submission record when that route is available.

## Official process references

- [JSP-000013 catalog entry](https://github.com/TheJustinSunPrize/awards/blob/main/problems/catalog-0001-0100.md#jsp-000013--hadamard-matrix-conjecture)
- [MathDB pilot register](https://github.com/TheJustinSunPrize/awards/blob/main/problems/mathdb-pilot.md)
- [MathDB award process](https://github.com/TheJustinSunPrize/awards/blob/main/docs/award-process-mathdb.md)
- [MathDB problem 315867](https://mathdb.com/p/315867/hadamard-conjecture)

The official rules require a stable material link, fixed version, publication date, authors, topic, cited sources, and reviewed content. Exposition has its own review path and is not gated by a solution or Lean proof. A committee decision is still required.
