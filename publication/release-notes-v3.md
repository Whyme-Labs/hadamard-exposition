# Hadamard exposition v3

## What the Hadamard conjecture promises

Wei Meng Soh, Whyme Labs. Exposition candidate for JSP-000013 (MathDB problem 315867).

The exposition has three parts:

- **Part I** states the conjecture and proves the multiple-of-four condition and the flatness and determinant characterizations. It explains the equivalent design, code and orthogonal-array forms.
- **Part II** surveys what is known. It covers the Sylvester, Paley and Williamson constructions and the 1962 order-92 search, the frontier from order 428 to the open orders 668, 716, 892 and 1132, and the asymptotic and density results. It also explains why the problem is hard.
- **Part III** is an application. It proves that perfect balance does not guarantee lower quantization error, and summarizes a preregistered synthetic study, including its unfavorable results.

AI assistance is disclosed. The internal AI review is recorded in `submission/v3/REVIEW.md`; it is not external peer review or committee selection.

## Fixed source and assets

- Source edition: `submission/v3`, frozen from development commit `b8f08eb1163f63174529736980ff42628cf17812`. The release tag must point at a commit on the default branch that contains it unchanged.
- `hadamard-conjecture-v3.pdf`, 14 pages, SHA-256 `dccd9940906f9b2a488a8b1c7e22554a38fda194d50853af3213e63c8716c294`.
- `hadamard-conjecture-v3.html`, standalone with the exact calculator, SHA-256 `1bdc8f914074ab4162b2d5252a81787d710846d3fd496f2670b8a55514de2da4`.
- `submission/v3/SHA256SUMS`, SHA-256 `5553fc8f932f8af4a4236c20357f8f49cc1b794508dc6321cddcc7ab3eea1293`.
- Part III evidence: `submission/v2`, unchanged, with its own checksums and audit.

Attach the PDF and HTML from `submission/v3` without rebuilding them. A suggested tag name is `exposition-v3`.

## Claim boundaries and licensing

This release does not solve the Hadamard conjecture, construct a new order, provide a formalization, claim priority for the counterexample, or establish real-model performance. Creating the release is not an official submission, candidate selection or award.

Text and data use CC BY 4.0; original code uses MIT. See `submission/v3/LICENSE.md`.
