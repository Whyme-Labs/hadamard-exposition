# What changes when the answer stays the same

Hadamard matrices, quantization, and the price of a representation.

Wei Meng Soh, Whyme Labs. Prepared with AI assistance for writing, experiment code and verification. This package is an exposition for JSP-000013, not a solution of the Hadamard conjecture or an award claim.

Open [index.html](index.html), then [the standalone article](exposition.html), in a browser. All article display assets are embedded. The [editable manuscript](article.md), [sources](sources.json) and [submission note](SUBMISSION.md) are included.

## What this explains

An orthogonal change of basis preserves an exact linear product. Rounding depends on the coordinates and quantization scale groups. The article explains the Hadamard conjecture, proves elementary identities, and tests this distinction with paired synthetic experiments. It retains favorable results, Gaussian controls and counterexamples rather than claiming universal improvement.

At group size 32, the constructed persistent-outlier experiment reduces mean relative squared output error from 2.656032% to 1.419916%. This is a synthetic error result, not language-model accuracy or measured inference speed. Every paired cell is in [group-results.json](group-results.json).

## Reproduce

Use Python 3.12, Node.js, and the pinned dependencies. The original recorded Python version is 3.12.14.

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/validate.py --reproduce
```

This checks the retained results, executes the actual calculator JavaScript and reproduces the group-size study. It writes a new receipt under `build/` without overwriting the retained scientific data. Pandoc is needed only to rebuild the HTML using `python3 scripts/build_article.py`; it is not needed to read the article or reproduce its numbers.

`MANIFEST.json` identifies every payload file except the manifest and checksum list themselves. `SHA256SUMS` covers the manifest and the remaining files. On a system with `sha256sum`:

```bash
sha256sum --check SHA256SUMS
```

## Version and review

The scientific article remains byte-identical to the reviewed preparation dated 17 October 2026. The author information on this landing page supersedes only the historical authorship-pending note inside that frozen draft. No scientific result has changed.

Historical issue links in the frozen article refer to the private research repository. They are not required to reproduce the bundled work. This public package contains no Git history, pretrained model, benchmark campaign archive or private discussion export.

The original project recorded internal AI-agent reviews. They are not external academic peer review, MathDB acceptance or prize-committee selection. Public distribution alone establishes none of those statuses. The preparation date is not a claim to public priority.

## License

[CC BY 4.0](LICENSE-CC-BY-4.0.md) covers the article, figures, explanatory documentation and result data to the extent the author holds the relevant rights. [MIT](LICENSE-MIT.txt) covers executable code, including the calculator JavaScript embedded in the HTML. The [license map](LICENSE.md) explains composite files and third-party material.
