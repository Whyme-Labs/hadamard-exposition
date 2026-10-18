# Pinned GPTNeoX export probe: accepted run and complete attempt history

Owner: [issue #5](https://github.com/Whyme-Labs/hadamard-exposition/issues/5). The frozen model experiment is specified in [model-benchmark-v1.md](../../../docs/experiments/model-benchmark-v1.md). This archive records a generated-model qualification of its exporter, with no pretrained model or dataset acquisition.

**Attempt 4 is accepted.** All six ONNX variants passed their generated-model comparisons in a monitored 4.708163071-second run. The worker's OS peak RSS was 357,396,480 bytes (340.84 MiB), within its 1 GiB ceiling. The parent recorded 91 valid RSS samples and no monitoring error. The authoritative [assessment](assessment.json) retains the original status of every earlier attempt.

This is an untrained, small GPTNeoX model: six layers, hidden width 32, MLP width 64, four attention heads of width eight, vocabulary 97, and context 64. It exercises the exact pinned Transformers implementation and the same private tracing primitive used by the production exporter. The public production entry point correctly rejects these smaller dimensions. **The result establishes no full pretrained Pythia parity, full-model campaign feasibility, language-model quality improvement, speedup, or commercial saving.**

## What passed

The accepted probe receipt, member `attempt-4/probe.json` inside [raw-evidence.tar.gz](raw-evidence.tar.gz), records the following comparisons. An output comparison covers one complete logits or cache array, using relative Frobenius and maximum absolute error checks.

| Check | Accepted observation |
|---|---:|
| ONNX variants | 6 |
| Dynamic batch/sequence/cache cases | 24: four cases per variant |
| Additional prefill and cached-decoding comparisons | 36: one prefill and five one-token steps per variant |
| Retained output comparisons | 780: 60 comparisons × 13 outputs |
| Outputs per call | Logits and twelve layer-ordered key/value tensors |
| Largest relative Frobenius error among retained comparisons | 5.170438578475888 × 10⁻⁷ |
| Largest absolute error among retained comparisons | 1.9371509552001953 × 10⁻⁷ |
| Numerical limits | Relative error ≤ 10⁻⁵ and absolute error ≤ 10⁻³ |
| Existing cache prefixes | Preserved exactly |
| Full request versus prefill plus cached request | Passed for all six variants |
| Altering future tokens preserves earlier logits | Passed for all six variants |
| Named stored weights and orientation | Exact equality with Torch parameters verified at all six sites |
| Production configuration guard | Rejected the small generated model before export |

The four shared cases have `(batch, new tokens, past tokens)` equal to `(1, 1, 0)`, `(1, 7, 0)`, `(2, 3, 0)`, and `(2, 2, 5)`. Nonempty cache tensors contain distinct generated values; the checks detect cache ordering mistakes as well as shape mistakes. Each variant also processes a ten-token request as a five-token prefill followed by five cached calls. Full-request/cache agreement and causal-prefix checks are retained as passed flags in addition to the 780 detailed comparisons.

The six variants are `fp32_original`, `fp32_rotated`, `w4a32_g32_original`, `w4a32_g32_rotated`, `w4a32_g16_original`, and `w4a32_g16_rotated`. Their graph audits verify that only the six selected MLP output projections and their online transforms change. Weight packing is checked against independent contract quantization/decoding. The small Torch references use dense float64 Sylvester transforms and scalar quantization; exported rotated graphs use the prescribed FP32 Add/Sub butterflies and restore batch/sequence shape. Original bias Add operations remain unchanged.

The stack was Torch 2.5.1+cpu, Transformers 4.46.3, NumPy 2.3.5, ONNX 1.19.1, and ONNX Runtime 1.23.2. Runtime sessions use only `CPUExecutionProvider`, one intra-op thread, one inter-op thread, sequential execution, and disabled graph optimizations. The receipt establishes execution through those sessions; it does not identify an internal MLAS kernel path.

## Resource observations

The parent task receipt, archive member `attempt-4/task-receipt.json`, controls resource acceptance. The worker receipt, archive member `attempt-4/worker-result.json`, binds its source identities and records its own OS high-water RSS. Both are preserved in [raw-evidence.tar.gz](raw-evidence.tar.gz).

| Measurement | Accepted attempt 4 |
|---|---:|
| Parent elapsed time, including process imports and exit | 4.7081630710017635 seconds |
| Probe elapsed time after its numerical imports | 2.042872362995695 seconds |
| Outer deadline | 180 seconds |
| Worker RSS ceiling | 1,073,741,824 bytes |
| Valid memory samples | 91 |
| Sampling interval | 0.05 seconds |
| Parent sampled peak worker RSS | 357,109,760 bytes |
| Worker OS high-water RSS | 357,396,480 bytes |
| Maximum observed cache/output bytes during monitoring | 4,080,225 bytes |
| Monitor error or stop reason | None |
| Process return code | 0 |
| Verified exit-transition observations needed in this run | 0 |

The sampled memory guard observes and terminates a worker that exceeds its ceiling. It is not an instantaneous kernel allocation cap. The sampled peak and OS high-water measurement have different observation methods and are retained separately. The cache/output figure describes the monitored working directory during execution; it is not the size of this publication archive, which adds source snapshots and a later assessment.

## Four preserved attempts

For each row, the parent receipt is member `attempt-N/task-receipt.json` inside [raw-evidence.tar.gz](raw-evidence.tar.gz), where `N` is the attempt number. The [member inventory](archive-inventory.json) records every member's size, SHA256, prior local-snapshot path, and evidence-origin path.

| Attempt | Parent status | Numerical worker status | Disposition |
|---|---|---|---|
| 1 | Failed | Failed before the probe could start | Rejected: wrapper import path |
| 2 | Failed | Failed during graph audit | Rejected: FP64 scalar storage in the original Torch export |
| 3 | **Failed** | **Passed** | **Rejected: parent resource monitor** |
| 4 | Passed | Passed | Accepted generated export qualification |

### Attempt 1: wrapper import path

The original `runpy` wrapper did not put the repository's `benchmarks` directory on Python's module search path. Importing the test module therefore failed with `ModuleNotFoundError: No module named 'model_export'`. The corrected wrapper supplies that directory explicitly. No numerical probe receipt or ONNX graph was emitted in attempt 1.

The original attempt bound only the four numerical source files in its receipt. Its retained wrapper and guard snapshots are also included, along with the unchanged identity helper, but those supplemental sources were not contemporaneously hashed by attempt 1. The assessment labels this distinction instead of retroactively claiming a complete original source binding. Subsequent attempts include the wrapper, guard, and identity helper in their before/after source hashes.

### Attempt 2: Torch scalar storage normalization

The actual Torch exporter generated two scalar `DOUBLE` constants for attention's `baddbmm` arguments: beta `1.0` and alpha `0.3535533905932738` for this tiny model's head width eight. Each constant was consumed exclusively by six standard ONNX `Cast(to=FLOAT)` nodes. Attention arithmetic already consumed the FP32 cast results, but the original graph audit rejected the stored FP64 constants.

The correction runs once on the common original graph, before any variant is constructed. It stores each exact FP32 cast result and leaves every Cast consumer unchanged. It accepts only finite scalar constants used exclusively by standard FP32 casts. Actual FP64 consumers, exposed FP64 graph outputs, non-scalars, and nonfinite or overflowing values remain failures. Real-ORT regression tests establish bit-identical outputs before and after this normalization.

The accepted receipt and graph metadata record both constants' original tensor bytes and hashes, converted FP32 bytes and values, and all unchanged consumers. This correction does not change the frozen precision, quantization, numerical, quality, or overhead thresholds. Attempt 2 remains rejected; its earlier graph is inventoried separately.

### Attempt 3: numerical pass rejected by the parent monitor

All numerical comparisons passed, and the worker exited with return code zero. The parent nevertheless recorded `status: failed`, `stopped_for: resource_monitor`, and a missing live process RSS reading during exit. Both the parent's failed classification and the worker's numerical pass are retained unmodified.

For a worker whose exit has not yet been observed by `Popen`, the monitor correction verifies the same procfs PID and process start time and requires a terminal process state before permitting at most a one-second reap grace. An already observed process exit is handled separately. Missing or unreadable RSS for a live process still fails. Attempt 4 is a fresh run under that corrected monitor. All six graph hashes are identical between attempts 3 and 4, as verified in the assessment. No numerical result or model variant was selected between those runs.

### Attempt 4: accepted observation

The final run passed source identity, numerical comparisons, process identity, the deadline, sampled RSS, and the worker's OS peak check. Its guard snapshot was copied and verified against the original recorded SHA256 before any later campaign-guard edits. A later change to the runner does not become part of this accepted observation.

## Archive contents and source reconstruction

[assessment.json](assessment.json) is the index. It records each attempt's classification, exact retained-file hashes, source bindings, supplemental snapshots, and omitted-artifact inventory. Its `archive` / `archive_member` and `snapshot_archive` / `snapshot_archive_member` fields identify members inside [raw-evidence.tar.gz](raw-evidence.tar.gz), not loose files. Raw task receipts, worker receipts, worker identities, stdout, and stderr are preserved inside that archive without modification. Numerical probe receipts exist only for attempts 3 and 4 because earlier attempts failed before emitting them. Attempt 2's original source-snapshot hash ledger is also preserved as member `attempt-2/original-source-snapshot-ledger.json`.

The archive's `source-snapshots/` member prefix contains all 12 distinct source versions needed by these attempts: three campaign guards, two exporters, two probe test modules, two wrappers, and the unchanged contract, ONNX controls, and identity helper. Each snapshot's filename includes its SHA256; the assessment maps it to the original repository path for each attempt. All 25 contemporaneously recorded source bindings are verified against those saved bytes. Before/after source maps agree for every attempt.

The archive holds all 35 previously stored raw files: 23 attempt records and 12 source snapshots, totaling 2,230,592 uncompressed content bytes. Every member was checked byte for byte against its loose copy and local staging commit `9df946fef11672594cbc075b2445f2fd050f7cc2` before the loose copy was removed. The [member inventory](archive-inventory.json) covers every archive member. This packaging changes storage and index references; it preserves all raw evidence bytes and every prior outcome and provenance distinction.

The 200,193-byte archive uses sorted regular-file members in POSIX ustar format, with no directory entries. Tar ownership, timestamps, and permissions are normalized; gzip has an empty filename, timestamp zero, and compression level nine. The inventory records the complete encoding settings. Two builds using those settings produced identical bytes. These normalized container fields do not replace the original timestamps and process observations retained inside the receipts.

From this folder, verify the published package and read a raw receipt without recreating the loose copies:

```bash
sha256sum -c SHA256SUMS
tar -tzf raw-evidence.tar.gz
tar -xOzf raw-evidence.tar.gz attempt-4/task-receipt.json
```

To verify every archived member against the inventory using Python's standard library:

```python
import hashlib
import json
import tarfile
from pathlib import Path

inventory = json.loads(Path("archive-inventory.json").read_text())
expected = {entry["archive_member"]: entry for entry in inventory["members"]}
with tarfile.open("raw-evidence.tar.gz", "r:gz") as archive:
    members = archive.getmembers()
    assert len(members) == inventory["member_count"] == len(expected)
    assert [member.name for member in members] == sorted(expected)
    for member in members:
        assert member.isfile()
        entry = expected[member.name]
        data = archive.extractfile(member).read()
        assert len(data) == member.size == entry["bytes"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]
print(f"Verified {len(expected)} unchanged evidence members")
```

Thirteen generated ONNX binaries are intentionally omitted: the unqualified baseline from attempt 2 and the six completed variants from each of attempts 3 and 4. Their sizes and hashes are retained in the per-attempt omitted-artifact inventories. Hashes for attempts 3 and 4 match the original per-arm probe receipts. The attempt-2 graph hash was computed during archive assembly because the run failed before emitting per-arm hashes; it is labeled accordingly. Incidental Hugging Face cache-format markers are inventoried and omitted as well. No pretrained weights, dataset text, or tokenized dataset artifacts were present in these probe directories.

To reproduce an attempt, read its mapped source snapshots from the archive and restore them to the original paths in an isolated checkout, use the matching pinned dependency environment, and restore its saved wrapper as `build/pinned-export-probe-worker.py`. Run that wrapper through its corresponding `campaign_guard.run_bounded_task` with a fresh output directory, the recorded one-thread environment, a 180-second deadline, and a 1 GiB worker-memory ceiling. The original command and guard parameters are in each archived task receipt. The numerical entry point used by the wrapper is `benchmarks/test_model_export.py --pinned-stack-probe <fresh-directory>`; invoking it alone does not supply the parent's termination monitor.

Dependency acquisition and wheel locks belong to the enclosing milestone's dependency evidence. Re-execution produces new timestamps, process IDs, timing, and memory observations. Preserve these receipts and record a new attempt rather than overwriting this history. [SHA256SUMS](SHA256SUMS) covers every final published file in this folder except itself, including the compressed archive and member inventory; the inventory covers all 35 raw members within the archive.
