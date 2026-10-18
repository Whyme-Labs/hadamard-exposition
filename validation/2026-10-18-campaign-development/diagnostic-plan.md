# Reference cache divergence diagnostic, version 1

Date: 18 October 2026. Tracks [issue #5](https://github.com/Whyme-Labs/hadamard-exposition/issues/5). The retained campaign at commit `c45ff6b4f29ad6190e5783ff36a7a71bdd4e8e2a` stopped before ONNX development parity, feasibility, quality or timing.

## Observation and question

The unmodified CPU FP32 Transformers reference passes full-versus-prefill equality but fails full-versus-cached absolute logit error on both frozen development articles. Maximum errors are 0.016845703125 and 0.001708984375 against the unchanged 0.001 limit. Relative Frobenius errors pass. The retained final-row slices show many differing vocabulary entries; even the best uniform scalar shift cannot bring either maximum error below 0.001.

Read-only source inspection found the intended token at position 512, a 512-position past cache, matching layer/key/value order and aligned causal masks. Shape-dependent FP32 arithmetic is a hypothesis, not an established cause. The [PyTorch numerical-accuracy documentation](https://docs.pytorch.org/docs/2.14/notes/numerical_accuracy.html#batched-computations-or-slice-computations) explains why tensor and slice computations need not be bitwise identical. That general statement does not identify this run's failing operation or qualify its numerical error.

This diagnostic asks where the two paths first diverge, whether their earlier cache positions remain identical, and whether an instrumented replay reproduces the original saved outputs.

## Frozen diagnostic scope

Use only `build/model-campaign-development-002`, the same pinned checkpoint, converter environment and two selected development prefixes. Verify original campaign, acquisition, selection and reference receipts, the two development token identities and all used input hashes before model loading. Preserve those files.

Make exactly six forward calls through the existing `load_reference` and `reference_forward`: full 513, prefill 512, cached one, in that order for article 0 and then article 1. Keep CPU FP32 eager attention, evaluation mode, all original parameters, backend settings and one worker/thread. No alternate precision, backend, wrapper, quantization arm, sign choice or changed token sequence is part of this diagnostic.

Forward hooks observe last-token input/output vectors at the embedding, layer norms, attention, MLP and transformer block boundaries, including final normalization and the language-model head. Record actual positions and last-query attention masks where available. Hooks return no replacement tensor. They may copy observations after computation but cannot modify inputs or outputs.

Compare full-forward and prefill key/value prefixes, then compare the cached result's first 512 positions with the prefill cache for every layer and key/value tensor. Locate the first unequal observed last-token boundary between the full and cached cases. This identifies a boundary, not necessarily the internal kernel responsible.

Compare every replay logit array with its corresponding original read-only NPY array. Retain exact equality, stable array-content hashes and numerical error metrics. If any replay changes, report that explicitly and do not call the original numerical result exactly reproduced. Save only small observations and summary metrics, not another set of full logits.

## Resource maintenance and execution gates

Reading and hashing the retained model outputs warmed this project's file cache. A read-only host observation found 3,591,278,592 conservative available bytes, below the unchanged 6,442,450,944-byte launch gate.

Before the diagnostic, make one additional independently reviewed advisory pass over the single exact root `build/model-campaign-development-002`. The [scoped helper](sources/release-reference-cache.py) retains the reviewed descriptor anchoring, current-user/single-link regular-file checks, read-only hashing, nonbinding `POSIX_FADV_DONTNEED` advice, before/after metadata identity, process lock, 120-second deadline and 512 MiB address-space limit. It changes no input bytes or experiment setting. Retain its complete journal and outcome. Advice does not prove any number of bytes were reclaimed.

Then require a fresh unchanged host preflight. If maintenance or preflight fails, stop with the original observation. Do not lower the gate or repeat maintenance until it happens to pass.

The [diagnostic parent](sources/run-reference-trace.py) holds the existing campaign process lock. It verifies the original model source review and both independent diagnostic reviews before starting one worker. The worker has a 120-second outer deadline, 6 GiB sampled and OS high-water RSS ceiling, and 64 MiB new output allowance. Prepared environments and the already-retained campaign are read-only inputs outside that new diagnostic-output allowance. They are not claimed as newly measured footprint savings. No network, paid service or GPU execution is permitted.

The diagnostic uses a fresh output directory. Publish process identity before numerical imports; retain parent observations, stdout/stderr, worker output, source hashes and every failure. Check used input and helper identities again after completion. Archive original receipts and the small observation arrays before interpreting the result.

## Interpretation and stopping rule

A completed diagnostic establishes only its observed development trace and resource behavior. It does not repair the frozen campaign, pass a parity control, publish an execution lock or authorize quality model evaluation.

If the first divergence is localized, record the evidence and a specific next implementation or diagnostic proposal. If it remains unresolved, state that limit. Any change to model arithmetic, execution implementation or acceptance criteria needs its own prospective review and fresh evidence. The current campaign remains blocked at the original reference gate.

