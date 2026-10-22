# Hadamard exposition v3

## What the Hadamard conjecture promises

Wei Meng Soh, Whyme Labs. Exposition candidate for JSP-000013 (MathDB problem 315867).

The exposition has three parts:

- **Part I** states the conjecture and proves the multiple-of-four condition and the flatness and determinant characterizations. It explains the equivalent design, code and orthogonal-array forms.
- **Part II** surveys what is known. It covers the Sylvester, Paley and Williamson constructions and the 1962 order-92 search, the frontier from order 428 to the open orders 668, 716, 892 and 1132, and the asymptotic and density results. It also explains why the problem is hard.
- **Part III** is an application. It proves that perfect balance does not guarantee lower quantization error, and summarizes a preregistered synthetic study, including its unfavorable results.

AI assistance is disclosed. The internal AI review is recorded in `submission/v3/REVIEW.md`; it is not external peer review or committee selection.

## Fixed source and assets

- Source edition: `submission/v3`, frozen from development commit `cae15edcf8aa861bed0c3389c8d3155024c1f6a2`. The release tag must point at a commit on the default branch that contains it unchanged.
- `hadamard-conjecture-v3.pdf`, 14 pages, SHA-256 `1661863090430be092dc8946ae0cbcb88abb5e3e219491db9d321a7162dbb3d3`.
- `hadamard-conjecture-v3.html`, standalone with the exact calculator, SHA-256 `ebd7600ab885d455e34b59aac56fc1262b7b0f26c7688d1f9d465d6b8446d2ed`.
- `submission/v3/SHA256SUMS`, SHA-256 `43a933a125e7bfc232b5fb712720c11f7515fdb97dd59efe40f9046f7e0af41d`.
- Part III evidence: `submission/v2`, unchanged, with its own checksums and audit.

Attach the PDF and HTML from `submission/v3` without rebuilding them. A suggested tag name is `exposition-v3`.

## Claim boundaries and licensing

This release does not solve the Hadamard conjecture, construct a new order, provide a formalization, claim priority for the counterexample, or establish real-model performance. Creating the release is not an official submission, candidate selection or award.

Text and data use CC BY 4.0; original code uses MIT. See `submission/v3/LICENSE.md`.
