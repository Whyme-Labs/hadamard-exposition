# Publication in the existing repository

## Decision

Use `Whyme-Labs/hadamard-exposition` for the award release. A second repository is not a prize requirement and is no longer the default plan. This supersedes the earlier mirror recommendation, not the frozen scientific artifacts or historical receipts.

Do not run the legacy `release/publish_bundle.py` mirror-creation path for this plan. Keep the research history and attach a clearly versioned submission package to the existing repository's release. Failed experiments and unfinished Pythia work are not, by themselves, confidentiality problems.

The scientific candidate remains the 49-file v2 package with SHA-256 `6074fcc3745e756765bd676be051d04b72c3c29314dd6094b64ef555af29b044`, 470,653 bytes. Its scientific source was integrated at `911f9ad0840fe36521b51ce9038c2ed97c81f9c8`. No article, theorem, empirical result, original archive or license was changed by this publication audit.

## Audit completed on 21 October 2026

The read-only scanner inspected all objects reachable from the fetched branch, tag and PR-head refs at audit source `a64120aacb2983a5155b4384adc05fb0c836fb6d`:

- 60 commits and 352 unique blob versions, including historical content no longer at a branch tip.
- 39 ZIP/tar/gzip containers and 1,342 member visits, including nested archives. These counts include container layers and repeated evidence, not 39 distinct underlying datasets.
- 184,261,439 bytes inspected across Git and remote material.
- 15 issues/PRs, 26 issue comments, two reviews, four completed workflow log archives and the current artifact inventory. No retained Actions artifacts were present.

Report: [redacted full audit](https://github.com/Whyme-Labs/hadamard-exposition/blob/evidence/publication-audit-39549217108-1/report.json), Git blob `52f7b23ca8b835d83d99ee6c5764d13981cf0424`.

Summary: [scope and counts](https://github.com/Whyme-Labs/hadamard-exposition/blob/evidence/publication-audit-39549217108-1/summary.json), Git blob `49a8b2e1ba8f64096bb44e6923fbdc4fb4516591`.

No private-key, GitHub-token, cloud-access-key, Hugging Face-token or API-secret pattern was found by the configured detector. This is a bounded indicator scan, not a guarantee that no confidential data exists.

The authenticated URL flags were deliberate negative-test fixtures in `benchmarks/test_dependency_lock.py` and its archived copies. The password-assignment flag was the new scanner's explicit test fixture. They are not account credentials.

The archived personal-email and home-path indicators were checked against the corresponding public PyPI package-version metadata. All compared indicators were present in that public metadata. No package-distribution or model-weight file matching the audit's selected redistribution extensions was found. This is not a blanket copyright or license clearance; third-party metadata retains its original terms.

Follow-up: [metadata verification and cleanup receipt](https://github.com/Whyme-Labs/hadamard-exposition/blob/evidence/publication-review-39550137635-1/review.json), Git blob `93087cf490ad0d56e2efb6661cd5f436f02952c3`.

## Remaining publication review

The live PR bodies contain signed Codesmith action links. Eight generated footer blocks were removed while preserving every byte outside those blocks, and immediate readback confirmed removal. A later read found eight signed footer blocks again, including PR 15. The cleanup did not persist. Do not describe this repository as sanitized or repeatedly fight the integration by deleting the same footer.

These links are service-generated action URLs, not evidence of a leaked GitHub credential. Their authorization behavior was not tested, and no signed action link was exercised. Before exposing the entire repository, resolve the integration's footer policy or confirm that exposing these signed URLs and their historical edit versions is acceptable. Editing a current PR body does not erase its edit history. This is an integration-metadata question, not a requirement for a second repository or another numerical experiment.

The original audit marked three unfinished workflow runs as coverage gaps. The follow-up verified zero executed steps and no assigned runner for all three. Two cancellation requests completed with no steps: runs `39536825246` and `39465140698`. Run `39466379796` was `pending`, not `queued`, and the narrow cleanup did not cancel it. Later runtime logs, if any, are outside the audit cutoff.

The present connector has no repository-visibility operation, the local runtime has no authenticated GitHub CLI, and the connected browser only reads tabs. No visibility change or public release is claimed. No administrator credentials were requested or extracted.

## Execution and tests

The scanner and cleanup-helper tests ran locally: 19 tests passed. The exact candidate archive was rescanned locally with no indicator findings or skipped ZIP members. Its extracted package passed 47 existing tests, all 48 checksum entries, the 589-field scientific audit and the actual embedded calculator check.

The full Git database and archived evidence were not available in the local runtime, and shell DNS access to GitHub failed. A new home-runner attempt, run `39548955770`, remained queued with no assigned runner and no steps. Two bounded Blacksmith jobs then performed the full-history audit and the findings review, runs `39549217108` and `39550137635`. The workflow is now manual-only and defaults to home-ci-01; there is no automatic Blacksmith fallback.

`audit.py` is read-only except for writing a new local report. It never authorizes publication. `review_findings.py` records a one-off metadata intervention and has explicit write behavior: current generated PR-footer cleanup and cancellation of three named zero-step runs. It is not a general-purpose safe scan and should not be rerun while the footer integration remains active.

## Fixed release handoff

1. Resolve the live signed-footer exposure question. Do not rewrite scientific history to remove ordinary failed experiments.
2. An authorized administrator changes the existing repository's visibility only after the exposure review. No new repository is needed.
3. Create a release tied to the exact scientific commit and attach the accepted ZIP and PDFs without rebuilding them. Use [the prepared release notes](release-notes-v2.md).
4. Verify the material without authentication and record the actual public observation time, fixed commit, URLs and checksums in a new publication receipt. Private preparation or release-draft dates are not public priority.
5. Submit the exact version through the authorized Exposition review route. Do not claim candidate selection or an award until the official process records it.

An alternative that still uses this repository is publishing only the selected package through a configured static site. GitHub Pages from a private repository requires an eligible plan and initial administrator setup. Neither that plan eligibility nor Pages enablement has been established here.

Official references: [GitHub visibility consequences](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility), [GitHub Pages setup](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site), and [the Exposition process](https://github.com/TheJustinSunPrize/awards/blob/main/docs/award-process-mathdb.md).
