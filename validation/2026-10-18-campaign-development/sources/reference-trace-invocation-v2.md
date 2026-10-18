# Development reference trace, version 2

Version 2 uses a fresh reconstructed input directory because the original local
campaign inputs were lost after their evidence was archived. Version 1 remains
unchanged and was not executed. The parent owns the new recovery plan,
prospective review, bounded launch and publication.

## Inputs and provenance

Use `build/reference-diagnostic-inputs-001`. Preserve original member paths for
the six receipt and development-token files, the two complete cached NPY files,
and the five model files. Add the preserved slice package at
`reference/cache-comparison-slices.npz` and its original derivation record at
`reference/slice-derivation.json`.

The ten copied evidence files are:

| Input-relative path | Provenance |
|---|---|
| `campaign.json` | Copied original campaign receipt |
| `review.json` | Copied original source review |
| `artifacts/acquisition.json` | Copied original acquisition receipt |
| `selection/selection.json` | Copied original role selection receipt |
| `selection/tokens.development.json` | Copied original two development prefixes |
| `reference/reference.json` | Copied original failed reference receipt |
| `reference/article0.cached.npy` | Copied complete original cached logits |
| `reference/article1.cached.npy` | Copied complete original cached logits |
| `reference/cache-comparison-slices.npz` | Copied originally retained full-last and cached arrays |
| `reference/slice-derivation.json` | Copied original slice derivation record |

The five files below `artifacts/model` are newly reacquired public inputs:
`config.json`, `model.safetensors`, `tokenizer.json`,
`tokenizer_config.json` and `special_tokens_map.json`. Their bytes must match
the identities in the original acquisition receipt. Reacquisition does not turn
them into a new original campaign observation.

The input directory must include `reconstruction.json`:

```json
{
  "schema_version": "hadamard-reference-diagnostic-inputs.v2",
  "status": "complete",
  "original_campaign_directory": "build/model-campaign-development-002",
  "original_campaign_sha256": "96136cf823ca00d82c28d080b0c7ff38726717cd2764cca20dacd914ff07b781",
  "full_prefill_logits_available": false,
  "model_calls": 0,
  "quality_test_accessed": false,
  "copied_original_evidence": {},
  "reacquired_model_files": {}
}
```

Replace the two empty maps with every required input-relative path, each mapped
to its integer `bytes` and hexadecimal `sha256`. The first map must contain
exactly the ten copied evidence files above. The second must contain exactly
the five model files. The parent may add archival and download provenance in
other fields. The worker binds this reconstruction receipt and rechecks it with
all consumed files after the diagnostic.

The historical campaign path is rejected. Original full and prefill NPY paths
must be absent from the reconstructed directory. Generated replacement arrays
cannot substitute for the lost original files.

## Comparison contract

Every replay logit array is compared with the original reference receipt's
shape, dtype, byte count and canonical array-content SHA256. Any mismatch
prevents a claim that the original failure was reproduced.

Full and prefill NPY files are unavailable. Direct `array_equal`, differing
element count, maximum absolute error and relative Frobenius error against those
complete original arrays remain null, even when all recorded identities match.
The receipt explicitly identifies the comparison as one against recorded
whole-array identity.

For each full forward, position 512 is also compared directly with the preserved
original final-position slice. For each cached forward, every value is compared
with the complete restored original cached NPY and the cached copy in the
preserved NPZ. The worker first checks that these retained arrays reproduce the
original cached control metrics. It rechecks the slice derivations against the
original source file identities.

Reproduction requires all six recorded logit identities, every available direct
logit comparison, every original cache identity and the original failed cached
logit gate for both articles. The receipt's `reproduction_basis` states which
claims use recorded hashes and which use direct comparisons. Neither hashes nor
newly observed error metrics are presented as an elementwise reread of a lost
original array.

## Bounded invocation

Do not launch until the parent plan, version 2 helper bytes and both review axes
are bound in a prospective review record. The parent should hold the existing
campaign process lock and invoke the worker through the unchanged
`benchmarks.campaign_guard.run_bounded_task` API with a 120-second deadline,
a 6 GiB worker RSS ceiling and a 64 MiB new-output allowance. Require the unchanged
host and dependency gates in the parent. Keep the reconstructed inputs outside
the fresh diagnostic output root.

Use the newly restored converter interpreter. The command is:

```text
build/diagnostic-environments-001/converter/bin/python
validation/2026-10-18-campaign-development/sources/reference-trace-worker-v2.py
--diagnostic-inputs build/reference-diagnostic-inputs-001
--output <new diagnostic task directory>
```

The parent creates the task directory with only its stdout and stderr logs.
The worker publishes process identity before numerical imports, validates its
input and source identities, and makes exactly six unchanged reference-wrapper
calls: full 513, prefill 512 and cached one for article 0, then the same order for
article 1. It preserves all version 1 hooks, prefix-cache checks and resource
behavior. Hooks return `None` and only copy last-token observations.
The worker hashes this invocation note and its own version 2 source before and
after execution, in addition to the original benchmark sources and consumed input
files. The parent owns the source bindings for all other recovery and execution
helpers.

This worker does not download, reconstruct prefixes, regenerate original logits,
change arithmetic, relax thresholds, run a quantized arm, or read quality or
timing token files. Recovered model inputs must already exist. Its elapsed times
include instrumentation and provide no inference timing evidence. Diagnostic
success never sets campaign readiness.

The helper was authored without execution. Static syntax inspection is not an
observed diagnostic result.

