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

## Citation verification

Every reference was checked against registry or publisher metadata: Crossref, arXiv, PMLR, the authors' and publishers' pages, and secondary bibliographies. DOIs were added where they exist. This found and fixed one further error. The complete order-32 classification is Kharaghani and Tayfeh-Rezaie, J. Combin. Des. 21 (2013), not their 2010 partial classification. Scarpis (1898) is confirmed only through secondary bibliographies, and the reference says so. Venues were added for QuIP# (ICML 2024) and SpinQuant (ICLR 2025).

## Primary-source check, 23 October 2026

Three agents checked each sourced claim against the cited texts and quoted the supporting passage.

- **Read in the original:**
  - Hadamard 1893, Sylvester 1867, Paley 1933 and Scarpis 1898, from archive.org scans.
  - Baumert-Golomb-Hall 1962, downloaded from the AMS site with a headless browser. Its printed first rows reproduce a Hadamard matrix of order 92, now a test.
  - Goethals-Seidel 1970, Seberry 1976, Jensen 2007, the order-428 paper and Livinskyi's thesis.
  - The arXiv versions of Đoković 2008, de Launey-Gordon, de Launey 2009, de Launey-Levin, Jaming-Matolcsi, Cati-Pasechnik and Du-Jiang.
- **Paywalled or behind a captcha; checked through abstracts and secondary sources:** Williamson 1944, Turyn 1972, Đoković 1993, Holzmann-Kharaghani-Tayfeh-Rezaie 2008 and Craigen 1995.

**Material finding.** The frontier was out of date. In August 2026 Hadamard matrices were announced at the twelve open orders below 2000, including 668. Egan, Kotsireas, London and Ó Catháin verified them in October 2026, and their survey lists 2396 as the smallest open order. The frontier, introduction, hardness example and summary were rewritten.

**Other fixes:**
- Order 428 used a Goethals-Seidel array, not a Baumert-Hall array. Order 764 was posted in 2007.
- Jensen's correction applies already for primes $p\equiv1\pmod4$.
- Craigen's coefficient is $2/3$. Livinskyi's $1/5$ is disputed by a 2024 preprint.
- Paley's statement of the conjecture is now quoted, and his list of unsettled orders is cited to his Lemma 6.
- Williamson's 1944 order 172 is no longer attributed to a specific construction. The Williamson conjecture is stated for all orders $4m$.
- The Goethals-Seidel array is described as introduced for skew-Hadamard matrices. Turyn's family is stated, and Hadamard's complex-entry bound is noted.

## Open

- Review by a human specialist in Hadamard matrices is still recommended. Five cited papers were checked only through abstracts and secondary sources.
