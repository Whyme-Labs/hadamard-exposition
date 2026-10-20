# Reference cache divergence diagnostic, version 2

Date: 18 October 2026 UTC. Tracks [issue #5](https://github.com/Whyme-Labs/hadamard-exposition/issues/5). This is a prospective recovery and diagnostic procedure, not a revision of the benchmark or its acceptance limits.

## Reason for this version

The actual campaign retained at commit `c45ff6b4f29ad6190e5783ff36a7a71bdd4e8e2a` exported six pretrained graphs, then failed the unmodified Transformers reference's full-versus-cached absolute logit control. Errors were 0.016845703125 and 0.001708984375 against the frozen 0.001 limit. No ONNX parity, development cost proof, execution lock, quality or timing stage followed.

Version 1 of this diagnostic was reviewed and published at `8d97748bf5e6598af2eaaaf5b63c90609e423fd5`, but never executed. Automated workspace maintenance removed the checkout, prepared environments, downloaded model, exported graphs and original full/prefill arrays while publication was pending. GitHub retains the original receipts, all six logit content identities, both complete cached arrays, and both full-forward final-position slices. The old inventory's statement that omitted files remained locally describes its earlier snapshot; those files are now unavailable. Preserve all version-1 files and reviews unchanged as a never-executed procedure superseded by this version.

The repository was reconstructed from the retained GitHub tree, and every one of its 160 original file blobs was verified. The original reviewed commit/tree objects and all thirty bound benchmark source hashes were restored exactly. No benchmark source, model, development token or numerical threshold changes here.

## Sequence and stopping rules

Publish this plan and both independent prospective reviews before restoration or diagnostic execution. Use fresh fixed roots below `build`; preserve every attempted effort and all original committed evidence. Stop after the first failed prerequisite. Do not retry downloads, repeat maintenance, loosen limits, regenerate missing original logits, or run an alternate model implementation.

### 1. Restore exact environments using the existing reviewed helper

Run the unchanged `validation/2026-10-18-environment-recovery/sources/run-recovery.py dependencies` with repository root, output `build/diagnostic-environment-recovery-001`, venv root `build/diagnostic-environments-001`, and `--prior-https-bytes 715089677`. The preceding accepted dependency receipt supplies that prior observed total.

This is a new restoration effort after pruning, with a fresh 600-second deadline, 1 GiB worker RSS ceiling and 4 GiB retained cache/output allowance. Prepared environment footprints are separately observed, as in the existing reviewed helper. Carry prior observed HTTPS reads into the unchanged combined 1 GiB receive ceiling. Only 358,652,147 bytes remain; the preceding restoration consumed 357,544,826. That estimate does not guarantee this attempt will fit. Exhaustion, a failed installation/ABI check or missing transfer accounting stops the sequence. No retries, fallback packages, different wheel hashes or newly reset receive allowance are permitted.

Both complete wheel closures and their fresh generated ABI checks must pass. The 135-test offline suite already passed on these unchanged benchmark sources; it need not be repeated solely because this diagnostic adds separate observation helpers. Run the repository's documented default exposition validation once before the final proposal.

### 2. Recover diagnostic inputs with separate acquisition provenance

Run `sources/prepare-reference-inputs-v2.py` under the repository process lock with the exact version-2 review. Its fixed fresh root is `build/reference-diagnostic-inputs-001`. It requires the original source review/Git objects, both prospective review axes, all thirty frozen source hashes, and the accepted fresh environment receipt with the carried byte count.

The parent verifies the original 49-member archive before copying only the eight consumed original receipt/token/cached-array members. Copy the retained slice NPZ and derivation receipt as the ninth and tenth evidence inputs. Paths and byte hashes are preserved. Full and prefill NPY files are not reconstructed.

Use the unchanged acquisition worker for the manifest's exact eight pinned files under `new-acquisition/artifacts`. Its public allowlist has no five-file mode. Require the frozen CPU and Python, a fresh 1 GiB available-memory acquisition preflight, 4 GiB free disk, a 600-second total recovery deadline, 1 GiB worker RSS and 4 GiB total fresh input/output allowance. This preserves the separate frozen 1 GiB model/dataset response-body acquisition limit. It is distinct from dependency HTTPS-read accounting.

Keep all fresh worker, transfer, identity and resource observations. Apply unchanged acquisition verification and compare all eight ordered original URLs, repositories, revisions, sizes and content hashes against the original acquisition receipt. Copy only the five verified model files to `artifacts/model` for the diagnostic. The fresh acquisition receipt remains under `new-acquisition`; it never replaces the copied original receipt.

The three dataset artifact bodies are necessarily downloaded by the unchanged worker and explicitly recorded. Do not parse them, run selection, load quality tokens or call a quality model. In these receipts, `quality_test_accessed: false` describes model evaluation; separate fields record downloaded dataset bodies and `dataset_parsed: false`. No model forward is permitted in input recovery. Missing acquisition accounting remains unknown.

Retain `reconstruction.json` with the exact ten copied evidence identities, five reacquired model identities, original campaign identity, new acquisition receipts, source identities, time/disk observations and failures. Its `full_prefill_logits_available` is false. A final identity or resource failure keeps reconstruction failed.

### 3. Perform one scoped advisory pass and fresh host preflight

Run `sources/release-recovered-cache-v2.py` exactly once over these four roots, all created by this recovery:

- `build/diagnostic-environment-recovery-001/pip-cache`
- `build/diagnostic-environment-recovery-001/pip-temporary`
- `build/diagnostic-environments-001`
- `build/reference-diagnostic-inputs-001`

This is the previously reviewed descriptor-anchored advisory helper with only the explicit owned roots changed. Keep its current-user, single-link regular-file checks, no symlink following, read-only hashing, `POSIX_FADV_DONTNEED` advice, before/after metadata checks, process lock, 120-second deadline and 512 MiB address-space ceiling. Preserve the full journal, source identities and outcome. Do not delete files, change their data, advise unrelated caches or use global memory controls. Advice does not establish a reclaimed-byte quantity or guarantee the subsequent preflight.

Then `sources/run-reference-trace-v2.py` requires that successful complete journal, exact reviews, successful input reconstruction, and the unchanged frozen 6 GiB conservative available-memory preflight. A blocked preflight stops the sequence.

### 4. Make exactly six observed reference calls

Use the freshly qualified converter interpreter and `sources/reference-trace-worker-v2.py`. Retain version 1's unchanged `load_reference` and `reference_forward`, CPU FP32 eager attention, evaluation mode, original parameters, same two development prefixes, and one worker/thread. Exactly six calls are permitted: full 513, prefill 512, cached one for article 0, then the same three calls for article 1.

Hooks copy observations and return no replacements. Keep the same last-token boundaries, actual positions and last-query masks, full/prefill and cached/prefill cache-prefix checks, independent prefill-cache snapshots, backend observations and source rechecks as version 1. The parent uses the existing observed-worker guard with a 120-second deadline, 6 GiB RSS ceiling and 64 MiB new trace-output allowance. Input/environment roots are read-only prepared inputs outside this new output allowance. No network or quality/timing work is permitted.

For each of six replay logits require exact agreement with the original recorded shape, dtype, byte count and canonical array-content SHA256. Also directly compare both full-forward final-position slices and both complete cached arrays against the retained original bytes. For missing full/prefill arrays, elementwise equality and full-array error metrics are unavailable and must be null with an explanation. A content-hash mismatch fails exact reproduction even if a retained row matches. Do not substitute a newly regenerated array for an original.

Retain six small observation NPZs and all task/identity/result logs. Save the first differing observed boundary and the first tokenwise module with equal input bytes but different output bytes if one exists. These localize observed divergence and do not establish an internal kernel cause.

## What completes this diagnostic milestone

Report the actual original failure, recovered-input provenance and bounded version-2 outcome. A passed diagnostic means reproduction by the stated retained identity checks; it does not pass the failed numerical control or create an execution lock. A failed or blocked diagnostic remains useful evidence and is retained honestly. Issue #5 remains open until its original parity, cost, quality and timing acceptance is met.

Any proposed arithmetic/backend change or new acceptance contract needs a separate prospective version and fresh evidence. The historical host qualification can close issue #6 once its passing source-bound preflight and campaign receipt are linked in issue #5; this is not a guarantee about later host availability.
