# Model-benchmark qualification evidence

These records concern generated-input W4A32 design qualification. They contain no pretrained-model quality or model inference measurements. Dates in this directory and the receipts use UTC.

The accepted [qualification.json](qualification.json) records 38 focused tests and 20 ONNX controls passing in 6.194 seconds. The parent collected 119 valid identity-bound RSS samples. Worker OS high-water RSS was 187,994,112 bytes, about 179.3 MiB, under the unchanged 1 GiB ceiling; the outer deadline was 180 seconds. All ten bound source files were unchanged. `campaign_ready` remains false.

The largest full-shape relative Frobenius error was `8.251977963763346e-7`, against the `1e-5` bound. Its largest absolute error was `5.707463393012091e-6`, against `1e-3`. The two-block legal floating-point rotation differed from the original runtime by `1.4681475992503365e-7` in relative Frobenius norm. Both deliberately invalid placements failed invariance while matching their own independent references.

## Attempt history

| Record | Observation | Acceptance |
|---|---|---|
| [failed-precheck.json](failed-precheck.json) | Stopped before launching a worker because the original memory precheck counted all cgroup file cache as unavailable. | Rejected. No numerical controls ran. |
| [unqualified-rss.json](unqualified-rss.json) | All 34 focused tests and 20 ONNX numerical controls passed. Worker high-water RSS was 184,414,208 bytes, but parent sampling returned zero. | Rejected for resource qualification. The mounted proc filesystem used a different PID view from `Popen.pid`. |
| [qualification.json](qualification.json) | All 38 tests and 20 controls passed, with valid process-identity-bound RSS monitoring and unchanged source hashes. | Accepted for generated-input design qualification. Full-model readiness remains false. |

`unqualified-rss.json` preserves the original command's `design_qualified` value. That automated status was incorrect because its monitor had no valid worker RSS samples. The assessment here supersedes that status; the receipt itself has not been rewritten. Both corrections are recorded in the protocol and issue #2 before the subsequent run.

The exact changed qualifier, protocol and test source bytes associated with each earlier attempt are retained as `.txt` files. Their SHA256 values match the corresponding receipt's source map. In particular, [unqualified-rss-test_qualify.py.txt](unqualified-rss-test_qualify.py.txt) preserves the six-case memory test source before the PID correction. `assessment.json` maps each historical override to its source path and receipt hash; every other bound source matches the reviewed repository revision. This keeps all sources for the failed observations reconstructable after the implementation corrections.

The earlier numerical run's native ORT logs and profiles are retained in [unqualified-rss-runtime-evidence.tar.gz](unqualified-rss-runtime-evidence.tar.gz). Its stderr includes the named tests. Generated ONNX graphs are reproducible from the pinned fixture source and their hashes are in the receipt; they are not duplicated in this evidence directory. Archive member bytes can be checked against the receipt's control-artifact hashes.

The accepted run's [runtime-evidence.tar.gz](runtime-evidence.tar.gz) retains all 20 native logs and 20 profiles, plus the original worker result, identity and subprocess logs. All 40 runtime members in each archive were verified against their original receipt hashes. [assessment.json](assessment.json) records the accepted/rejected decision for each attempt, receipt hashes and archive hashes. [stderr.log](stderr.log) shows the accepted run's named tests. Generated ONNX graphs are recreated by the documented command; each original graph hash is retained in its receipt.

## Original exposition

[exposition-validation.json](exposition-validation.json) records a passing integration check of the existing exposition, retained synthetic results and bundled calculator. Its separate earlier full numerical reproduction remains in [2026-10-17-group-size.json](../2026-10-17-group-size.json).

## Reproduction

Use the commands in [benchmarks/README.md](../../benchmarks/README.md) with a new output path. The generated output directory retains each ONNX graph, native runtime log, CPU profile, subprocess log and numerical receipt. A new run has its own timestamps, process identities, timings and resource observations.

CPU provider and `MatMulNBits` profile evidence do not identify an internal MLAS kernel. No inferred hardware integer GEMM or model speedup is part of this qualification.
