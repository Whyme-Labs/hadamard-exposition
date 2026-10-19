# Exact first-layer affine audit — version 1

Status: prospective protocol, 19 October 2026. Issue [#5](https://github.com/Whyme-Labs/hadamard-exposition/issues/5) owns this follow-up to [PR #9](https://github.com/Whyme-Labs/hadamard-exposition/pull/9). Publish the protocol, executable sources, synthetic validation and both independent review axes before acquiring its checkpoint or evaluating the retained numerical cases. Keep this version stable after publication; preserve every attempted phase and any rejected candidate.

## Question and completion criterion

The six-forward version-2 trace reproduced the original reference failure. For both fixed development articles, the first attention QKV output differed between the full and cached paths despite identical retained last-token inputs. The first parallel MLP affine output also differed. The saved vectors establish the outputs, but do not identify an internal BLAS kernel, reduction order or the entire cause of the later logit gap.

This milestone answers two narrower questions:

1. How far are each of the eight retained native FP32 output vectors from the exact real affine result for the saved FP32 input and pinned FP32 parameters?
2. Does one fixed NumPy FP64 matrix product, followed by a separate FP64 bias addition and one FP32 cast, give the directly rounded exact FP32 result at every tested final position under both prescribed row counts?

Completion requires a valid bounded run, retained exact sums and numerical evidence, independent result review, and a published corrective decision. A candidate rejection is a completed scientific milestone. An acquisition, provenance or resource failure is a retained blocked attempt, not an arithmetic result.

There are no fresh Torch or native FP32 affine calls in this milestone. The dependency environment from the preceding milestone is no longer available. Its existing cumulative dependency transfer ledger remains 1,072,634,485 bytes against 1,073,741,824, leaving 1,107,339. No dependency is installed or downloaded here. NumPy 2.3.5 and threadpoolctl 3.6.0 are already available in the Python 3.12.14 base runtime.

## Frozen evidence and parameters

Base repository commit: `e26702bdd16242abbfe7dd34cdcf7529327f527a`; tree: `d0490c2647f8c067dfc6b5fde1d69730fa7ab932`.

The thirty original benchmark source identities remain unchanged. Their canonical JSON SHA256 is `1dd75e9af0736795e4d83c26f866d15d9f7a3fe55003e399ddbd36951ab2d69e`, as retained in `validation/2026-10-18-campaign-development/diagnostic-review-v2.json`.

Use `validation/2026-10-18-campaign-development/reference-trace-v2/`:

| File | Bytes | SHA256 |
| --- | ---: | --- |
| `raw-evidence.tar.gz` | 2,216,803 | `67d20a6e24f477fcf5e789aa8af6259f07f06ffd83bc407084e24b747e0f683a` |
| `worker-result.json` | 866,754 | `0a3f346cc8fc3904167cd9bf4d8331e31591117ec30d2e11dfcc57866887965c` |

Verify the inventory identity, every one of its fifteen regular archive members, and the standalone worker copy before reading the four full/cached NPZs. Read members without filesystem extraction and load arrays with `allow_pickle=False`. Check the article identities, labels, event positions, original and retained shapes, FP32 dtypes, finite values and the historical whole-array identities. The full and cached input vectors must be byte-identical for each case. The loader must fail closed on any mismatch.

| Case order | Article start row | Module | Weight shape | Input/output events |
| --- | ---: | --- | --- | --- |
| `article0_qkv` | 1 | `gpt_neox.layers.0.attention.query_key_value` | 1536 × 512 | 15 / 16 |
| `article0_mlp` | 1 | `gpt_neox.layers.0.mlp.dense_h_to_4h` | 2048 × 512 | 23 / 24 |
| `article1_qkv` | 47 | first attention QKV, as above | 1536 × 512 | 15 / 16 |
| `article1_mlp` | 47 | first parallel MLP affine, as above | 2048 × 512 | 23 / 24 |

The source development token SHA256 values are respectively `0a9f94df5f5de2b581d82281907b01af4aeac86f95055e3684aa42ee643185f4` and `4bb3be20531fe494946704c1ebdf36fbeffbc73be4861e91bfd76b87c66aa43d`. These identify the historical selection; no tokenization or dataset acquisition occurs now.

Reacquire only `EleutherAI/pythia-70m` revision `301b2c9bdf4d6da917d8f02d3c48aac481a60d06`, file `model.safetensors`, from its immutable Hugging Face resolve URL. Its published size is **166,029,852 bytes** and SHA256 is `ebfa4e2f18696ebd83716a0d39fe2c025f2ff8483f72a83ca59c475692fc9d15`.

Use the existing unchanged pinned-download helper for this one allowlisted file, retaining response-body bytes, sanitized redirect provenance, hashes and any partial. No tokenizer, configuration, dataset or runtime package download is needed. Two known earlier complete eight-file model/data acquisitions recorded 175,891,986 bytes each. Adding this checkpoint would bring that known complete-receipt subtotal to 517,813,824 bytes; this is not a complete historical traffic ledger. The previously disclosed unreferenced 152,043,520-byte partial had unresolved origin and is not used here.

Parse Safetensors as an 8-byte unsigned little-endian header length, UTF-8 JSON header and packed little-endian C-order data. The local header ceiling is 1 MiB. Reject duplicate JSON keys, nonstandard constants, invalid sizes/shapes/offsets, overlaps, holes or an unconsumed payload. Check all header tensor extents. Select exactly the two weights and two biases above; require their stored types to be F32, F16 or BF16. Widen F16 exactly to FP32; widen BF16 by placing its sixteen bits in the high half of an FP32 word. Do not reinterpret BF16 as F16. F32 is preserved. Reject nonfinite selected values. Record header, source tensor byte ranges and raw/derived tensor hashes. This matches the historical reference's FP32 load for those supported source dtypes without instantiating a model. It does not reverify an absent historical in-memory parameter buffer.

Retain the four derived FP32 arrays in the new evidence archive, totaling 7,354,368 data bytes, with their checkpoint derivation receipt. The complete checkpoint can remain outside Git with an explicit observed omission identity.

## Exact reference

For each finite binary32 bit pattern, decode an integer \(I\) such that the value is \(I2^{-149}\). A subnormal uses its signed fraction bits. A normal with stored exponent \(e\) and fraction \(f\) uses the signed integer \((2^{23}+f)2^{e-1}\). Both input zero signs map to mathematical zero; retain the original bits separately.

For output feature \(o\), use the stored output-by-input orientation:

\[
S_o=\sum_{k=0}^{511} I(x_k)I(W_{o,k}) + 2^{149}I(b_o),
\qquad y_o=S_o2^{-298}.
\]

Python integer arithmetic supplies all **3,670,016 exact products** and **7,168 exact output sums** across the four cases. The weight-row iterator can share each decoded row across both article inputs. The final result is unchanged by this iteration order because every operation is exact.

Round each integer sum directly to binary32, nearest with ties to even. Implement normal/subnormal boundaries, carries, signed underflow and overflow using integer shifts and remainder comparisons. Exact mathematical zero maps to +0. Do not use an FP64 intermediate to generate the FP32 oracle: a legal FP32 affine input can produce \(1+2^{-24}+2^{-54}\), which rounds directly to `0x3f800001` but through binary64 to `0x3f800000`.

Before publication, synthetic tests must independently check decoding and affine arithmetic with exact rational values, non-square orientation and bias, rounding boundaries, zero conventions, nonfinite rejection, streaming, and the double-rounding counterexample. Parser tests must reject malformed or changed evidence. Outcome classification tests must distinguish a valid candidate miss from an invalid or incomplete run. These controls use no retained development arrays or checkpoint.

## Fixed FP64 candidate and call budget

Process cases in the table order. For each case, widen its saved input, weight and bias from FP32 to FP64 exactly. Make a C-contiguous 2-D input with either one row or 513 copies of that same saved row, in that order. The prescribed candidate is:

```python
x64 = np.repeat(x32.astype(np.float64)[None, :], rows, axis=0)
w64 = w32.astype(np.float64)
b64 = b32.astype(np.float64)
product64 = x64 @ w64.T
output64 = product64 + b64
output32 = output64.astype(np.float32)
```

There are exactly **8 attempted/completed FP64 matrix evaluations**, **8 FP64 bias additions** and **8 FP32 casts** in a complete run. There is no warmup, repeated trial, backend sweep, adaptive row count or recomputation after seeing a miss. Record each call's pre-operation intent, completion state, shapes, strides, dtypes, contiguity and full output hashes. Retain the final row before and after the cast. Validate every computed output is finite. Capture actual NumPy/BLAS runtime metadata and require each reported BLAS pool to have one thread before and after the experiment.

These counters cover the explicit checkpoint/trace candidate evaluations. NumPy 2.3.5's normal import also executes a synthetic length-two FP32 dot and a synthetic 20 × 20 FP64 matrix multiplication, once per fresh importing process. Record those source-derived startup calls separately in each worker receipt, with the installed NumPy import-source identity; they are not individually instrumented. They access no checkpoint or retained trace data. Synthetic validation processes also import NumPy. Do not describe this milestone as having literally no floating dot/matrix operations outside the eight candidates. The stated zero fresh native-affine replay count refers to the audited 512-input FP32 operators.

The 513 repeated rows are a controlled row-count surrogate. They do **not** reconstruct the original preceding 512 activation rows, allocation, strides or storage offset, which were not retained. This is a NumPy FP64 candidate experiment and a retrospective audit of saved native outputs, not a fresh Torch shape reproduction.

The historical native vectors were produced on AMD EPYC 9V74. The current candidate is evaluated on the separately qualified Intel Xeon Platinum 8573C host. Thus precision, backend and hardware differ together; this experiment cannot attribute improvement specifically to precision or reproduce the historical shape mechanism. Both sets of outputs can still be compared with the same exact mathematical affine result. Candidate qualification applies to the observed Intel/NumPy/BLAS environment and fixed final positions.

## Prespecified measurements and decision

For every historical output value, calculate exact absolute error as the integer
\(\lvert 2^{149}I(y_{native})-S\rvert\), at scale \(2^{-298}\). Report counts differing from the correctly rounded FP32 target, maximum exact absolute error and its index, maximum representable-step distance and its index, and which of full/cached is closer to the exact value for each component (including ties). Rank using integers. Decimal presentation is approximate; preserve the exact signed sums and error numerators.

Representable-step distance orders finite FP32 values and treats +0 and -0 as the same numerical point. It is not absolute error divided by a single local ULP. Keep bit equality separately. Ordinary FP32 affine evaluation has intermediate rounding, so differing from the single-final-round target does not by itself establish a defective native operation.

For the candidate, the primary observations are the final row from each of its two row counts. Compare all **14,336 retained candidate FP32 values** directly with the 7,168 exact FP32 targets, reused once per shape. Record the FP64 final-row errors against the exact sums for context. There is no sampled subset and no tolerance.

The candidate qualifies **for the tested final positions** only if every primary FP32 bit pattern matches the exact target in both shapes. A single mismatch rejects that local qualification, while remaining a valid experimental outcome. The other 512 repeated rows have whole-output hashes and finite checks, but are not additional independent inputs or the primary qualification population.

Execution validity independently requires complete input/source/review bindings, all four cases and eight completed evaluations, finite arrays, unchanged sources/inputs, one-thread backend observations and successful resource monitoring. A partially completed run cannot qualify. Do not select a better shape or alter arithmetic after an outcome.

If the candidate qualifies locally, the corrective decision is to nominate this arithmetic for a separately versioned full-model reference validation, with its own resource/environment solution. No general correct-rounding guarantee follows. If it misses, publish the miss and reject this candidate without adding new variants to this version.

The original reference's **0.001 absolute logit gate**, relative gate and all matched benchmark criteria remain unchanged. The original campaign stays blocked. This audit establishes no ONNX parity, full-model repair, quantized-model quality, timing, cost saving, prize eligibility or Hadamard-conjecture result. Elapsed times below are execution-budget receipts, not benchmarks.

## Execution, publication and retention

Use a distinct operator-audit host preflight, not the campaign preflight that also requires the unavailable ONNX stack. The preliminary metadata-only host check rejected this session against the old AMD identity; preserve that blocked observation. Before publication, separately qualify **INTEL(R) XEON(R) PLATINUM 8573C**, x86_64, in `experiments/operator-audit/host-v1.json` and bind that record and its source observation in the reviewed source map. This requalification applies only to this local arithmetic audit. The original campaign's AMD identity and all thirty source files remain unchanged.

Reuse the unchanged conservative available-memory function and require Python 3.12.14, at least one core of quota, 6 GiB conservative available memory and 4 GiB free disk. Require the stated existing NumPy and threadpoolctl versions. Every phase reobserves the specifically qualified Intel CPU and these resource/runtime conditions. Record missing campaign packages without qualifying them. The preliminary host check imported no NumPy and accessed no checkpoint/trace arrays; it did not claim the single execution slot.

| Phase | Wall ceiling | Worker RSS ceiling | Directory/output ceiling | Downloads |
| --- | ---: | ---: | ---: | --- |
| Single checkpoint preparation | 600 seconds | 1 GiB | 4 GiB | one body, at most 200 MiB |
| Exact audit plus fixed candidate | 120 seconds | 1 GiB | 64 MiB | zero |

Run one isolated CPU worker at a time, one BLAS/OpenMP thread, no GPU and no paid service. Publish process identity before importing numerical packages. The unchanged resource guard observes identity-bound RSS every 50 ms, applies wall/output stops and verifies the worker's OS peak. These are observation/termination guards, not instantaneous kernel allocation limits. The arithmetic worker rejects socket audit events and does not launch another numerical process.

The executable source/protocol map and thirty-file benchmark map must match both independent prospective reviews. Record the published preregistration commit/tree and review receipt in a write-once publication receipt. Bind that receipt in preparation and numerical run starts. Each phase uses a fresh directory; never overwrite a receipt, retry an acquisition or execute additional candidates under this version. A launch that fails before numerical work must be retained and requires a documented prospective correction before any new attempt.

Retain source recovery receipts separately from dependency and checkpoint acquisition. The initial recovered archive request returned HTTP 404 with zero observed body bytes; the subsequent fresh connector-issued private download capabilities recovered three Git source archives totaling 9,860,354 bytes, all Git/SHA256 identities verified. No model or operator calls occurred during source recovery. Do not publish the transient signed URLs.

Retain the preparation and run receipts, all worker logs, selected parameter package, input/native/exact/candidate vectors, signed exact sums, output identities, independent result reviews and a deterministic archive inventory. Publish dated result comments in issue #5 and a scoped PR stacked on PR #9. Run `python scripts/validate.py` and all new synthetic controls before proposal. The absent full benchmark dependency closure is not reinstalled; earlier benchmark tests remain historical evidence and are not reported as rerun.

Primary-source reasoning and limitations are recorded in [operator arithmetic sources](../research/operator-arithmetic-sources.md). The final result report must cite the retained evidence and keep native observations, exact arithmetic and candidate qualification distinct.
