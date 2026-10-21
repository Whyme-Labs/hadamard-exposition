# Hadamard exposition

## Read and verify the committed submission

The [v2 submission source edition](submission/v2/README.md) is committed directly in this repository. It includes both manuscripts, all 7,600 raw measurements, the exact local-run receipt, source, tests, citation metadata and licenses. Its 41 copied files match the accepted archive byte for byte; the three additional files provide the reader entry point, source manifest and checksums. The rendered PDFs and HTML remain separate release assets, not files in this source edition.

To verify the committed evidence without rerunning the experiment:

```bash
cd submission/v2
python -m pip install -r requirements-v2.txt
python -m unittest discover -s strengthening -p 'test_*.py' -v
python strengthening/audit_study.py run-v2
sha256sum -c SHA256SUMS
```

The raw-data audit checks all 19 settings and reconstructs 589 scalar summary fields. This directory is an immutable submission snapshot, not a second development copy. Make future scientific revisions under a new submission version rather than editing these recorded results.

## Current submission candidate

**What the Hadamard conjecture promises** explains the conjecture through optimal coordinate spreading, determinant equality and an explicit Paley construction, then connects the mathematics to quantization error.

Read the [v2 manuscript](strengthening/conjecture-companion.md), followed by the [all-Hadamard addendum](strengthening/all-hadamard-addendum.md). The addendum proves that the same fixed counterexample works for every real Hadamard matrix at each existing order, not only one recursive construction. This does not prove existence at unknown orders or claim literature priority.

The [release acceptance record](validation/2026-10-21-v2-release/README.md) and [machine-readable milestone](validation/2026-10-21-v2-release/milestone.json) identify the locally validated 49-file package. It includes the 10-page article, 3-page addendum, standalone HTML, interactive calculator, all raw observations, original source, verification tools, licenses and submission note.

The prespecified v2 study uses 100 seeds disjoint from the original 20, four transform arms and 19 settings. At its primary synthetic outlier setting, mean relative squared output error changes from 2.606175% to 1.355898%, a 47.9737% reduction. Haar rotation also helps; Gaussian and grid-aligned negative outcomes remain in the article. No real-model quality, speed or memory result follows.

## Validate and build

```bash
python -m pip install -r requirements-v2.txt
python -m unittest discover -s strengthening -p 'test_*.py' -v
python strengthening/study.py --output new-v2-run
python strengthening/audit_study.py new-v2-run
python strengthening/all_hadamard_checks.py > new-all-hadamard-checks.json
```

The mathematics and experiments need Python and NumPy, no GPU, model download or external dataset. Use new output paths. The execution order is local assistant environment first, home CI second, Blacksmith last.

To build the complete candidate with HTML/PDF and browser checks, also install Node.js, Pandoc, Playwright and Chromium at `/usr/bin/chromium`, then run:

```bash
python -m unittest discover -s release -p 'test_v2.py' -v
python release/build_v2.py --output build/v2-candidate-new
```

The public package's [README template](release/v2/README.md), [submission note](release/v2/SUBMISSION.md), [citation metadata](release/v2/CITATION.cff) and [license map](release/v2/LICENSE.md) define the publication surface. CC BY 4.0 applies to the original exposition and data; MIT applies to original code. No private research history enters the generated package.

## Publication and claim limits

Use this existing repository, not a second mirror, for the next release. The [publication audit and decision](publication/README.md) supersede the older mirror recommendation. The bounded review covered 60 commits, 352 file versions, nested archives and available workflow/discussion records. The [prepared release notes](publication/release-notes-v2.md) pin the exact candidate assets and scientific source commit.

The code/archive review found no confirmed credential leak. A live integration still restores signed Codesmith action footers after removal; its exposure policy remains unresolved. This is not a claim that those links are exploitable. The repository has not been made public, and the review does not certify that all possible confidential data is absent.

[Issue 11](https://github.com/Whyme-Labs/hadamard-exposition/issues/11) owns publication in this repository and authorized submission. The local package has passed its acceptance checks. A stable public release, observable publication date, authorized content review and committee selection have not happened. A private commit or passing test is not an award claim.

This work targets Exposition for JSP-000013. It claims neither a solution of the general Hadamard conjecture nor a complete Lean formalization. AI assistance is disclosed in the manuscript. Internal checks and self-review are not academic peer review or prize committee review.

## Preserved earlier work

The [previous README at its fixed commit](https://github.com/Whyme-Labs/hadamard-exposition/blob/12f0463020cfb6e81f9ce2178386668f9b60c27f/README.md) retains the full v1 results, reproduction instructions and Pythia campaign history. The frozen [v1 article](article.md), [standalone v1 HTML](exposition.html), [reference results](results.json), [group-size results](group-results.json) and source files are unchanged.

The unfinished pretrained-model campaign remains in issue 5 and is not required for this exposition release. The historical v1 award dossier remains under `docs/awards/`; it does not supersede the current v2 acceptance record or the same-repository publication decision.
