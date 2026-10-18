# Exact environments and the complete offline suite

This milestone restores both exact dependency environments and closes the missing current-source full-suite qualification from [the preceding implementation milestone](../2026-10-17-model-campaign/README.md). The accepted fresh run passes **all 135 offline tests**, with zero failures, errors or skips, under the retained 180-second and 1 GiB generated-input limits. It supports the environment prerequisite in [issue #6](https://github.com/Whyme-Labs/hadamard-exposition/issues/6).

**The pretrained campaign remains blocked.** Its fresh preflight now passes the runtime checks and fails only the unchanged memory requirement. This record establishes dependency restoration, tiny ABI compatibility and offline test execution. Pythia development parity, model quality, latency, inference savings and campaign feasibility remain unmeasured in [issue #5](https://github.com/Whyme-Labs/hadamard-exposition/issues/5).

## Accepted fresh observations

The [dependency qualification](dependencies/qualification.json) and [offline qualification](offline/qualification.json) are unchanged copies of the original run receipts. Their full worker records and logs are in the archives below.

| Qualification | Observed result | Declared allowance |
|---|---:|---:|
| Exact converter installation and ABI | 47 packages, passed | Complete published converter wheel closure |
| Exact runtime installation and ABI | 21 packages, passed | Complete published runtime wheel closure |
| Complete dependency effort | 57.680884 seconds | 600 seconds |
| Fresh dependency HTTPS receives | 357,544,826 bytes | Remaining combined recovery allowance |
| Combined receives including the earlier secondary observation | 715,089,677 bytes | 1,073,741,824 bytes |
| Complete offline qualification | 6.728361 seconds | 180 seconds |
| Offline tests | 135 passed, zero failures, errors or skips | Every current `benchmarks/test_*.py` test |
| Offline worker OS peak RSS | 244,969,472 bytes | 1,073,741,824 bytes |

The dependency effort began at 2026-10-18 07:02:31 UTC. It includes fresh environment creation, both metered installations, complete installed-closure checks and both ABI probes. The offline qualification began at 07:06:38 UTC and includes a fresh runtime metadata and complete 21-package closure check, the observed suite, final source checks and the separate campaign preflight.

| Observed worker | Parent-observed duration | Valid RSS samples | OS peak RSS |
|---|---:|---:|---:|
| Converter installer | 40.730342 seconds | 787 | 224,903,168 bytes |
| Converter ABI | 2.385949 seconds | 44 | 416,604,160 bytes |
| Runtime installer | 13.303799 seconds | 255 | 107,147,264 bytes |
| Runtime ABI | 0.264899 seconds | 3 | 73,732,096 bytes |
| Complete offline suite | 6.610036 seconds | 130 | 244,969,472 bytes |

Every task passed its identity-bound resource monitor. The largest sampled worker RSS was 420,413,440 bytes during the converter ABI probe. The suite's sampled peak was 212,000,768 bytes. Sampled RSS and each worker's OS high-water observation are retained separately. They establish the named worker observations, not an instantaneous allocation cap or an aggregate bound over every test-declared child fixture.

## Exact dependency restoration

The [complete wheel lock](../../benchmarks/model-dependencies-v1.json), [converter installation list](../../benchmarks/locks/converter-requirements.txt) and [runtime installation list](../../benchmarks/locks/runtime-requirements.txt) are unchanged. Each target environment was created without pip and installed through the parent interpreter's external pip runner. The target package sets therefore contain exactly the locked distributions.

The installer used explicit wheel URLs with `--no-index --require-hashes --no-deps --only-binary=:all:`, zero retries and one shared dependency-effort deadline. All 68 package entries in the two fresh pip reports match their published package name, version, wheel URL and SHA256. The converter retains SymPy 1.13.1 for Torch 2.5.1+cpu; the runtime retains SymPy 1.14.0. Python is 3.12.14 in both environments.

The existing source-bound dependency workers verified complete installed sets, interpreter markers, active dependency edges and compatible wheel tags. Both executed a generated NumPy/ONNX Runtime matrix multiplication. The converter also passed Torch/NumPy computation and memory sharing, package imports and an in-memory Arrow/Parquet round trip. No pretrained checkpoint, tokenizer artifact, WikiText row or model-quality input was obtained or evaluated.

The unchanged archived HTTPS meter measures application-visible decrypted bytes returned by `SSLSocket.read`. It includes HTTP response headers and excludes TLS record overhead. The parent observes the same process that runs pip and enforces its outer deadline and RSS guard. Before each installer starts, an unknown aggregate transfer total is null. A valid final transfer receipt must match the remaining allowance, original deadline, interpreter and exit status before the aggregate becomes complete. A missing or invalid receipt ends the effort without another network attempt.

## Fresh campaign preflight

The [unchanged preflight receipt](offline/campaign-preflight.json), observed at 2026-10-18 07:06:45 UTC, records one blocking error.

| Host gate | Observed value | Result |
|---|---|---|
| CPU and architecture | AMD EPYC 9V74 80-Core Processor, x86_64 | Matches the frozen design |
| Runtime | Python 3.12.14, NumPy 2.3.5, ONNX 1.19.1, ORT 1.23.2 | Matches |
| CPU quota | 8 cores | Passes |
| Free disk | 25,023,062,016 bytes | Exceeds 4 GiB |
| Conservative available memory | 5,225,238,528 bytes, about 4.87 GiB | Below 6,442,450,944 bytes, or 6 GiB |
| Model or dataset accessed | false | Preflight only |

The memory calculation credits 682,549,248 bytes of cgroup headroom and 4,542,689,280 bytes of inactive file cache after dirty/writeback deductions, capped by host `MemAvailable`. Active file cache and reclaimable slab receive no credit. The complete original counters are retained. No threshold change, cache-pressure workaround, alternative CPU, paid service or GPU execution was used.

## The earlier run and the retention failure

A first restoration and full-suite run completed before an execution-service disconnection. Its observed results were recorded in [issue #6](https://github.com/Whyme-Labs/hadamard-exposition/issues/6#issuecomment-6246816407). When shell access returned, the checkout had resumed from an older snapshot and the newly written raw receipts, logs, helper files and environments were unavailable.

[attempt-1-secondary.json](attempt-1-secondary.json) preserves the completed tool-output observations, the failed packaging check and the subsequent retention failure. It is explicitly secondary evidence. The missing first-run raw files are not reconstructed, and that summary is not substituted for the fresh retained qualification.

The fresh restoration uses a new 600-second effort after that reset. The earlier reported 357,544,851 dependency bytes were deducted from its receive allowance. Fresh raw receipts account for another 357,544,826 bytes. Their sum remains below the original 1 GiB recovery allowance. The interval containing the service interruption is not described as part of one successful 600-second effort.

The new helper source and the secondary observation were committed before the fresh restoration. The dependency archive was then committed before the fresh suite. This separates the persistent checkpoints from later reporting work.

## Temporary-fixture observation discrepancy

Some negative tests deliberately create real symlinks and verify that the production disk accountant refuses them. Their temporary files therefore live in a sibling fixture tree. The production accountant still applies its strict rules to the retained evidence tree. No production guard was changed.

The first qualification reported zero regular files in its final fixture scan. A later inspection observed 199 synthetic files totaling 1,211,743 bytes. The fresh qualification likewise reported zero regular files; the separately retained [later inspection](fixture-observations.json) observed 175 files totaling 1,078,229 bytes. That inspection records paths, sizes, hashes and modification timestamps. **The cause of these differences is unresolved. Neither run establishes a cleanup guarantee.**

Both original zero-file observations remain in their receipts, and both later observations remain visible. Temporary fixture peak disk usage was explicitly outside the generated-suite measurement scope. The acceptance claim concerns the complete test result, source identities, worker RSS and elapsed time. The fictional fixture files are not pretrained campaign evidence.

The retained-output disk guard observed at most 840,380,178 bytes during dependency setup and 36,700 bytes during the suite. Installed virtual environments were separate prepared inputs because they contain intentional interpreter symlinks; their logical footprints were recorded using a non-following walk that fails on directory-read errors. These scoped observations do not claim that all temporary or installed files fit inside a measured whole-workspace disk peak.

## Retained evidence and source binding

| Record | Contents |
|---|---|
| [Dependency archive](dependencies/raw-evidence.tar.gz) and [inventory](dependencies/inventory.json) | 32 original regular files, including both complete pip reports, transfer receipts, installer and ABI worker records, identities, stdout/stderr, host observations, lock copy and final qualification |
| [Offline archive](offline/raw-evidence.tar.gz) and [inventory](offline/inventory.json) | Nine original regular files, including the full 135-test output, worker identity, task/worker receipts, host observation, qualification and fresh campaign preflight |
| [Verification receipt](verification.json) | Archive readback, every member hash, standalone-copy equality, five task bindings, qualified helper/source hashes, exact package-report identities, transfer arithmetic and earlier benchmark-source review verification |
| [Recovery source](sources/run-recovery.py) and [installer worker](sources/pip-worker.py) | Exact helpers used for the fresh runs |
| [HTTPS meter](sources/pip_meter.py) and [full-suite worker](sources/full-suite-worker.py) | Byte-identical copies of the earlier retained sources |
| [Snapshot helper](sources/snapshot-evidence.py) and [verification helper](sources/verify-evidence.py) | Reproducible archive creation and read-only verification |

The dependency archive is 376,354 bytes with SHA256 `e3d465bbe6ac71f65a2f9efaf915e6decec8f8e915823d6d6710f3a4d641f2c9`. The offline archive is 12,752 bytes with SHA256 `ef90c8954598fb82d1349d626ef4b4cbba2c695a8bc815a71ce78a65533343ba`. Together they retain 41 files and 1,514,428 uncompressed member bytes. Wheel bodies, installed venvs, regenerable caches and temporary negative-test fixtures are omitted; the inventories state those boundaries.

All 30 bound benchmark files retain source-map SHA256 `1dd75e9af0736795e4d83c26f866d15d9f7a3fe55003e399ddbd36951ab2d69e`. They match the earlier independently reviewed commit `8237ea186603b1b34aadbfdc9133bd956db41c05`, tree `00a7e6b0914a8e8cd46a010a121dc430318e09ae`, and the starting implementation commit `a72bb30a4b65a6adce751b5c6b136d6880f2d43b`. The new qualification helpers are bound separately by their before/after hashes. The frozen model, data roles, arms, signs, metrics, thresholds and campaign budgets remain unchanged.

## Reproduction

Use the frozen CPU/architecture and CPython 3.12.14. The parent interpreter needs pip and packaging; target environments start empty. Choose fresh paths for every attempt. A separate reproduction starts its own bounded effort. This recorded recovery supplied `--prior-https-bytes 357544851` to carry forward the earlier observed transfers.

```bash
python3 validation/2026-10-18-environment-recovery/sources/run-recovery.py dependencies \
  --repo "$PWD" \
  --output "$PWD/build/environment-recovery-003" \
  --venvs "$PWD/build/recovered-envs-003"

build/recovered-envs-003/runtime/bin/python \
  validation/2026-10-18-environment-recovery/sources/run-recovery.py suite \
  --repo "$PWD" \
  --output "$PWD/build/offline-recovery-003" \
  --dependency-effort "$PWD/build/environment-recovery-003"
```

The separate evidence verifier needs no package installation or experiment rerun. It reads the published archives and repository files and refuses an existing output path.

```bash
python3 validation/2026-10-18-environment-recovery/sources/verify-evidence.py \
  --repo "$PWD" --output recovery-evidence-verification-003.json
```

The next campaign step remains a successful frozen 6 GiB host preflight on an available zero-cost CPU surface. That only permits a fresh attempt. Actual pinned acquisition, all six full-model/reference/cache parity checks and the bounded development feasibility proof must still pass before any quality or timing result is accepted.
