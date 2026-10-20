# JSP-000013 curated public release plan

## Recommendation

Publish a small public mirror rather than changing this entire research repository from private to public.

The full repository is about 14.9 MiB and contains internal benchmark development, failed attempts, environment receipts, dependency provenance, compressed evidence, and incomplete pretrained-model work. Those records are useful for research traceability, but they make the exposition harder to review and expand the privacy and redistribution surface without strengthening the Exposition submission.

A curated mirror gives reviewers the complete article, citations, exact counterexamples, reproducible synthetic experiments, and validation evidence. It excludes model-development material that the submission does not claim as a result.

## Bounded publication-safety audit

On 20 October 2026, code search on the default branch returned no matches for these common indicators:

- `BEGIN PRIVATE KEY`
- `api_key`
- `password`
- `secret`
- `ghp_`
- `sk-`
- `HF_TOKEN`
- `gmail.com`
- `/home/`

This is a bounded text scan, not a complete secret scanner. It does not inspect the contents of compressed archives or measure string entropy. The repository also has no committed `LICENSE` file and no declared repository license. These two facts are enough to prefer an allowlisted mirror over publishing every retained artifact.

## Public mirror allowlist

Copy these files from merge commit `e442d1b74bc0cf3fe2c103a96d961341d570c5d2`. Do not rebuild the frozen article or standalone HTML.

### Reader-facing material

- `exposition.html`
- `article.md`
- `sources.json`
- `CITATION.cff`
- `coordinate-example.png`
- `coordinate-example.svg`
- `quantization-results.png`
- `quantization-results.svg`
- `group-size-results.png`
- `group-size-results.svg`
- `style.css`
- `calculator.html`
- `calculator-verification.json`

### Reproducible synthetic experiment

- `experiment.py`
- `group_experiment.py`
- `results.json`
- `group-results.json`
- `requirements.txt`
- `test_verify_results.py`
- `test_group_experiment.py`
- `verify-calculator.cjs`
- `scripts/build_article.py`
- `scripts/validate.py`
- `scripts/verify_results.py`
- `docs/experiments/group-size-v1.md`
- `validation/2026-10-17-group-size.json`

### Submission dossier

- `docs/awards/README.md`
- `docs/awards/jsp-000013-exposition-submission.md`
- `docs/awards/jsp-000013-publication-manifest.json`
- `docs/awards/jsp-000013-reviewed-content.md`
- `docs/awards/jsp-000013-public-release-plan.md`

The public mirror should use a short landing `README.md` written from the submission dossier. Do not copy the private repository's root README unchanged because it gives substantial space to the incomplete Pythia campaign.

## Explicit denylist

Do not copy these paths into the first public exposition release:

- `benchmarks/`
- `requirements-benchmark.txt`
- `requirements-model-converter.txt`
- `docs/experiments/model-benchmark-v1.md`
- `docs/experiments/model-execution-v1.md`
- `validation/2026-10-17-model-benchmark/`
- `validation/2026-10-17-model-campaign/`
- `validation/2026-10-18-campaign-development/`
- `validation/2026-10-18-environment-recovery/`
- all compressed raw-evidence and dependency-provenance archives outside the allowlist
- all branches, pull-request discussions, and issue histories unless deliberately selected later

This denylist is about scope and publication hygiene. It does not imply that those files are unsafe or invalid.

## License gate

Choose and commit public licenses before the mirror becomes visible. The recommended simple split is:

- CC BY 4.0 for the article, figures, and explanatory documentation.
- MIT for the experiment and validation code.

The public README should state the split clearly and identify which files each license covers. Do not add license text to the private source package without the author's approval because licensing changes the rights granted to the public.

## Immutable release procedure

1. Create the public mirror as private or locally first.
2. Copy only the allowlisted paths from commit `e442d1b74bc0cf3fe2c103a96d961341d570c5d2`.
3. Add the approved license files and a concise public landing README.
4. Verify that the article blob is `c35b5a157cec7c96b23d5ec94969ea934b881380` and the standalone HTML blob is `9c36728e24ca82f528fe8205b849762f30bfc806` before the first public push.
5. Compute SHA-256 digests for the public files and retain the digest list in both repositories.
6. Make the mirror public in one operation. Record the first independently accessible UTC time.
7. Create an immutable release tag for that first public commit.
8. Update the private publication manifest with the public repository, commit, tag, stable article URL, SHA-256 digest, and UTC date.
9. Replace the three publication placeholders in the submission draft.
10. Submit that exact public version through the authorized prize route when available.

## Acceptance criteria

The public release is ready only when:

- the standalone article opens without authentication;
- its article and HTML bytes match the frozen reviewed artifacts;
- the author and license are visible;
- sources and original contributions are identified;
- favorable and unfavorable results remain present;
- the reproduction command works from the public file set;
- the public timestamp is independently observable;
- no wording implies a solution, formal proof, candidate selection, award, or payment;
- the private publication manifest points to the exact public release.

Until those conditions hold, issue 11 remains open and the repository should describe the package as a private submission candidate.