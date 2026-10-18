# Pythia campaign execution, version 1

Owner: [issue #5](https://github.com/Whyme-Labs/hadamard-exposition/issues/5). This supplement records how the [runner](../../benchmarks/run_model.py) implements the frozen [benchmark protocol](model-benchmark-v1.md) and [manifest](../../benchmarks/model-benchmark-v1.json). It does not change their model, data, six arms, quantizer, signs, endpoints, thresholds, seeds or budgets. Its own bytes are included in the reviewed source identity.

**The full campaign remains blocked until the concrete launch prerequisites below pass.** Implemented code, generated controls and a dependency lock do not constitute a pretrained-model result. This private repository has no hosted campaign launch configured by this revision; no remote runner is assumed available. The current CLI accepts the frozen CPU/architecture and resource requirements. A different host needs explicit qualification before any supported execution change.

## Launch sequence and evidence

Use a new output directory for every attempt. The parent runs one observed child at a time. Existing model inputs, receipts, logs and failed attempts are preserved. The [resource guard](../../benchmarks/campaign_guard.py) and [runtime](../../benchmarks/model_runtime.py) implement the following sequence.

| Stage | Required observation |
|---|---|
| Host and source checks | Frozen hardware/runtime metadata, sufficient conservative memory and disk, and both independent review axes passed. Verify that the named Git commit/tree actually contains every current bound source file. |
| Isolated environments | The complete transitive [wheel lock](../../benchmarks/model-dependencies-v1.json) for converter and runtime, with exact versions, official source URLs and SHA256 identities. Verify installed package sets, interpreter and compatible wheel tags; execute the NumPy/ORT and converter Torch/NumPy/Arrow import and ABI probes. |
| Acquisition and selection | Download only pinned model/tokenizer and three dataset files. Record sizes, hashes and provenance. Apply the fixed first-eligible article rule and verify disjoint article IDs/content hashes. Keep token files separate by role. |
| Export | Produce all six standalone graphs using the [reviewed exporter](../../benchmarks/model_export.py). Retain parameter/buffer counts, signs, complete graph and initializer identities, packed codes/scales verification and the full graph-pair scope audit. |
| Reference and ONNX parity | Use both fixed development articles. Check full 513-token forwards and 512-token prefill plus one cached call; compare original ONNX with Transformers and rotated FP32 ONNX with original ONNX. Check aggregate NLL and every arm's full-versus-cached path. |
| Development cost proof | Launch six fresh child processes, one per arm, on the single deterministic development cost fixture below. Include graph auditing/loading, both warmups, both measured workloads and worker overhead in the projection. |
| Execution lock | Bind the successful prerequisite receipts and every retained prerequisite file to the reviewed sources and frozen design. Verify all bound file hashes and the reviewed Git object before publishing the lock. Only this complete lock permits quality evaluation. |

Converter and runtime Python environments are prepared inputs to the command. They remain isolated: Torch 2.5.1+cpu requires the converter's SymPy 1.13.1, while the qualification runtime pins SymPy 1.14.0. A package-name list or successful dependency resolution is insufficient; the observed ABI probes must pass.

Acquisition and selection may read, tokenize and hash the quality split to establish its fixed identity. They make no model calls and cannot guide fitting or design changes. The launch lock's `quality_test_accessed=false` means that quality prefixes have not been evaluated by a model. It does not claim that their file bytes were never read.

The parent verifies all bound prerequisite bytes at phase boundaries. Workers verify the execution-lock hash, current source/review identities, an explicit set of relevant JSON receipts, and the selected token identities; every graph load rechecks its byte and initializer identities plus structural/operator constraints. Unused large reference arrays and runtime profile JSONs are not rehashed by every timing worker. Git commit/tree content verification occurs in the parent before acquisition and again at lock publication.

## Development cost fixture and projections

The first selected development article has exactly 513 frozen tokens. Construct a 640-token cost fixture by taking indices `0..512`, then repeating indices `0..126`. Equivalently, output token index `i` uses source index `i % 513`. Retain the source article/token identity, this mapping and the new little-endian uint32 token hash. This artificial continuation is used only for cost and cache-shape checks; it supplies no new article, quality endpoint, calibration examples or sign selection.

Each fresh cost worker runs short warmup, short measurement, primary warmup and primary measurement, with cache reset for every request. This is the same 128+32 and 512+128 work used later. Profiles are disabled for cost/timing; development parity retains separate CPU operator profiles on the same graph hashes. ONNX feed construction, cache/output validation and the complete ONNX call are inside the timed step, consistently across arms. Tokenization, initial token-array construction and slicing, graph audit/loading and artifact handling remain outside forward latency but inside their enclosing resource budgets.

Define the following observed quantities from the six development arms:

- `P[a]`: the arm's complete two-article ONNX parity wall time, including graph audit/load, full/cached calls, NLL calculations, numerical comparisons and profile closure.
- `C[a]`: the parent's elapsed observation of that arm's fresh cost child, including process startup and completion.
- `W[a]`: the cost helper's inner `worker_wall_seconds`, including audit/load, both warmups and both measured requests.
- `O = max_a(max(0, C[a] - W[a]))`: observed child overhead outside the cost helper.

The predeclared operational estimates are:

```text
timing_seconds_upper  = 1.25 * 20 * sum_a(C[a])
quality_seconds_upper = 1.25 * (32 * sum_a(P[a]) + 36 * O)
projected_campaign_seconds = 600 + quality_seconds_upper + timing_seconds_upper
```

The quality estimate deliberately charges a complete two-article parity sequence for each of the 32 quality articles in every arm. This includes substantially more loading, cached-path and diagnostic work than the quality evaluation itself. It also charges overhead for all 36 quality children. These are conservative engineering projections, not statistical confidence bounds or a guarantee of completion.

Both projected measurement phases must fit their individual 600-second ceilings. The total projection reserves the full 600 seconds for preparation. `acquisition_export_seconds` records preparation elapsed when the proof is created; remaining file binding, verification and lock publication still consume that same preparation deadline. If a projection fails, stop before quality evaluation and retain the proof. Do not reduce article/block counts or change the frozen workload to fit.

## Quality and timing execution

Quality uses 32 FP32-pair children, one per article, followed by four quantized-arm children, each processing all 32 articles. Each pair loads original and rotated FP32 sessions sequentially and compares the two article logit arrays in memory. This means **36 child processes and 68 graph loads**. It avoids retaining all original quality logits: `32 * 513 * 50304 * 4 = 3,303,161,856` bytes, about 3.08 GiB, before any graph or reference storage.

Retain each article's NLL sum and 512-target count for all six arms, every FP32 logit control and the aggregate FP32 NLL control. Reset cache per article. The [statistics helpers](../../benchmarks/model_metrics.py) enforce the fixed pairing, whole-article bootstrap, token weighting and primary/sensitivity distinction.

Timing follows the frozen 20-block arm permutations and article schedule. It has 120 fresh children and 120 graph loads. Its two workloads, each with a warmup and measurement, produce 480 requests, 38,400 cached calls and 153,600 prefill tokens. Every worker retains full-call durations, post-warmup steady RSS and its OS high-water RSS, including loading and warmup. All arms and both workloads remain in the report when a primary endpoint fails.

## Limits, failures and interpretation

Preparation, quality and timing each have a 600-second ceiling within a 1,800-second campaign ceiling. Preparation includes dependency probes, acquisition, selection, export, reference/ONNX parity, six cost workers and lock publication. Require at least 6 GiB conservatively available memory and 4 GiB free disk before launch. The worker RSS limit remains 6 GiB, campaign cache/output limit 4 GiB, and model/dataset download limit 1 GiB. Use one CPU worker/thread, zero GPU execution and zero paid services.

The availability calculation is unchanged: cgroup headroom plus nonnegative inactive file cache after dirty/writeback deductions, capped by observed host `MemAvailable`. Missing evidence does not waive a gate. Identity-bound 50 ms RSS observations and the worker's OS peak provide complementary checks; sampling is not an instantaneous kernel allocation cap. The parent stops work at the first observed resource breach and retains partial files, worker identity, stdout/stderr and the failed task receipt.

A small generated test through the real Torch/Transformers/ONNX stack can establish import/export/cache behavior for its tested configuration. A generated graph test can establish IO, numerical-helper or operator conformance. Neither establishes pinned Pythia-70M parity, full-model feasibility or quality improvement. Those claims require the actual prerequisite and campaign receipts. A negative or inconclusive matched result is retained; group 16 cannot replace a failed primary endpoint, and no commercial saving follows from this pilot alone.

## Commands and acceptance

Run from the repository root with the qualified runtime Python available as `python3`. The paths below refer to already prepared environments and actual lock/review records; they are interface examples, not evidence of an executed campaign.

```bash
python3 benchmarks/run_model.py preflight \
  --output build/model-preflight-001

python3 benchmarks/run_model.py run \
  --output build/model-campaign-001 \
  --converter-python build/model-envs/converter/bin/python \
  --runtime-python build/model-envs/runtime/bin/python \
  --dependency-lock benchmarks/model-dependencies-v1.json \
  --review build/model-locks/review.json
```

Preflight records source and environment observations without model/data access. It returns a blocking status when any host requirement fails. Use a new output name for a later attempt; never replace the earlier receipt. A real review record must identify the independently reviewed commit/tree and current source hashes with both specification and standards reviews passed.

Full-campaign acceptance remains outstanding:

- [ ] Current host and both locked environments pass their concrete checks.
- [ ] Reviewed, acquired full-model graphs pass reference, rotation and cached-path parity.
- [ ] Six observed fresh-worker cost runs establish the bounded development proof.
- [ ] The immutable execution lock is published before quality model evaluation.
- [ ] All frozen quality/timing observations complete within the resource ceilings.
- [ ] Every arm, control, interval and failed gate is retained and interpreted within the pilot's scope.
