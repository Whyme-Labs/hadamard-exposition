# JSP-000013 exposition content review dossier

This document evaluates the fixed exposition against the content requirements stated in the Justin Sun Prize MathDB process. It is a submission-readiness assessment. It is not a prize committee decision, MathDB acceptance, academic peer review, or candidate registration.

## Material under review

- Title: *What changes when the answer stays the same*
- Author: Wei Meng Soh, Whyme Labs
- Problem: JSP-000013, Hadamard matrix conjecture
- Category: Exposition
- Fixed source commit: `5ec28b8f5a0dbed51630fc94e270a2a2462c37f3`
- Standalone artifact: `exposition.html`, Git blob `9c36728e24ca82f528fe8205b849762f30bfc806`
- Manuscript: `article.md`, Git blob `c35b5a157cec7c96b23d5ec94969ea934b881380`
- Source map: `sources.json`, Git blob `e250d105d1ed2cc9eab79811ff86d3db87c79cab`

## Requirement map

| Review question | Assessment | Basis |
|---|---|---|
| Does the material identify the correct open problem? | Pass | It states that the conjecture asks whether every positive multiple of four admits a square plus-or-minus-one matrix with mutually orthogonal rows. |
| Does it distinguish necessary conditions from the unresolved conclusion? | Pass | It proves that every nontrivial order above two must be divisible by four, then says explicitly that necessity does not prove sufficiency. |
| Does it distinguish known constructions from a general solution? | Pass | It derives the Sylvester doubling construction for powers of two and explains why an infinite family does not cover every multiple of four. |
| Does it distinguish proved statements from measurements? | Pass | Algebraic identities, probability statements, floating-point observations, synthetic results, and model-development evidence are labeled separately. |
| Does it identify citations and source roles? | Pass | The manuscript cites primary research and the official JSP entry. `sources.json` records the claims supported by each reference. |
| Does it identify original contributions? | Pass | The submission draft lists the explanatory framing, exact counterexample, paired experiment, group-size study, interactive artifact, and claim-boundary design. |
| Is the exposition inspectable without specialized infrastructure? | Pass | `exposition.html` is standalone, includes native MathML and embedded display assets, and contains an interactive calculator. |
| Are numerical claims reproducible? | Pass within stated scope | Source code, retained records, an independent verifier, pinned dependencies, focused tests, and a complete validation command are provided. |
| Does it discuss counterexamples or failure modes? | Pass | It includes an exact rational counterexample, a grid-aligned failure case, Gaussian controls, and the incomplete pretrained campaign. |
| Does it avoid claiming a solution, universal quantization benefit, or model speedup? | Pass | These exclusions are explicit in the article, README, and submission draft. |
| Is authorship stated for the submission? | Pass in dossier | The dossier and citation metadata identify Wei Meng Soh. The frozen standalone article itself remains byte-identical to the reviewed artifact. |
| Is there a stable public material link? | Blocked | The repository is private at this review point. No public URL is claimed. |
| Is there a verifiable public publication date? | Blocked | The document preparation date is recorded, but the first public UTC date does not yet exist. |
| Has MathDB or the prize committee reviewed and selected it? | Not yet | No official candidate or award record is published for the exposition category. |

## Mathematical content checks

### Definition and normalization

The exposition defines an order `n` Hadamard matrix by entries in `{−1,+1}` and the identity `HH^T = nI`. It then defines `Q = H/sqrt(n)` and derives orthogonality. This prevents a common normalization error where the raw Hadamard matrix is treated as length-preserving.

### Necessary divisibility condition

The column-normalization and row-counting argument is valid for orders above two. After making the first row all plus ones, orthogonality forces every later row to have equal signs. Reordering by the second row and comparing a third row against the first two gives `n/4` as an integer.

### Exact change of basis

For compatible matrices, the article uses `X_r = XQ` and `W_r = Q^T W`, so `X_r W_r = XQQ^T W = XW`. It does not extend this identity carelessly through arbitrary nonlinear network components.

### Randomized signs

The expectation and tail discussion state the fixed-input assumption and the independence of random signs. The article warns that choosing the input after seeing the signs invalidates that interpretation.

### Counterexample

For `x = [7,1,1,0]`, the original max-absolute-value quantizer represents the vector exactly. The transformed peak falls to `4.5`, yet the stated relative squared reconstruction error becomes `11/3332`. This directly refutes the naive rule that reducing the largest coordinate must improve realized quantization.

## Experimental content checks

The reference experiment uses paired seeds and the same bit count, scale rule, rounding convention, and number of scale groups in both bases. The group-size follow-up changes one factor at a time and keeps the comparison matched within each group size.

The article reports favorable and unfavorable cases. It does not use the persistent-outlier result as a population estimate for language models. Bootstrap intervals are described as variation across the retained synthetic draws, not as a guarantee for real-model performance.

The incomplete Pythia campaign is documented rather than hidden. It reached real checkpoint acquisition and graph export, then stopped when the unmodified reference model failed its own cached-decoding tolerance. No quality or timing endpoint was evaluated.

## Review history and limits

Pull request 3 recorded separate standards and specification reviews of the exposition and group-size study. The standards axis checked evidence preservation, source identities, failure handling, and verifier independence. The specification axis checked arithmetic, setting coverage, scale counts, uncertainty calculations, and the Hadamard construction.

Later milestones retained additional source-bound reviews for operator qualification, campaign code, environment recovery, and the pretrained diagnostic. These reviews support traceability. They remain internal agent reviews.

The award process still requires review through its authorized channel and a committee decision selecting the first satisfactory exposition. This dossier cannot substitute for either action.

## Recommended committee reading order

1. Read `exposition.html` as the submitted material.
2. Inspect the exact counterexample and the section titled "What changes when groups become smaller."
3. Check `sources.json` for source-to-claim mapping.
4. Run `python3 scripts/validate.py` for retained-result and calculator checks.
5. Run `python3 scripts/validate.py --reproduce` for a fresh group-size sweep.
6. Use the publication manifest to verify that the reviewed public release has the same article and source blobs.

## Readiness conclusion

The fixed exposition is ready for public release and authorized content review. Two prerequisites remain outside the scientific package: publish an immutable public version with a defensible UTC timestamp, then submit that fixed version through the official route when available. No award status should be stated before the committee and public-review process record it.