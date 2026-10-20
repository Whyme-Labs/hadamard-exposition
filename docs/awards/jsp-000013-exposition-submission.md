# JSP-000013 exposition submission draft

## Submission identity

- Problem: JSP-000013, Hadamard matrix conjecture
- MathDB problem: 315867, Hadamard conjecture
- Category: Exposition
- Title: *What changes when the answer stays the same*
- Subtitle: *Hadamard matrices, quantization, and the price of a representation*
- Author: Wei Meng Soh, GitHub `wms2537`
- Affiliation: Whyme Labs
- Material: standalone illustrated article with an interactive calculator, editable manuscript, source map, reproducible experiments, retained results, and validation receipts
- Fixed scientific source commit: `5ec28b8f5a0dbed51630fc94e270a2a2462c37f3`
- Fixed scientific source tree: `d0490c2647f8c067dfc6b5fde1d69730fa7ab932`
- Stable public material URL: pending public release
- Public publication date in UTC: pending public release

The manuscript displays 17 October 2026 as its preparation date. That date is part of the document history. It is not represented here as a public publication date because the repository was private when this dossier was prepared.

## Submission summary

This exposition explains what Hadamard matrices are, why every nontrivial order above two must be divisible by four, what the Hadamard conjecture asks, and why known infinite constructions do not settle the conjecture. It then connects normalized Hadamard matrices to orthogonal changes of basis in linear algebra.

The central teaching example is deliberately narrower than the open conjecture. An orthogonal basis change can leave an exact linear product unchanged while changing the error introduced by a coordinatewise quantizer. The article proves the exact identity, derives a concentration bound for randomized signs, states its assumptions, and tests the mechanism in a small reproducible experiment.

The exposition also shows where the mechanism fails. The exact vector `[7, 1, 1, 0]` has a lower coordinate peak after a normalized Hadamard transform but worse realized quantization error. A separate grid-aligned synthetic case has zero error in the original basis and nonzero error after transformation. These counterexamples prevent the article from implying that Hadamard mixing always helps.

## What is original in this material

The submission does not claim a new solution of the Hadamard conjecture. Its original contribution is the explanatory and experimental package:

1. A concrete bridge from the conjecture and elementary Hadamard identities to representation-dependent numerical approximation.
2. An exact rational counterexample showing that a lower peak and a tighter general error bound can coexist with worse realized quantization.
3. A paired, reproducible synthetic experiment that includes a Gaussian control, a persistent-outlier case, and a grid-aligned failure case.
4. A prespecified group-size sensitivity study that holds the transform, data, signs, bit count, and rounding rule fixed while giving both bases equal numbers of quantization scale groups.
5. A standalone article with embedded display assets and an interactive four-coordinate calculator, plus machine-readable results and independent verification code.
6. Explicit claim boundaries separating exact algebra, probabilistic statements, synthetic measurements, generated operator checks, incomplete pretrained-model work, and the still-open conjecture.

## Main explanatory result

For a linear layer `Y = XW` and a compatible orthogonal matrix `Q`, define

`X_r = XQ` and `W_r = Q^T W`.

Then

`X_r W_r = X Q Q^T W = XW`.

The exact output is unchanged. Quantization is not invariant under the same transformation because its rounding cells and scale groups depend on coordinates.

In the constructed persistent-outlier experiment, the full-width group-128 comparison reduced mean relative squared output error from 8.030172% to 1.999829%. In the prespecified group-32 comparison, the mean fell from 2.656032% to 1.419916%, a 46.54% reduction. Rotation helped in all 20 outlier seeds at every tested group size.

The Gaussian controls did not show a systematic advantage. The grid-aligned case became worse after rotation. The article presents all cases rather than selecting only the favorable result.

## Scope and claim limits

This submission claims an exposition, not a solution.

- It does not prove that a Hadamard matrix exists for every positive multiple of four.
- It does not supply a complete Lean formalization of the conjecture.
- It does not claim that basis rotation universally improves quantization.
- It does not infer language-model quality or hardware speed from the synthetic experiment.
- It does not report a completed Pythia quality or inference-cost result. The retained pretrained campaign stopped at a reference cached-decoding control.
- It does not claim committee approval, candidate status, an award, or payment.

## Primary material

- Standalone reviewed article candidate: [`exposition.html`](../../exposition.html)
- Editable manuscript: [`article.md`](../../article.md)
- Source map: [`sources.json`](../../sources.json)
- Reference experiment: [`experiment.py`](../../experiment.py) and [`results.json`](../../results.json)
- Group-size study: [`group_experiment.py`](../../group_experiment.py), [`group-results.json`](../../group-results.json), and [`docs/experiments/group-size-v1.md`](../experiments/group-size-v1.md)
- Independent retained-result verifier: [`scripts/verify_results.py`](../../scripts/verify_results.py)
- Complete validation entry point: [`scripts/validate.py`](../../scripts/validate.py)
- Retained exposition validation receipt: [`validation/2026-10-17-group-size.json`](../../validation/2026-10-17-group-size.json)

## Review evidence

The original exposition and group-size milestone were reviewed on two separate axes before publication in pull request 3:

- A standards review checked preservation, failure handling, source identities, and separation between result production and verification.
- A specification review checked arithmetic, reported settings, uncertainty calculations, scale counts, and an independent exact-integer Hadamard construction.

The reviewed content commit was `554beb2647eb5430de20bddeea3df100c163725c`. Its article and standalone HTML blobs are the same blobs recorded in this dossier's publication manifest.

Later campaign work received further independent agent reviews and retained exact source and evidence bindings. Those later reviews support the repository's research discipline. They do not convert the incomplete model campaign into a result, and they are not represented as prize committee review or external academic peer review.

## Reproduction

For the exposition and synthetic result package:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/validate.py --reproduce
```

Node.js is required for the calculator check. The command verifies retained results, exercises the bundled calculator JavaScript, runs the focused tests, and reproduces the group-size sweep in a temporary directory under fixed thread and time limits.

## Submission text for the official entry point

> I submit *What changes when the answer stays the same* for the Exposition category of JSP-000013, the Hadamard matrix conjecture. The material explains the conjecture and its elementary necessary condition, distinguishes known constructions from the unresolved universal statement, and develops a concrete application of normalized Hadamard changes of basis to quantization error. It includes an exact counterexample to universal improvement, a reproducible paired synthetic experiment, a prespecified group-size sensitivity study, source citations, retained result data, and validation code. The submission does not claim a solution or a complete formalization. Author: Wei Meng Soh, Whyme Labs. Fixed version: [PUBLIC_FIXED_VERSION]. Stable material: [PUBLIC_STABLE_URL]. Public publication date: [PUBLIC_UTC_DATE].

Replace only the three bracketed publication fields after creating an immutable public release. Do not replace them with private repository links.
