# Proposed development reference trace

Do not launch until the parent plan, helper bytes and both review axes are bound
in a prospective review record.

The parent should hold the existing campaign process lock and invoke the worker
through the unchanged `benchmarks.campaign_guard.run_bounded_task` API. Use a
120-second parent deadline, a 6 GiB worker RSS ceiling, and a separate fresh
diagnostic root with a 64 MiB output ceiling. Set `campaign_root` to that fresh
diagnostic root, rather than the original campaign. The default bounded-task
environment supplies one CPU thread, offline Hugging Face loading and no CUDA.
Use the recovered converter interpreter.

The worker command is:

```text
build/recovered-envs-002/converter/bin/python
validation/2026-10-18-campaign-development/sources/reference-trace-worker.py
--original-campaign build/model-campaign-development-002
--output <new diagnostic task directory>
```

The task directory is created by `run_bounded_task` and initially contains only
its stdout and stderr logs. The worker publishes `worker-identity.json` before
numerical imports. It binds the original six saved NPY files, receipts, local
model files, thirty benchmark sources and exact two development prefixes before
any model call. It performs six original-wrapper forwards in the original order.
No precision, backend, threshold, attention implementation or model arithmetic
is changed. Hooks return `None` and retain only copied last-token tensors and the
last query row of each attention mask.

Each forward writes a small NPZ of hook observations. The final worker receipt
contains exact comparisons with all original logit data, original cache data
identities, layerwise cache-prefix comparisons, and ordered full-last versus
cached hook comparisons. The first differing event localizes the first observed
numerical discrepancy. It does not by itself prove an underlying kernel cause.
Prefill last-token vectors describe position 511 and are not compared with full
or cached position 512. Prefix-cache comparisons use a saved prefill snapshot,
so an in-place mutation of the supplied cache cannot hide itself.

Successful collection requires exact reproduction of all six original logit
arrays and cache identities, followed by the original failed cached logit gate
for both articles. Any different replay is retained as a failed diagnostic with
`original_reference_failure_reproduced: false`. A successful diagnostic never
sets campaign readiness and never supplies quality or inference timing evidence.

This helper has been authored without execution. The parent owns the prospective
review, bounded launch, evidence archive and publication.
