# What the Hadamard conjecture promises

**The best possible spreading, and why it does not guarantee better rounding**

Wei Meng Soh, Whyme Labs. Version 2. Prepared 21 October 2026.

Open `exposition-v2.html` in a browser for the complete article and exact interactive calculator. `exposition-v2.pdf` is the print edition. Read `all-hadamard-addendum.html` or `all-hadamard-addendum.pdf` next for the stronger theorem covering every real Hadamard matrix of a given order, including non-power-of-two orders. The v2 manuscript is unchanged; this addition has its own source and exact witnesses.

The editable manuscript is `strengthening/conjecture-companion.md`.

## Read the mathematics before the percentage

The article explains the conjecture through a precise optimization problem, proves the necessary order condition, and constructs an explicit order-12 matrix with Paley's prime-field construction. These are attributed explanations of established mathematics.

It then proves a counterexample family. The separately dated addendum removes the Sylvester restriction by a three-row balance argument. The same fixed input fails for every order-n Hadamard matrix, conditional only on that matrix existing. For every power-of-two dimension at least four, every bit width at least three, and every diagonal sign choice, the constructed input has a lower transformed peak but a positive reconstruction error where its original error was zero. A linear-layer corollary also quantizes both operands. The proof does not claim literature priority.

The prespecified numerical study uses 100 seeds not used in the earlier 20-seed study, competing transforms, matched scale counts and negative controls. In the primary constructed-outlier setting, mean relative squared output error changes from 2.606175% to 1.355898%, a 47.9737% reduction. Haar rotation also helps. The Gaussian degradation and the grid-aligned failures remain visible.

## What these files establish

`run-v2/` contains every one of the 7,600 measurements, input hashes, 19 setting summaries, exact construction checks and an execution receipt. This bundle includes a fresh execution of the already registered v2 seeds. It is a same-protocol reproduction, not a third independent dataset. The first v2 local run is recorded separately in the research history. No public priority is inferred from a private commit date.

`verification/audit.json` reconstructs all 589 scalar summary fields from the raw cells. It also checks coverage, source bindings, finite controls and the order-12 determinant using separate rational elimination. Hashes bind bytes; they do not authenticate execution or establish mathematical correctness on their own.

`all-hadamard-checks.json` records 1,280 rational checks of the stronger theorem, including Paley orders 12, 20, 24 and 44 and row/column sign and permutation variants.

`family-checks.json` and `family-linear-checks.json` contain the same newly recomputed exact witness report, including both reconstruction and linear-layer checks. Their names preserve the article's reproduction pointers; they are not two independent experiments.

AI assistance was used in writing, derivation, implementation and verification. Automated checks and self-review are not external academic peer review, learner testing or prize committee approval.

## Reproduce locally

Python and NumPy are sufficient for the mathematics and experiment. Install the pinned dependency, then run:

```bash
python -m pip install -r requirements-v2.txt
python -m unittest discover -s strengthening -p 'test_*.py' -v
python strengthening/audit_study.py run-v2
python strengthening/study.py --output new-run
python strengthening/audit_study.py new-run
python strengthening/counterexample_family.py > new-family-checks.json
```

Always use a new output directory. The study requests one BLAS thread and has an internal 180-second limit. On Linux, use `timeout 180s python strengthening/study.py --output new-run` for an outer process deadline.

Node.js checks the actual embedded calculator:

```bash
node strengthening/verify_lab.cjs exposition-v2.html
```

The already generated HTML and PDF need no build tools for reading. Rebuilding HTML requires Pandoc. Optional layout/PDF checks require Playwright and Chromium at `/usr/bin/chromium`. Those tools are not needed for the numerical experiment.

## Scope and license

This is an Exposition submission candidate for JSP-000013, not a solution of the general Hadamard conjecture or a new quantization method. It reports no pretrained-model quality, throughput or memory-saving result. No award probability, committee selection, submission receipt or payment is asserted.

The article, explanatory text and numerical records use CC BY 4.0. Original executable code uses MIT. See `LICENSE.md` for composite-file treatment. Third-party references retain their own terms.

`MANIFEST.json` and `SHA256SUMS` identify the package bytes. `PUBLICATION.json` deliberately has no public URL or publication date until an independently accessible release exists. `SUBMISSION.md` contains the category, contribution map and review request.
