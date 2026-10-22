# Hadamard exposition v2: manuscript and reproducible evidence

Wei Meng Soh, Whyme Labs. Exposition candidate for JSP-000013.

## Read the submission

Start with [What the Hadamard conjecture promises](strengthening/conjecture-companion.md), then read [the all-Hadamard addendum](strengthening/all-hadamard-addendum.md). GitHub renders both Markdown articles, including their equations. The [submission note](SUBMISSION.md) identifies the category, contribution boundaries, sources and requested review.

This directory is a self-contained source edition extracted from the accepted v2 package. It includes the unchanged manuscripts, source, all 7,600 measurements and their exact local-run receipt. It does not rely on a private evidence branch or a conversation download to validate the numerical results.

## Inspect the evidence

- [Every measurement](run-v2/cells.csv), [all 19 setting summaries](run-v2/summary.json), and [input and transform identities](run-v2/inputs.json).
- [Original local reproduction receipt](run-v2/receipt.json) and [589-field independent audit](verification/audit.json).
- [Exact construction checks](run-v2/exact-checks.json) and [rational family witnesses](family-linear-checks.json).
- [Registered experimental protocol](strengthening/protocol-v2.json) and [the all-Hadamard checker](strengthening/all_hadamard_checks.py).

The original v2 sample uses seeds 1000 through 1099, disjoint from v1's 0 through 19. The retained run here is the same-protocol local reproduction completed on 21 October 2026, not a new dataset. At the primary synthetic outlier setting, mean relative squared output error changes from 2.606175% to 1.355898%. The Gaussian and grid-aligned unfavorable outcomes remain included.

The theorem and synthetic study are contributions to an exposition. They do not solve the general Hadamard conjecture, establish literature priority, or measure real-model speed or quality. AI assistance is disclosed. Internal validation is not external peer review or prize committee selection.

## Validate from this directory

```bash
python -m pip install -r requirements-v2.txt
python -m unittest discover -s strengthening -p 'test_*.py' -v
python strengthening/audit_study.py run-v2
sha256sum -c SHA256SUMS
```

A fresh run needs a new output directory:

```bash
python strengthening/study.py --output new-run
python strengthening/audit_study.py new-run
python strengthening/all_hadamard_checks.py > new-all-hadamard-checks.json
```

The numerical work needs Python and NumPy, no GPU or external dataset. The unmodified study requests one BLAS thread and has an internal deadline. Use an outer process timeout where required.

A fresh run should pass the audit, but its `cells.csv` need not match `run-v2/cells.csv` byte for byte. Values can differ in the last floating-point digits across NumPy versions, BLAS builds and platforms; a rerun with NumPy 2.5.3 differed by at most 6.2e-16 per error value. Compare values numerically or use the audit, not `cmp` or file digests.

## Source edition and rendered files

The accepted archive has SHA-256 `6074fcc3745e756765bd676be051d04b72c3c29314dd6094b64ef555af29b044`. This source edition copies 41 files from that archive without changing their bytes. It adds this README, `SOURCE-MANIFEST.json` and its own `SHA256SUMS`. It is not the complete 49-file archive.

The two PDFs, two rendered HTML files and large generated all-Hadamard witness JSON are not committed in this source edition. The manuscripts and generation code are included. The accepted rendered editions remain identified in [the release notes](../../publication/release-notes-v2.md). Browser, calculator and unit-test receipts under `verification/` are preserved historical records from that accepted package, not claims of a new rendering during this commit.

To render HTML from the included source, install Pandoc and run `python strengthening/build_article.py`; Node.js can then run `node strengthening/verify_lab.cjs exposition-v2.html`. PDF generation additionally requires Playwright and Chromium. New PDF metadata may differ from the accepted PDF, so do not relabel a rebuild with its earlier digest.

The two family JSON files intentionally contain the same original report for compatibility with the article's pointers. They are not independent experiments. `SOURCE-MANIFEST.json` identifies every copied Git blob and lists the original files omitted from this edition; `SHA256SUMS` records the source-edition SHA-256 digests.

[License map](LICENSE.md): CC BY 4.0 for original exposition and data; MIT for original executable code. Third-party references retain their own terms.

Repository access and official submission are separate from this commit. `PUBLICATION.json` is the unchanged pre-publication record. No public date, official submission, committee selection or award is asserted here.
