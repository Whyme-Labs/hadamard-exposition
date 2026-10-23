# Hadamard exposition v3

Wei Meng Soh, Whyme Labs. Exposition candidate for JSP-000013.

## Read

- [What the Hadamard conjecture promises](hadamard-conjecture.md). The Markdown renders on GitHub, including equations.
- [PDF](hadamard-conjecture-v3.pdf) and [standalone HTML with the exact calculator](hadamard-conjecture-v3.html).
- [Submission note](SUBMISSION.md), [internal review record](REVIEW.md), [license map](LICENSE.md).

## Verify

From the repository root:

```bash
python -m pip install -r submission/v3/requirements-v3.txt
python submission/v3/known_orders.py --limit 200
python -m unittest discover -s submission/v3 -p 'test_*.py' -v
(cd submission/v3 && sha256sum -c SHA256SUMS)
```

Part III cites the version-2 counterexample checker and study evidence. Those are frozen, unchanged, in [`submission/v2`](../v2/README.md), with their own checksums and audit.

To re-render, install Pandoc, Playwright and Chromium, then run `build_article.py --output <path>` and `build_pdf.py --html <path> --output <path>`. A rebuilt PDF can differ in metadata, so do not give a rebuild the digest of the PDF frozen here.

## What this edition is

This directory is a frozen snapshot. `SOURCE-MANIFEST.json` names the development commit it was built from and the build environment. `SHA256SUMS` covers every other file. Make later revisions in a new version.

`PUBLICATION.json` is the pre-publication record and stays empty. Record the public release, its URL and an independently observed UTC time in a separate receipt. No public date, official submission, committee selection or award is asserted here.

CC BY 4.0 applies to the text and data; MIT applies to the code.
