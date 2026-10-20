# First pretrained run and reference-cache diagnosis

Date: 18 October 2026. Tracks [issue #6](https://github.com/Whyme-Labs/hadamard-exposition/issues/6) and [issue #5](https://github.com/Whyme-Labs/hadamard-exposition/issues/5). This milestone extends the [pinned environment recovery](../2026-10-18-environment-recovery/README.md).

## Decision

The zero-cost CPU execution prerequisite has been demonstrated. The unchanged host preflight passed in fresh campaign attempts, both exact dependency environments passed their import and ABI checks, and the network-enabled attempt acquired all pinned inputs and exported all six pretrained Pythia graphs.

The completed six-forward reference diagnostic reproduces the original failed logit controls and localizes the first numerical divergence in both development articles to the first attention QKV projection. Identical last-token input values produce slightly different FP32 outputs under the full-sequence and cached call shapes. This establishes a concrete boundary for the next investigation, without identifying the internal kernel cause.

The frozen campaign remains blocked at the reference model's own full-versus-cached logit control. No ONNX development parity, cost proof, execution lock, quality evaluation or timing campaign followed that failure. No Hadamard quality benefit or inference saving follows from this milestone.

[Issue #6 is closed as completed](https://github.com/Whyme-Labs/hadamard-exposition/issues/6#issuecomment-6254174039) because its host and environment prerequisites were demonstrated and linked in issue #5. That is a historical qualification, not a guarantee of future host availability. Issue #5 remains open for full campaign acceptance.

## What changed

The first reviewed maintenance pass advised only this project's installation caches and prepared environments. Its [receipt](cache-maintenance/advice.json) records 54,501 accepted file-advice calls over 2,687,642,820 logical bytes, 5.985 seconds elapsed and no target-data write or deletion. The [original preflight](preflight-before-cache/preflight.json) reported 5,222,633,472 available bytes. The [fresh post-maintenance preflight](preflight-after-cache/preflight.json) reported 7,467,794,432 bytes against the unchanged 6,442,450,944-byte requirement.

File advice is nonbinding. Those observations do not establish exactly how much memory the operation reclaimed, nor attribute the entire host change to our pass. Later file access can warm caches again. Every model launch still needs a fresh host observation.

The benchmark implementation, manifest, protocol, six arms, dependency locks, signs and acceptance thresholds remain byte-for-byte unchanged across all 30 bound source files. Their canonical source-map SHA256 is `1dd75e9af0736795e4d83c26f866d15d9f7a3fe55003e399ddbd36951ab2d69e`. The model-source review remains the [original reviewed implementation](../2026-10-17-model-campaign/review.json).

## The two actual campaign attempts

| Observation | First attempt | Second attempt |
|---|---|---|
| Fresh host preflight | Passed | Passed |
| Exact converter and runtime dependency checks | Passed | Passed |
| Public artifact acquisition | Socket creation denied by the sandbox | All eight pinned inputs acquired |
| Artifact-body bytes downloaded | 0 | 175,891,986 |
| Pretrained export | Not reached | All six graphs exported and structurally audited |
| Reference development | Not reached | Failed full-versus-cached absolute logit error |
| Quality model evaluation | Not started | Not started |
| Campaign outcome | Blocked | Blocked |

The [first campaign receipt](campaign-attempt-1/campaign.json), [acquisition failure](campaign-attempt-1/acquisition.json) and complete raw logs remain intact. Its `model_or_dataset_accessed=true` records that acquisition was attempted; the acquisition receipt records zero transferred artifact-body bytes and no model call.

The second attempt used the platform's approved network-access path for the same frozen command in a new directory. Its [campaign receipt](campaign-attempt-2/campaign.json), [host preflight](campaign-attempt-2/preflight.json) and [acquisition receipt](campaign-attempt-2/acquisition.json) are unchanged originals. It completed 41.739 seconds of preparation before the reference gate stopped it. This elapsed time is preparation cost, not model inference performance.

The host is the frozen Linux x86_64 AMD EPYC 9V74 surface, with an eight-core quota and an 8 GiB cgroup limit. The actual second launch observed 7,463,809,024 conservative available memory bytes and 28,594,003,968 free disk bytes. Execution used one CPU worker/thread, no GPU and no paid service. The 1 GiB artifact-body, 6 GiB worker RSS, 4 GiB output and 600-second preparation limits remained in force.

The largest recorded worker OS high-water RSS was 2,474,774,528 bytes during export. The parent observed a maximum of 2,662,662,840 campaign bytes during the final reference task. These are retained observations under the documented sampling policy, not guarantees about every instantaneous allocation or later directory size.

## Acquired inputs and graph exports

The model revision is `301b2c9bdf4d6da917d8f02d3c48aac481a60d06`. The checkpoint file SHA256 is `ebfa4e2f18696ebd83716a0d39fe2c025f2ff8483f72a83ca59c475692fc9d15`. WikiText uses revision `b08601e04326c79dfdd32d625aee71d232d685c3`. Acquisition verified immutable input identities and the published hashes for the large model and dataset files.

The selected roles remain two development prefixes of 513 tokens, four timing prefixes of 640 tokens, and 32 quality prefixes of 513 tokens. The selection receipt passes role disjointness and records zero model calls. Selection reads and hashes role inputs; `quality_test_accessed=false` means no quality prefix was evaluated by a model.

The exporter observed 70,426,624 FP32 model parameters occupying 281,706,496 bytes after loading. It retained the separate buffer and state-dictionary counts in its original receipt. The following are actual standalone graph file sizes.

| Arm | Serialized graph bytes | Packed selected-weight code bytes | FP32 scale bytes |
|---|---:|---:|---:|
| Original FP32 | 286,241,403 | 0 | 0 |
| Rotated FP32 | 286,360,353 | 0 | 0 |
| Original W4A32, group 32 | 265,007,937 | 3,145,728 | 786,432 |
| Rotated W4A32, group 32 | 265,126,887 | 3,145,728 | 786,432 |
| Original W4A32, group 16 | 265,794,381 | 3,145,728 | 1,572,864 |
| Rotated W4A32, group 16 | 265,913,331 | 3,145,728 | 1,572,864 |

The six graphs total 1,634,444,292 bytes. Each quantized graph contains exactly six `MatMulNBits` nodes. Each rotated graph retains 66 online Add nodes, 66 online Sub nodes and 49,152 bytes of sign constants. Structural export success establishes these file and graph properties. Full-model numerical acceptance still requires the later parity gates.

The original `export/export.json` inside the [raw archive](campaign-attempt-2/raw-evidence.tar.gz) retains every graph hash, initializer hash, operator attribute and per-site audit.

## Failed reference control

The [original reference receipt](campaign-attempt-2/reference.json) compares each complete 513-token forward with a separate 512-token prefill followed by one cached token. The cached token is position 512.

| Development article | Maximum absolute cached logit error | Frozen limit | Relative Frobenius error | Relative limit |
|---|---:|---:|---:|---:|
| Validation article starting at row 1 | 0.016845703125 | 0.001 | 2.753837674e-6 | 1e-5 |
| Validation article starting at row 47 | 0.001708984375 | 0.001 | 4.035291974e-7 | 1e-5 |

For both articles, every logit in the first 512 positions of the full forward equals the separate prefill output exactly. The one-token cached outputs fail the absolute gate. Both conditions are required by the frozen design.

[Analysis of the retained final-token arrays](retained-logit-analysis.json) finds 41,289 of 50,304 logits above the absolute limit in the first article and 498 in the second. The worst differences occur at ordinary vocabulary IDs. The top-20 ordering remains the same, which does not replace the failed numerical control.

The full final-token logits have means near 1,056 and 1,051. This large common magnitude contributes to the denominator of relative Frobenius error. The discrepancy is not purely a common scalar shift: even the best possible shift leaves maximum errors of 0.0126953125 and 0.00140380859375. These descriptive calculations introduce no alternative acceptance criterion.

## Bounded trace and first numerical divergence

The [version-2 plan](diagnostic-plan-v2.md) and [both prospective reviews](diagnostic-review-v2.json) were published at commit `49d787419737f3ab0da3b692549d6bd6c2912e63` before execution. The [parent receipt](reference-trace-v2/trace-run.json) passes with exactly six calls in 6.120 seconds. The worker records 5.444 seconds, a 794,464,256-byte OS RSS high-water observation and unchanged inputs. The parent separately observed a 794,763,264-byte sampled peak across 117 valid samples. Both observations are below the 6 GiB ceiling; the diagnostic's elapsed time includes instrumentation and is not an inference benchmark.

All six replay logit content identities and every original cache identity match the retained reference receipt. Both full-forward final-position slices and both complete cached arrays also match their retained original bytes directly. Full and prefill original NPYs are unavailable, so their full-array elementwise equality and numerical error fields remain null. This is exact reproduction under the explicitly recorded identity scheme, with direct comparisons where original arrays survive. The [worker receipt](reference-trace-v2/worker-result.json) preserves the complete comparison basis.

For **both articles**, the first numerically unequal saved event is the output of `gpt_neox.layers.0.attention.query_key_value`. Its last-token input vectors are byte-identical; the complete module input shapes are `[1,513,512]` for full evaluation and `[1,1,512]` for cached evaluation. The output has 1,536 entries. Maximum difference is exactly **0.000001430511474609375** in each article, affecting 1,280 and 1,286 entries respectively.

The sixteen preceding saved events are numerically equal. This does not mean every earlier byte is identical: the equivalent last-query masks differ in the sign of their permitted-position zero values. Both masks have retained shape `[1,1,1,514]`, permit the same 513 positions and mask the extra position. Recorded token/cache positions are 512 and the rotary cosine/sine observations match. All 24 full-prefix/prefill cache comparisons and all 24 cached-prefix/prefill comparisons match in data identity; the 24 supplied prefill arrays remain unchanged.

The pinned reference applies the QKV projection before rotary application, cache update and attention-mask addition. This places the first numerical divergence in a linear operation receiving the same last-token values under different call shapes. Shape-dependent FP32 linear evaluation is therefore the leading explanation for this first divergence. It is consistent with the [general PyTorch numerical-accuracy guidance](https://docs.pytorch.org/docs/2.14/notes/numerical_accuracy.html#batched-computations-or-slice-computations). That documentation describes a general limitation; this trace uses pinned Torch 2.5.1 and does not identify an internal MKL/oneDNN kernel or prove an accumulation order.

The observed differences later change through the model:

| Saved boundary, maximum absolute difference | Article at row 1 | Article at row 47 |
|---|---:|---:|
| First attention QKV output | 0.000001430511474609375 | 0.000001430511474609375 |
| Transformer block 0 output | 0.00000095367431640625 | 0.0000029206275939941406 |
| Transformer block 2 output | 0.000002384185791015625 | 0.0000019073486328125 |
| Transformer block 3 output | 0.00024706125259399414 | 0.00009328126907348633 |
| Transformer block 5 output | 0.002376079559326172 | 0.00032830238342285156 |
| Final layer normalization output | 0.00754547119140625 | 0.00151824951171875 |
| Final logits | 0.016845703125 | 0.001708984375 |

The [derived trace summary](trace-analysis.json) records these boundaries and the explicit comparison semantics. Other linear operations, including the first block's parallel MLP branch, also show numerical differences. The first QKV discrepancy cannot by itself be assigned responsibility for all later error. The unchanged frozen full-versus-cached control still fails in the reproduced run.

## Recovery and retained resource observations

Automated workspace maintenance removed the earlier local checkout, prepared environments, checkpoint, graphs and full/prefill arrays while version-1 publication was pending. [Version 1](diagnostic-plan.md) was reviewed and published but never executed. Its files and reviews remain unchanged. The [source-recovery record](source-recovery.json) verifies all 160 original repository blobs and the original reviewed Git/source identities.

The [fresh dependency restoration](diagnostic-environment-recovery/qualification.json) passed both complete wheel closures and ABI checks in 73.805 seconds. It received 357,544,808 new measured HTTPS bytes and carried the preceding 715,089,677 bytes, for a combined **1,072,634,485 bytes**. This stayed below the existing 1 GiB ceiling with **1,107,339 bytes remaining**. These are dependency HTTPS-read observations, separate from model/dataset response-body accounting.

[Input recovery](diagnostic-input-recovery/reconstruction.json) completed in 6.818 seconds without a model call. The unchanged acquisition worker reacquired all eight pinned files, totaling 175,891,986 body bytes; all eight recorded identities matched the original acquisition. The ten consumed original evidence files were copied unchanged, and the five complete model files were copied into the diagnostic's separate model directory. Dataset bodies were downloaded by the unchanged allowlist, but no dataset parsing, reselection or quality evaluation occurred.

The one [reviewed advisory pass](recovered-cache-maintenance/advice.json) records 54,519 accepted file-advice operations over 3,565,454,159 logical bytes in 4.561 seconds. Metadata remained unchanged, with no input-data writes or deletions. The subsequent [frozen host preflight](reference-trace-v2/preflight.json) passed with **7,085,432,832 conservative available bytes**. These observations do not establish a reclaimed-memory quantity.

### Clarification about an unreferenced partial file

The later input snapshot also observed `new-acquisition/artifacts/model/model.safetensors.partial`: 152,043,520 bytes, outside the eight acquisition records and the trace's consumed-input map. Its origin is unresolved. Its recorded metadata change follows the completed reconstruction receipt, and the maintenance journal subsequently records that same partial identity. Metadata does not establish when or how it was created.

The [append-only clarification](diagnostic-input-recovery/omission-clarification.json) corrects the initial inventory's overly broad public-input label without changing that inventory, the archive or the partial file. Its hash establishes observed byte identity only. The current new-acquisition directory includes this extra file and must not be described as freshly passing the exact eight-file acquisition verifier; the successful verification receipt describes the earlier observation. The five complete files actually consumed by the trace remain separately bound to the original model identities.

The later snapshot represents 497,224,832 regular-file bytes. This equals the reconstruction receipt's 345,168,215-byte pre-finalization observation, its 13,097-byte final receipt and the 152,043,520-byte partial. The partial is included in the recorded maintenance footprint. No instantaneous footprint or cleanup guarantee is inferred.

## Evidence and reproduction

The second attempt's [archive inventory](campaign-attempt-2/inventory.json) binds all 49 retained raw receipt, log, task and identity files, totaling 2,312,296 uncompressed bytes. The archive is 514,572 bytes with SHA256 `320ab8f6dbcb36b4cc962de25b193f9cbfee88345fae37beb1ea9453f373031e`. Both independent reviewers verified every retained member and the standalone receipt copies.

Large acquired inputs, generated graphs, full development logit arrays and nondevelopment token files have explicit omission records with byte identities. No quality output was produced. The exact two full-forward final rows and two cached rows are separately retained in [cache-comparison-slices.npz](campaign-attempt-2/cache-comparison-slices.npz). Its [derivation record](campaign-attempt-2/slice-derivation.json) distinguishes copied slices from original receipts and binds them to the original arrays. Its SHA256 is `6972d7416056a53c840b1bf62ce139a34f27325a8ad611fc6f3aac6e4cef6a6f`.

Recompute the retained-array description without loading a model:

```bash
build/diagnostic-environments-001/runtime/bin/python \
  validation/2026-10-18-campaign-development/sources/analyze-retained-logits.py \
  --evidence validation/2026-10-18-campaign-development/campaign-attempt-2 \
  --output build/retained-logit-analysis-new.json
```

The original campaign command and interpreter paths are preserved in the worker/task receipts. Every campaign rerun must use a fresh directory and the unchanged runner gates. This milestone changes no acceptance record for an earlier failed attempt.

The additional version-2 archives preserve the recovery and diagnostic observations:

| Archive and inventory | Retained files | Archive bytes | Contents |
|---|---:|---:|---|
| [Dependency restoration](diagnostic-environment-recovery/inventory.json) | 32 | 376,461 | Install, package-closure, ABI, process and resource receipts |
| [Input recovery](diagnostic-input-recovery/inventory.json) | 20 | 884,064 | Copied development evidence, acquisition and reconstruction receipts |
| [Scoped cache advice](recovered-cache-maintenance/inventory.json) | 3 | 3,825,388 | Advice receipt and complete per-file journal |
| [Reference trace](reference-trace-v2/inventory.json) | 15 | 2,216,803 | Six trace NPZs, worker result, launch, process and resource evidence |

Each inventory binds archive bytes, member bytes and SHA256 identities. Large public input bodies are omitted explicitly; the separate partial-file clarification above limits the original input inventory's classification. The trace archive retains all six diagnostic array packages. The original failed campaign and version-1 plan remain separate evidence.

## Validation and review

The [documented validation receipt](exposition-validation.json) records a passing `python scripts/validate.py`: 25 focused tests, independent checks of the retained numerical results, five bundled-calculator cases and unchanged inputs. No new synthetic sweep was run. The earlier 135-test offline campaign suite remains the result for the unchanged 30-file benchmark source map; it was not rerun for these diagnostic records and documentation changes.

The [prospective version-2 review](diagnostic-review-v2.json) binds the five diagnostic/procedure sources and four unchanged environment helpers to the published pre-execution checkpoint. Final results and evidence receive separate [Specification review](reviews/final-specification.md) and [Standards review](reviews/final-standards.md), recorded in [final-review.json](final-review.json). Those reviews assess this diagnostic milestone and do not turn the failed campaign control into a pass.

## Next milestone

Issue #5's next milestone is a separately preregistered operator-level investigation of the first QKV projection and the parallel first-block MLP branch. It should compare the observed full-sequence and one-token FP32 call shapes using the pinned parameters and retained input values, with a higher-precision arithmetic reference to distinguish shape-related rounding from an implementation error. The design must state its exact inputs, permitted calls, resource budget and decision criteria before execution.

The required deliverable is evidence for a specific corrective approach and a reviewed decision about how the baseline control should be evaluated. A changed implementation or acceptance contract requires a new version and fresh validation; the original failed result stays failed. Full-model ONNX parity, the development cost proof and the frozen quality/timing gates must then pass in order before any model-quality or inference-cost claim. No such follow-up was executed in this milestone.
