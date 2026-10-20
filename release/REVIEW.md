# Release implementation review

Scope: the release tooling proposed in PR #13 against main commit `280ab929e206d263a5928585b13e09558ad445da`, implementing the approved curated-mirror plan in issue #11. This is a self-review by the implementing assistant, not an independent agent review, academic review or committee decision.

## Standards

The builder separates frozen scientific inputs from release metadata and excludes research history. It reads exact Git blobs, rejects unsafe paths and symlinks, checks exported links and records source identities. Existing output directories and receipts cannot be overwritten by a rejected rerun. Credentials and reproduction logs do not enter the public payload.

Two real regression controls exposed Git configuration hazards in the initial publisher. A global clean filter changed a committed article, and inherited Git directory variables redirected Git commands. The corrected publisher ignores those settings, checks all committed blob identities and pushes only the new parentless repository. The final local suite passes 33 tests.

Remaining standards limit: payload scanning checks a small set of high-confidence credential patterns. It is not a proof that every kind of private information is absent. The live GitHub creation and visibility-change path has not executed in this environment.

## Specification

The implementation preserves the article and all frozen scientific results. It adds the approved content/code licenses and an author wrapper with AI-assistance disclosure. It corrects the missing `docs/reference-import.json` dependency and does not copy a plan from an older commit where that plan did not exist. It replaces internal submission paperwork with a public-facing submission note, without asserting scientific novelty, priority or official acceptance.

Publication requires the original isolated `scripts/validate.py --reproduce` to pass, plus exact payload and receipt checks. Unit-test receipts are explicitly fixtures and do not satisfy this real-data gate. The publisher never changes the source repository's visibility. It records an anonymous observation of a public commit, not a committee priority determination.

Remaining specification gates: the hosted job failed before executing any steps, the real 26-file scientific extraction/reproduction has not run here, no accepted release ZIP exists, no public mirror or release tag exists and no official submission was sent. PR #13 is an implementation candidate, not an accepted public release. Keep issue #11 open.
