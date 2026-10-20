# Prospective Specification review

**PASS** for the scoped cache maintenance and development reference diagnostic. No material specification defect remains.

Reviewed the plan and all three executable helpers against the frozen benchmark, the original failed campaign, and the stated diagnostic stopping rules. The exact reviewed SHA256 values are:

| File | SHA256 |
|---|---|
| `diagnostic-plan.md` | `4a5e58d3fa61828cf6a3352a3f9988fe79ce3016608ab640b7ca25996a5d8996` |
| `sources/reference-trace-worker.py` | `c973d35f99b7978266146d17e54a2216b801de5282c1fb5b5f158889c0c0f9c9` |
| `sources/run-reference-trace.py` | `32cd0055b60f2d24f165b867ec842f7ab1405e433574dc7816945c2903c428bd` |
| `sources/release-reference-cache.py` | `7396ee1f0bd3029210bed981a650e8ead6d005841be3d8004bae19c2099a9baf` |

The maintenance helper restricts its single advisory pass to `build/model-campaign-development-002`, preserves input bytes, and retains its journal. Advice establishes no reclaimed-byte quantity. A failed maintenance result or unchanged 6 GiB preflight stops the sequence.

The parent requires both prospective reviews, exact helper and benchmark identities, the original model-source review, the original campaign receipt, and successful maintenance evidence. It uses the existing campaign process lock and observed-worker guard. The 120-second deadline, 6 GiB worker RSS ceiling, and 64 MiB new-output allowance remain explicit. Final observations preserve errors, and the parent reserves space for its final receipt.

Before model loading, the worker verifies the pinned model files, original receipts, two exact development prefixes, and all six saved reference arrays. It performs exactly six calls through the unchanged reference wrapper. Hooks copy observations and return no replacement tensors. No precision, backend, model arithmetic, quantization, token sequence, or benchmark source change is introduced.

The worker separately checks full-prefix versus prefill caches, cached-prefix preservation, exact replay logit identities, and original cache identities. A changed replay remains a failed diagnostic. The first unequal boundary, including any equal-input/different-output tokenwise boundary, can localize divergence but cannot establish an internal kernel cause.

I also independently verified all 49 archived attempt-2 members, four standalone receipt copies, and the four preserved comparison slices. The slices match their original local source slices.

This review accepts a prospective diagnostic procedure. It does not pass the failed parity control, qualify the campaign, create an execution lock, or accept quality or timing results.

I did not execute either maintenance helper, run model calls or tests, change files, install packages, or use the network during this review.

