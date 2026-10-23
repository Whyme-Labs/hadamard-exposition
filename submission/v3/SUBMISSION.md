# JSP-000013 Exposition review request

Title: *What the Hadamard conjecture promises*.
Subtitle: *Perfect balance, the orders we can reach, and why balance does not guarantee better rounding*.
Author: Wei Meng Soh, Whyme Labs.
Category: Exposition. MathDB problem 315867, Hadamard matrix conjecture.
Version: 3, with byte identities in `SOURCE-MANIFEST.json` and `SHA256SUMS`.
Public URL and publication date: recorded separately after public release. `PUBLICATION.json` is the frozen pre-publication record and does not give a public date.

## Requested review

Please review this article as an explanation of JSP-000013. It does not claim a solution, a new order, or a formalization.

- **Part I** states the conjecture and proves the necessary multiple-of-four condition. It proves the flatness and determinant characterizations and describes the equivalent design, code and orthogonal-array forms.
- **Part II** explains what is known:
  - Kronecker products and Sylvester doubling.
  - A complete proof of Paley's prime-field construction, with an explicit order-12 matrix.
  - The exact reach of the classical constructions.
  - Williamson's method, the 1962 order-92 search and the failed Williamson conjecture.
  - The computational frontier, from order 428 to the twelve orders below 2000 settled in 2026, and the smallest open order, now 2396.
  - Asymptotic and density results, related open problems, and why the problem is hard.
- **Part III** is an application. It proves that one fixed input loses quantization accuracy under every Hadamard matrix of each existing order, and summarizes a preregistered synthetic study with both favorable and unfavorable results.

## Contribution and attribution map

| Material | Contribution boundary |
|---|---|
| Necessary order, flatness and determinant characterizations, equivalent forms, Sylvester, Paley and Williamson constructions | Established mathematics, credited and explained, with proofs where short |
| Historical, frontier and asymptotic survey | Exposition of published results, with sources |
| `known_orders.py` reach computation and Williamson checks | Teaching and verification tools |
| All-Hadamard quantization counterexample | Derivation prepared for this exposition; no first-discovery claim |
| 100-seed synthetic study (version 2 evidence, unchanged) | Original synthetic study, not real-model validation or a new algorithm |
| Internal AI review (`REVIEW.md`) | Not external academic peer review or committee selection |

AI assistance was used in writing, derivations, code and internal review, and is disclosed in the article.

## Suggested review questions

Does Part I explain the conjecture and its significance to a reader new to it? Is Part II an accurate and fair account of the state of the problem? Are the proofs correct and the sources adequate? Is the application clearly separated from the conjecture itself?

## Official handoff

The official MathDB process requires a stable material link, a fixed version and publication date, authors and topic, cited sources and the reviewed content. Committee selection is separate. This note is not a submitted claim, committee decision, candidate record or award.

Official process: https://github.com/TheJustinSunPrize/awards/blob/main/docs/award-process-mathdb.md
