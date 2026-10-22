# v3 internal review, 22 October 2026

An independent AI referee reviewed the draft without seeing the author's reasoning, and the author re-checked the citations. This is AI self-review, not external peer review.

## Verified as correct

- Every proof in Parts I and III. The referee recomputed the order-12 matrix and its determinant, each step of the Paley proof, the Williamson example, and the counterexample table in exact rational arithmetic.
- The classical-order counts from `known_orders.py`.

## Fixed

| Finding | Fix |
|---|---|
| De Launey [22] misdescribed as an exceptional-set result | Positive-density statement; published version cited |
| De Launey-Gordon [21] logic reversed | The bound comes from Paley products; other methods do not improve it; positive density is open |
| Seberry's explicit bound stated as proved | Existence stands; Jensen (2007) shows the stated threshold does not follow for composite odd parts |
| Order 428 dated 2005 | Found 2004 with Turyn-type sequences, published 2005 |
| "Best possible value is $1/\sqrt n$" | Stated as a lower bound; the minimum is strictly larger when no Hadamard matrix exists |
| "Normalized" used in two senses | Use $H/\sqrt n$ |
| Implied that Paley first reached order 12 | Hadamard's orders 12 and 20 (1893) and Scarpis (1898) added |
| Six missing orders presented without history | Identified as Paley's own list; 172 (1944), 92 (1962), 184 by doubling; the 1000 count is qualified as depending on which product rules are counted |
| Naive probability heuristic | Notes that the independence heuristic predicts zero and fails; dependence explained |
| Asymptotic chain incomplete | Craigen-Tiessen 3/8, Livinskyi 1/5, and an unpublished 2024 claim of 3/20 |
| Signed groups listed as order-producing | Moved to the asymptotic results |
| 668 product argument | Uses the factorizations 2·334 and 4·167 |
| Williamson hypotheses redundant | Circulants commute automatically |
| Missing Williamson conjecture, Baumert-Hall/T-sequences, skew frontier | Added |
| Exact verifier path, bibliography details, letter $s$ used for both a sign and the scale | Fixed |

## Open

- [21] and [23]: journal volume and pages not confirmed online. [3], [6]–[8], [11]–[13], [16]–[19] and the Scarpis and Agaian references were checked against the referee's and author's knowledge, not the original texts.
- Review by a human specialist in Hadamard matrices is still recommended before freezing a v3 source edition.
