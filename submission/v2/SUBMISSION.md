# JSP-000013 Exposition review request

Title: *What the Hadamard conjecture promises*.
Subtitle: *The best possible spreading, and why it does not guarantee better rounding*.
Author: Wei Meng Soh, Whyme Labs.
Category: Exposition. MathDB problem 315867, Hadamard conjecture.
Version: 2 with the separately dated all-Hadamard addendum, with byte identities in `MANIFEST.json` and `SHA256SUMS`.
Public URL and publication date: not yet established. Consult `PUBLICATION.json` rather than using the manuscript preparation date as public priority.

## Requested review

Please review this article as an explanation of JSP-000013. It does not claim a solution or complete formalization. The article begins with the conjecture itself, proves its elementary necessary order condition, connects existence to an exact optimization objective, and supplies a complete prime-field Paley construction and an explicit order-12 example.

The all-Hadamard addendum strengthens the counterexample from one construction to every real Hadamard matrix at each existing order, using a complete three-row counting proof. The same fixed input works across this class.

The application sections explain why optimal coordinate spreading does not imply optimal rounding. They prove a dimension- and sign-uniform counterexample family, give a linear-layer corollary with both operands quantized, and report a preregistered-within-the-private-project synthetic comparison on 100 previously unused seeds. Full favorable and unfavorable measurements are included.

## Contribution and attribution map

| Material | Contribution boundary |
|---|---|
| Necessary order, Sylvester construction, determinant and flatness equivalence, Paley construction | Established mathematics, attributed and explained with complete proofs |
| Closed-form counterexample family and linear-layer corollary | Derivations prepared for this exposition, with no first-discovery claim |
| 100-seed comparison across Hadamard, Haar, permutation and original bases | Original synthetic study, not real-model validation or a new algorithm |
| Exact interactive calculator and inspectable reproduction package | Teaching and verification artifacts |
| Internal checks, numerical audit and self-review | Not external academic peer review or committee selection |

## Suggested review questions

Does the first half explain the open conjecture independently of the application? Are the hypotheses and proof of the counterexample family correct? Does the application distinguish a peak bound from realized quantization error? Are the established sources and the scope of the synthetic study clear? Can a reader reproduce the results without access to the private research repository?

## Official handoff

The official MathDB process requires a stable material link, fixed version, public date, authorship, topic, sources and content review. Committee selection is a separate requirement. This prepared note is not a submitted claim, committee decision, candidate record or award.

After public release, record the stable URL, full public commit and independently observable publication time in a separate publication record. Submit the exact reviewed version through the authorized content-review route. Do not substitute the original private commit date for public publication, and do not count a public-review period before administrators publish a candidate record.

Official process reference: https://github.com/TheJustinSunPrize/awards/blob/main/docs/award-process-mathdb.md
