# Prospective Specification review

Status: **passed**. Date: 19 October 2026. Reviewer: `/root/operator_methodology`, independently of the Standards reviewer.

- Base commit: `e26702bdd16242abbfe7dd34cdcf7529327f527a`
- Reviewed staged tree: `0d2f96c5de548d142dc297296af2eb26270a1ca8`
- Canonical source-map SHA256: `b043c055cae51f1faf4927aabef9c6a634ea31bfe04aee4c57ebf5385fbc0172`

I verified all forty bound source files against the staged bytes and the canonical map, including all thirty benchmark files against the base commit. The reviewed change adds the separate experiment without changing the frozen campaign.

The protocol's “Exact reference” clause and `affine_exact.py` agree: binary32 operands are decoded into integers, all 3,670,016 products and 7,168 sums retain exact arithmetic, and final binary32 rounding handles ties, boundaries, carries and signed underflow without a binary64 intermediate. The independent rational and double-rounding synthetic controls address the central oracle risk.

`audit_io.py` binds the complete historical archive and selected full/cached arrays, checks article/event identities and equal input bytes, and extracts the four checkpoint tensors with explicit output-by-input orientation and exact FP32 widening. The absent historical parameter buffers and preceding activation rows are not represented as recovered originals.

`audit_worker.py` implements the fixed four-case order and eight explicit candidate evaluations. It journals intent before each product, retains exact sums and candidate arrays, computes binary64 errors against exact rational values, and makes no data-dependent variant choice. `classify_candidate` rejects any primary bit mismatch while preserving valid execution; incomplete populations cannot qualify. NumPy's synthetic import checks are disclosed separately from these counters.

`run_audit.py` and `acquire_checkpoint.py` preserve the dependency ledger, require both source-bound reviews and publication evidence, use fresh phase claims, and separate the single checkpoint acquisition from the offline arithmetic worker. The specified preflight and resource observations remain prerequisites. Candidate qualification is local and leaves the original 0.001 logit gate failed.

I inspected the passing retained receipts for 35 new synthetic tests, import isolation, and documented validation including 25 tests. This review loaded no checkpoint or retained numerical arrays and executed no candidate probe. The verdict qualifies this prospective source snapshot; execution and results require separate evidence and review.
