# Source basis for the exact affine audit

Research date: 19 October 2026. This note supports the prospective [operator arithmetic protocol](../experiments/operator-arithmetic-v1.md). The interpretation below separates documented behavior, retained observations and the new experiment's hypotheses. It contains no result from the new arithmetic population.

## What the saved native trace can establish

The retained [version-2 trace report](../../validation/2026-10-18-campaign-development/README.md) identifies a first numerical divergence in the first attention QKV output for both selected development articles. Its full and cached final-position inputs to that affine are byte-identical; its original call shapes are `[1,513,512]` and `[1,1,512]`. The saved first parallel MLP affine also has identical paired inputs and differing outputs. The trace retains the final rows, not the preceding full activation rows or original tensor strides and offsets.

The pinned [PyTorch 2.5.1 numerical-accuracy note](https://github.com/pytorch/pytorch/blob/v2.5.1/docs/source/notes/numerical_accuracy.rst) explicitly allows different floating results when a computation is batched or sliced. Floating addition is not associative; native operations do not promise bit-identical outcomes across otherwise mathematically equivalent evaluation structures. That is a possible explanation of the observations, not a source-level identification of the kernel that produced them.

The pinned native sources narrow the possibilities:

| Primary source | Relevant behavior | Limit of the inference |
| --- | --- | --- |
| [PyTorch 2.5.1 Linear.cpp](https://github.com/pytorch/pytorch/blob/v2.5.1/aten/src/ATen/native/Linear.cpp#L55-L122) | A biased contiguous rank-three input can be flattened and evaluated through `addmm`. | Historical full activation layout was not retained, so this is conditional dispatch reasoning. |
| [LinearAlgebra.cpp](https://github.com/pytorch/pytorch/blob/v2.5.1/aten/src/ATen/native/LinearAlgebra.cpp#L1393-L1546) | The CPU affine path can include the bias through the matrix product's beta contribution. | A separately added bias is a different arithmetic candidate. |
| [CPUBlas.cpp](https://github.com/pytorch/pytorch/blob/v2.5.1/aten/src/ATen/native/CPUBlas.cpp#L170-L215) | The float wrapper can call the external single-precision BLAS GEMM interface. | The interface does not identify an internal MKL implementation, tiling or accumulation order. |
| [MKLDNN Matmul.cpp](https://github.com/pytorch/pytorch/blob/v2.5.1/aten/src/ATen/native/mkldnn/Matmul.cpp#L99-L130) | This optional BF32 path requires the medium float32 precision setting. | The historical highest setting excludes that particular path under its recorded conditions; it does not prove every other internal arithmetic detail. |

The prior source audit records these Git blob identities respectively: `e0af0a6b7542bbd7efadd3bb5c3ab80906a7f82c`, `2c4e000fce4421cb4aa7004eeea869ec683b1992`, `0a2789f4caff8b6f96ee85d289223afa1dcb43cf`, `e1fe3b92db83baf0c912e407f9c388d8a1fd841a`. The numerical-accuracy note is blob `2e081a08442d9a7a09b049235a9c4c978149f591`.

## Why these two affines are interpretable locally

The [Transformers 4.46.3 GPTNeoX implementation](https://github.com/huggingface/transformers/blob/v4.46.3/src/transformers/models/gpt_neox/modeling_gpt_neox.py) applies the QKV projection before rotary positions, cache concatenation and attention masking. Its parallel residual block feeds the MLP from a separate layer normalization of the original block input, rather than from the attention result. Consequently, paired equality of the saved MLP input is an independently useful local affine control; one should not assume the QKV discrepancy is already inside that MLP input. The source blob is `359996983eed74fc672606283e8d34ae1b2740c1`.

The repository's frozen model manifest fixes hidden width 512, MLP width 2048, eight attention heads and six layers, with output-by-input parameter orientation and an FP32 load. The immutable checkpoint identity binds the new extraction. Since no historical parameter-buffer hash was retained, the audit must describe this as reconstruction from the same pinned checkpoint and load dtype, rather than direct comparison with the absent original in-memory buffer.

This reasoning motivates the two local sites. It does not establish that repairing them alone will repair the final logits: later affines, reductions, nonlinearities and cache paths remain outside this milestone.

The preliminary host observation for this session records an Intel Xeon Platinum 8573C, while the historical native reference used AMD EPYC 9V74. The new operator-only host qualification preserves that difference and leaves the campaign's AMD acceptance unchanged. An exact integer affine value is a valid common comparison target for the retained native vectors and the Intel NumPy candidate. A favorable candidate result would not isolate precision as a causal factor, because backend and hardware also differ.

## Safe checkpoint interpretation

The official Safetensors repository redirects to `safetensors/safetensors`. This research pins the [format specification](https://github.com/safetensors/safetensors/blob/e246a2560645b7525f5775669ed816eb57c5bcc8/README.md#format), [Rust reader and validator](https://github.com/safetensors/safetensors/blob/e246a2560645b7525f5775669ed816eb57c5bcc8/safetensors/src/tensor.rs) and [NumPy adapter](https://github.com/safetensors/safetensors/blob/e246a2560645b7525f5775669ed816eb57c5bcc8/bindings/python/py_src/safetensors/numpy.py) to commit `e246a2560645b7525f5775669ed816eb57c5bcc8`.

The file begins with an unsigned eight-byte little-endian header length. The UTF-8 JSON header starts with `{`; tensor offsets are half-open and relative to the data buffer after the header. Tensor data is little-endian and packed in C order. Duplicate JSON keys are disallowed, metadata values are strings, and tensor ranges cover the payload without holes. The format itself permits nonfinite tensor values, so this audit adds finite-value checks for its selected tensors.

The Rust reader's upstream header maximum is 100,000,000 bytes. Our parser's documented 1 MiB ceiling is deliberately narrower. It accepts the listed byte-aligned BOOL, unsigned/signed integer and floating storage dtypes for whole-header size validation, and fails closed on unsupported formats. It validates empty tensor positions as well as occupied ranges. Only selected F16, BF16 and F32 tensors are decoded.

[Hugging Face's metadata-parsing example](https://huggingface.co/docs/safetensors/metadata_parsing) confirms the header layout but is not a complete validating loader. The official NumPy adapter distinguishes F16/F32 and does not provide a BF16 mapping. The pinned [PyTorch BFloat16 conversion](https://github.com/pytorch/pytorch/blob/v2.5.1/c10/util/BFloat16.h#L32-L48) places the sixteen BF16 bits in the upper half of a float32 word. This supports our exact widening rule; BF16 must not be read as NumPy float16.

The source blobs are `ccc910722eae29543526dc231186a699f71b3182` (format), `089d0933edba9f0147919df560c0a79463297163` (Rust), `75178ed773f455b87d2f9099806cb21087c5a9c7` (NumPy adapter) and `17326d81d7279c5adae7a15f915e44788448201e` (PyTorch BFloat16).

## Exact arithmetic and the candidate have different roles

The exact construction follows directly from binary32's finite representation: each input is an integer multiple of 2^-149, so each affine product is an integer multiple of 2^-298. Python integers retain the complete sum. Direct integer rounding supplies the exact nearest/ties-even FP32 target. Synthetic rational controls check that implementation independently.

Binary64 has more precision, but using it as an intermediate can still double-round. The protocol's legal FP32 affine counterexample produces an exact value just above an FP32 midpoint which rounds to the midpoint in binary64. Thus the FP64 candidate is measured against the integer oracle, rather than defining the oracle. Python's [integer documentation](https://docs.python.org/3.12/library/stdtypes.html#numeric-types-int-float-complex) distinguishes arbitrary-precision integers from floats; fixed-width NumPy integers are not used for exact sums.

[NumPy 2.3 matmul](https://numpy.org/doc/2.3/reference/generated/numpy.matmul.html) specifies ordinary two-dimensional matrix multiplication and uses optimized BLAS when possible. It promises neither a fixed reduction order nor a universally correctly rounded dot product. The candidate therefore names its dtypes, row counts and separate bias addition explicitly, retains its outputs, and is qualified only on the prespecified final positions.

[NumPy astype](https://numpy.org/doc/2.3/reference/generated/numpy.ndarray.astype.html) distinguishes safe widening from permitted lossy narrowing; `same_kind` does not mean value preservation. [NumPy frombuffer](https://numpy.org/doc/2.3/reference/generated/numpy.frombuffer.html) requires explicit byte order for external binary storage and views the original buffer. The loader creates the intended contiguous copies. [NumPy type documentation](https://numpy.org/doc/2.3/user/basics.types.html) also describes platform C-type relationships, so the worker verifies the actual binary32/binary64 finfo fields and byte order before applying raw-bit formulas.

## Thread and resource observations

[NumPy's global configuration documentation](https://numpy.org/doc/2.3/reference/global_state.html) distinguishes ordinary NumPy execution from potentially multithreaded BLAS. Backend-specific environment settings alone are not proof of the effective thread count. This audit sets the four recorded thread variables before worker startup, requires an observable BLAS pool, and checks threadpoolctl's effective pool counts before and after the calculation. It retains [build configuration](https://numpy.org/doc/2.3/reference/generated/numpy.show_config.html) and [runtime configuration](https://numpy.org/doc/2.3/reference/generated/numpy.show_runtime.html) alongside the parent resource samples.

An observed one-thread pool does not identify internal summation order. RSS samples and OS peaks describe the guarded run, while wall times cover accounting and evaluation overhead. These receipts support bounded execution, not a comparison of inference speed.

The installed [NumPy 2.3.5 import source](https://github.com/numpy/numpy/blob/v2.3.5/numpy/__init__.py) runs two synthetic numerical checks: `_sanity_check` evaluates a length-two FP32 dot product; `blas_fpe_check` evaluates a 20 × 20 FP64 matrix product. These normal import operations must be disclosed separately from our explicit eight candidate evaluations. Their source-derived counts are not individually instrumented. They do not use the selected checkpoint or development traces. In contrast, the [`_blas_supports_fpe` flag reader](https://github.com/numpy/numpy/blob/v2.3.5/numpy/_core/src/common/blas_utils.c) consulted by `show_runtime` returns the stored flag (or literal true on this build); that metadata read adds no matrix probe. The worker records the installed NumPy import-source hash as well as its version.
