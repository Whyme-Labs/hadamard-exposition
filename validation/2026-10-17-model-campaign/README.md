# Model implementation and blocked launch

This is the implementation and launch-qualification slice of [issue #5](https://github.com/Whyme-Labs/hadamard-exposition/issues/5), based on commit `a38ea0445fab7702392a963b91a6602a8b780f97`. The frozen [protocol](../../docs/experiments/model-benchmark-v1.md) and [manifest](../../benchmarks/model-benchmark-v1.json) are unchanged. The [execution supplement](../../docs/experiments/model-execution-v1.md) specifies the new runner's operating decisions before any pretrained-model result is opened.

**The pretrained campaign is blocked.** This record establishes isolated dependencies, tested exporter/cache behavior on a small generated model, offline orchestration checks and an actual failed host preflight. It establishes no Pythia quality, full-model parity, inference speedup, campaign feasibility or commercial saving. Issue #5 remains open.

## Implemented work

The adapter acquires only the pinned model/tokenizer and three named Parquet inputs. It records immutable artifact identities, preserves the frozen first-eligible article selection and separates development, timing and quality roles. It exports all six complete-model variants, changing only the specified post-GELU MLP output projections and their online transforms. Parameter/buffer counts, fixed signs, packed data/scales, initializers, graph hashes, cache IO and operator attributes are audited.

The runner requires a review tied to actual Git source bytes, observed dependency/ABI checks, full-model reference and cached-path parity, role disjointness and one conservative development cost proof. An immutable execution lock must precede quality evaluation. The measurement path implements token-weighted NLL, whole-article paired intervals, fixed paired timing blocks, isolated one-thread workers and retained primary/sensitivity decisions. The launch and resource guards preserve failures and stop at an unavailable prerequisite.

## Actual launch attempt

[preflight.json](launch-attempt-1/preflight.json) and [campaign.json](launch-attempt-1/campaign.json) are unchanged receipts from the actual `run_model.py run` invocation. The runtime and CPU matched the frozen contract. The memory gate failed before reading the review input, downloading artifacts, probing the converter or starting any worker.

| Observation | Retained value |
|---|---:|
| Required conservative available RAM | 6,442,450,944 bytes = 6 GiB |
| Observed conservative available RAM | 836,927,488 bytes ≈ 0.78 GiB |
| Cgroup headroom | 198,848,512 bytes |
| Credited inactive file cache after dirty/writeback deductions | 638,078,976 bytes |
| Host `MemAvailable` cap | 9,666,772,992 bytes |
| Output filesystem free space | 21,332,000,768 bytes |
| Workers started / model or dataset accessed | 0 / false |
| Source bytes unchanged during attempt | true |
| `campaign_ready` / adoption candidate | false / false |

Active file cache and reclaimable slab receive no credit. No memory-accounting relaxation, forced reclamation, pretrained download or model evaluation was used to get around this result. The attempt's source hashes identify its exact implementation; later reviews or source changes do not retroactively qualify it.

The initial `--review` path was the intended publication path. That file was not read because the host gate failed first. Its eventual existence does not change the rejected attempt or produce an execution lock.

### Fresh preflight after restoring the checkout

The local checkout later reverted to an earlier milestone. The saved publication package recovered all 46 implementation/evidence files, and the base files were retrieved through the GitHub connector. The restored tree is exactly `176d41898e21b9bc1d28b39e34aa37e89e6afbd3`, now published as commit `bdb27ea4ae520d9da0ccece06a8a2665b56577b1`. This is the same tree originally reviewed at local commit `9d1d5b1089055b623b918113f74153649b78cef9`. Neither archive nor any original receipt was regenerated.

After the finalization correction described below, a [fresh preflight](preflight-attempt-2/preflight.json) observed **6,354,026,496 bytes, about 5.92 GiB**, still below the unchanged 6 GiB requirement. The inspection interpreter also lacks the pinned ONNX and ONNX Runtime packages; the previous isolated environments are not present in this restored checkout. This invocation used `python3 benchmarks/run_model.py preflight --output build/model-campaign-preflight-2`, exited 2, and accessed no model or dataset. Its source hashes before and after agree. It is a host observation, not a second campaign execution or a replacement for the first launch receipt. [Issue #6](https://github.com/Whyme-Labs/hadamard-exposition/issues/6) tracks the execution-surface prerequisite, including restoration of both exact dependency environments.

## Dependency and numerical evidence

| Evidence | Result and scope |
|---|---|
| [Isolated dependencies](dependencies/README.md) | Converter closure: 47 packages; runtime closure: 21 packages; 55 unique wheel payloads checked. Exact URLs, hashes, original install reports, both installation outcomes, ABI receipts and source snapshots are retained. |
| [Pinned-stack exporter probe](export-probe/README.md) | Accepted attempt 4: six generated GPTNeoX variants, 24 dynamic cases, 36 further prefill/cached comparisons and 780 recorded output comparisons. Earlier rejected attempts remain rejected. |
| Maximum recorded relative Frobenius error | `5.170438578475888e-7`, against independent generated-model references |
| Maximum recorded absolute output error | `1.9371509552001953e-7` |
| Accepted probe monitored elapsed / OS peak RSS | 4.708163071 seconds / 357,396,480 bytes |

The probe uses an untrained six-layer GPTNeoX with hidden width 32 and intermediate width 64. It verifies dynamic cache paths, previous-cache retention, full/cached consistency, causal behavior and all six interventions through the actual pinned Torch/Transformers/ORT stack. The production exporter separately refuses that small configuration. This is distinct from the required Pythia-70M development parity on the two frozen articles.

The real export initially exposed two scalar DOUBLE constants that Torch immediately cast to FLOAT. The corrected exporter stores those exact FP32 cast values, retains the Cast nodes and records the original/converted bytes. Regression tests establish bit-identical outputs and reject genuine DOUBLE arithmetic, nonscalar values and nonfinite/overflow conversions. Probe attempt 3 then passed numerically but failed its parent's process-exit observation. The stricter identity-bound exit handling was corrected and tested; only attempt 4 is accepted.

## Offline tests and their evidence limits

- [Direct full-suite observation](tests/direct-suite-observation.json): 127 tests passed in 6.977 seconds before the final atomic-publication guard regression was added. This summary is transcribed from the shell-tool completion. That invocation did not record contemporaneous source hashes or an independent RSS receipt; it is not described as a bounded source-qualified run.
- [Focused guard recheck](tests/guard-recheck/worker/task-receipt.json): all 14 standard-library guard tests passed after the final disk-enumeration race fix, including the new regression. The observed worker completed in 0.910477216 seconds with 16 valid RSS samples and a 24,190,976-byte OS peak. The scoped ceiling was 128 MiB / 30 seconds. No NumPy, ONNX, Torch, model or dataset was imported. Its complete source hashes and worker source are retained.
- [Blocked full recheck](tests/blocked-full-recheck.json): a proposed full offline-suite rerun under the generated-control 1 GiB launch allowance stopped before starting a worker. The parent raised before retaining host counters; that missing observation is disclosed, with no reconstructed counter values. The original worker script is retained. This attempt is not accepted or retried under a weaker generated-control gate.
- [Exposition validation](tests/exposition-validation.json): the original tests, retained numerical results and bundled calculator checks pass; original source bytes remain unchanged.

The first two successful test runs cover 128 distinct offline checks with 13 overlapping guard tests. They do not constitute a single current-source 128-test bounded suite. The complete-flow unit fixture declares fictional child outcomes to verify all 169 task handoffs, prerequisite refusal, six-arm timing order and negative-primary retention. It makes no model calls and is not a campaign receipt.

The atomic-publication regression addresses a real integration race: a pending file can disappear during normal publication while the disk monitor scans. Missing names are tolerated only inside that scan; permission/IO errors and all process-identity/RSS failures still fail closed.

## Finalization review correction

The initial independent [standards review](reviews/initial-standards.md) blocked publication approval because final source hashing or disk accounting could raise again during shutdown, preventing the failed campaign receipt and explicit process-lock cleanup. The separate [specification review](reviews/initial-specification.md) passed the implementation and blocked-launch scope, while explicitly withholding full-campaign acceptance. Both original verdicts are retained.

The correction attempts the two final observations independently. An unavailable observation is `null`, with its exception type and message in `finalization_errors`; the original failure remains in the receipt. Unknown source identity also makes `inputs_unchanged` null. Every observation failure sets the campaign status to failed and disables the adoption decision. An unconditional nested `finally` releases and closes the process lock, including when final receipt publication or explicit unlock fails. The three dependency-lock navigation links were also corrected.

The [new focused qualification](tests/finalization-recheck/qualification.json) passed **seven standard-library regressions**, with zero failures, errors or skips. It exercises real campaign finalization, actual atomic JSON publication and real advisory-lock reacquisition, using explicit blocked-host and injected-error fixtures. The cases cover repeated symlink accounting refusal, independent and simultaneous source/disk failures, failed final publication, failed explicit unlock and the ordinary blocked-preflight path.

The parent observed 0.151912157 seconds, one valid RSS sample, a sampled peak of 24,862,720 bytes and an OS peak of 24,883,200 bytes. The declared scope was 128 MiB / 30 seconds and 32 MiB retained output. All 30 bound source files and the archived worker wrapper remained unchanged. The wrapper recorded no NumPy, ONNX, ONNX Runtime or Torch imports and no model/data access. The host observation, wrapper source, both receipts, worker identity and stdout/stderr are retained unchanged. This focused check does not substitute for the full offline suite, generated-model controls or the frozen pretrained campaign.

Both independent incremental reviews passed on source commit `8237ea186603b1b34aadbfdc9133bd956db41c05`, tree `00a7e6b0914a8e8cd46a010a121dc430318e09ae`. The exact [Standards](reviews/final-standards.md) and [Specification](reviews/final-specification.md) reports, their hashes and all 30 source hashes are recorded in [review.json](review.json). The [publisher binding check](reviews/publication-binding-check.json) used the production review validator to verify the named Git object and every current source file. The [review index](reviews/README.md) explains the original BLOCK and its resolution. These are independent agent reviews of implementation and retained blocked-launch evidence; full campaign acceptance remains outstanding.

## Remaining campaign acceptance

1. Resolve [issue #6](https://github.com/Whyme-Labs/hadamard-exposition/issues/6): obtain a zero-cost CPU execution surface satisfying the frozen memory, disk and hardware gates. A different CPU/architecture needs a separately reviewed hardware execution revision before measurement.
2. Run the command from the reviewed source and both exact dependency environments. Reobserve the host and preserve a fresh attempt directory.
3. Acquire pinned inputs, produce the actual model graphs and establish full/reference/cached development parity and role disjointness.
4. Complete the single six-arm development cost observation within preparation's 600 seconds. A failed time/RSS/cache projection stops before quality evaluation and requires a new reviewed protocol before changing the experiment.
5. If qualified, run all 32 quality articles and 20 paired timing blocks within the original 600/600/600-second phases and 1,800-second outer limit. Publish every outcome and failed gate.

The current private repository has no campaign workflow configured by this change. No remote runner or free hosted allocation is assumed, and no paid/GPU task is launched.
