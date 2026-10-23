# Hadamard exposition v3

## What the Hadamard conjecture promises

Wei Meng Soh, Whyme Labs. Exposition candidate for JSP-000013 (MathDB problem 315867).

The exposition has three parts:

- **Part I** states the conjecture and proves the multiple-of-four condition and the flatness and determinant characterizations. It explains the equivalent design, code and orthogonal-array forms.
- **Part II** surveys what is known. It covers the Sylvester, Paley and Williamson constructions and the 1962 order-92 search, the frontier from order 428 to the twelve orders below 2000 settled in 2026 and the smallest open order, now 2396, and the asymptotic and density results. It also explains why the problem is hard.
- **Part III** is an application. It proves that perfect balance does not guarantee lower quantization error, and summarizes a preregistered synthetic study, including its unfavorable results.

AI assistance is disclosed. The internal AI review is recorded in `submission/v3/REVIEW.md`; it is not external peer review or committee selection.

## Fixed source and assets

- Source edition: `submission/v3`, frozen from development commit `f9363186e7c8658daaf1efb57793523a2a5bca0d`. The release tag must point at a commit on the default branch that contains it unchanged.
- `hadamard-conjecture-v3.pdf`, 15 pages, SHA-256 `d2feda9e7bf6d81ee392683239f4520d368d1617836eda771cde6da6fe565fb0`.
- `hadamard-conjecture-v3.html`, standalone with the exact calculator, SHA-256 `617a6a21383e8b5f650d4bd15a37b00fa9e71e16d3733d80c5936c09a94947bc`.
- `submission/v3/SHA256SUMS`, SHA-256 `f29e9b2699f07b412c411a5fd63e3e979aa5451d236436e8f0be95ed0faf6398`.
- Part III evidence: `submission/v2`, unchanged, with its own checksums and audit.

Attach the PDF and HTML from `submission/v3` without rebuilding them. A suggested tag name is `exposition-v3`.

## Claim boundaries and licensing

This release does not solve the Hadamard conjecture, construct a new order, provide a formalization, claim priority for the counterexample, or establish real-model performance. Creating the release is not an official submission, candidate selection or award.

Text and data use CC BY 4.0; original code uses MIT. See `submission/v3/LICENSE.md`.
