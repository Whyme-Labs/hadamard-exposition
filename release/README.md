# Curated release tools

Issue #11 owns publication. These tools implement the approved curated mirror and CC BY 4.0 / MIT split. They never change the visibility of `Whyme-Labs/hadamard-exposition`.

## Build and verify

Run from a full checkout containing this implementation commit and the frozen source commit in `spec.json`. Use Python 3.12, Node.js and the root pinned requirements.

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover -s release -p 'test_*.py' -v
python3 release/build_bundle.py
```

The builder reads 26 exact scientific blobs from Git, adds eight public metadata files and writes a 36-file payload. It includes `docs/reference-import.json`, which the earlier prose allowlist omitted. It does not copy the private award dossier, a self-referential release plan, compressed model evidence or Git history.

The original `scripts/validate.py --reproduce` must pass inside an isolated copy of that payload. Only then does the builder create `build/public-release-v1/hadamard-exposition-v1.zip`, with a strict manifest, SHA-256 checksums and fixed ZIP metadata. Raw reproduction receipts and logs remain beside the ZIP, not inside it. A rejected rerun cannot overwrite an existing output or its receipt.

## Publish the verified payload

An authenticated GitHub CLI with permission to create a repository under Whyme-Labs is required. That action is not available through the current ChatGPT GitHub connector.

```bash
python3 release/publish_bundle.py --stage ../hadamard-exposition-public
python3 release/publish_bundle.py --stage ../hadamard-exposition-public --execute
```

The first command validates the build without a write. The second creates a fresh parentless Git repository in the new stage, creates **only** `Whyme-Labs/hadamard-exposition-public` as private, verifies the remote commit, then changes only that new mirror to public. Before upload, it checks every committed blob against the verified payload, disables global Git content filters and ignores inherited Git directory overrides. It refuses an existing stage or repository rather than overwriting it. It records an anonymous public observation and the stable full-commit article URL in a sibling publication receipt. A failed partial publication preserves its progress for inspection; do not blindly rerun into an existing stage.

This command does not submit to MathDB, create a prize claim, grant candidate status, configure GitHub Pages or create a release tag. After publication, attach its exact commit, material URL and observed UTC evidence to the existing award dossier and the authorized content-review submission. The historical preparation date is not public priority.

## Verification scope

Release-boundary tests use tiny Git fixtures. Their synthetic publisher receipts are intentionally test fixtures, not scientific evidence. Only a passing real-payload `validation.json` from the builder qualifies publication. Internal review is not external academic or committee review.

The payload scanner checks high-confidence credential patterns on the actual exported bytes. It is not a full secret audit, an entropy scan or an inspection of the excluded private history. Historical issue links in the unchanged article still point to the private research tracker; all local dependencies are included and checked.

The automated workflow is bounded to ten minutes, uses pinned action commits and has read-only repository permission. It does not contain publication credentials. A CI launch failure with no executed steps is recorded as an execution blocker, never a scientific pass.

## Current acceptance state

The release tooling is implemented and locally tested. The actual scientific bundle is not yet accepted or published. The first hosted attempt failed before executing a step; its cause was not exposed by the connector. Do not interpret a fixture-test pass or the existence of these scripts as a successful real-payload reproduction. Keep PR #13 and issue #11 open until their remaining gates pass.
