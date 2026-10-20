# Isolated dependency qualification

This record qualifies the Python dependencies for the converter and inference runtime. **No pretrained weights, tokenizer artifacts, WikiText rows or model-quality inputs were downloaded or evaluated.** The ABI checks used small generated arrays and two inline strings. `campaign_ready` remains false.

The [qualification receipt](qualification.json) is an unchanged copy of `build/model-dependencies/dependency-qualification.json`. The [wheel lock](../../../benchmarks/model-dependencies-v1.json) and [converter](../../../benchmarks/locks/converter-requirements.txt)/[runtime](../../../benchmarks/locks/runtime-requirements.txt) installation lists are exact copies of the qualified outputs.

## Outcome

| Check | Converter | Runtime |
|---|---:|---:|
| Complete installed packages | 47 | 21 |
| Active dependency edges verified | 78 | 27 |
| SymPy version | 1.13.1 | 1.14.0 |
| Tiny ABI probe elapsed | 2.693388 s | 0.550654 s |
| OS peak RSS during ABI probe | 391,622,656 bytes | 116,162,560 bytes |

Both installed closures, interpreter markers and wheel ABI tags passed for CPython 3.12.14 on Linux x86_64. The converter includes Torch 2.5.1+cpu. Eleven dependency-lock tests passed. Their exact source is archived.

The first sandboxed install attempt failed to resolve NumPy and recorded zero HTTPS reads. The subsequent scoped installation was approved through automatic review and completed. The entire install effort, including the first attempt and the interval between attempts, took 88.539215 seconds. Setup, ABI checks and lock verification finished 493.764976 seconds after the effort began, within the 600-second allowance.

The meter observed **370,456,444 application-visible decrypted HTTPS bytes**, within the 1 GiB dependency allowance. This includes response headers and metadata and excludes TLS record overhead. The 55 unique wheel payloads total **357,478,998 bytes**. These are dependency transfers, not pretrained model/data acquisition.

## Retained provenance

[provenance.tar.gz](provenance.tar.gz) contains 23 regular files: 1,257,238 bytes before compression, 353,211 bytes compressed. [inventory.json](inventory.json) gives every member's original repository-relative path, archive path, size and SHA256, plus the mapping for the separately published lock and qualification files.

| Archive prefix | Contents |
|---|---|
| `reports/` | Both complete, original pip installation reports, including all distribution metadata and source URLs |
| `receipts/` | Both ABI receipts; final installed-package/interpreter checks; effort and transfer receipts for every install attempt; original URL-to-local-wheel mapping |
| `logs/` | The failed initial installation log |
| `sources/` | Exact requirement files, lock implementation/tests, frozen model manifest, bootstrap, HTTPS meter and ABI-probe source snapshots |

Every source snapshot and original evidence file named by `qualification.json` was checked against its recorded hash before packaging. Archive ownership and timestamps are normalized; member content is unchanged.

| Artifact | SHA256 |
|---|---|
| Wheel lock | `f4b045d55bb3de7d8673c2a1e89ee15ec3dcd398097df381d3faa0761c67878b` |
| Qualification receipt | `a56ea9e3183d5e582db79b77db0919086da04f5eae3450e35cf196f6f0da8ba3` |
| Provenance archive | `625b311c9d69c91708e9c4c7f2ce71f946d11ced4d7ce34a94d1b70b139f58ef` |
| Inventory | `5defa84119fcced09f47470f35fd8ee4f38de48e5de45e2849dd58422e87847a` |

## Verification limits and reproduction

**Binary wheel bodies and installed virtual environments are omitted.** All 55 wheel bodies were locally hashed and checked against their embedded package metadata. Reported hashes matched where supplied. Their sizes, hashes and official URLs remain in the published lock. `receipts/wheel-files.json` records the original local cache paths; it does not mean those paths or bodies are included in this archive. Reproduction obtains fresh copies from the locked URLs and verifies their SHA256 values.

PyTorch's Jinja2 installation-report entry supplied no hash. The lock initially rejected it. The retained 134,899-byte wheel at that exact URL supplied SHA256 `85ece4451f492d0c13c5dd7c13a64681a86afae63a5f347908daf103ce6d2f67`; its metadata identified Jinja2 3.1.6. This also matches the [official PyPI wheel checksum](https://pypi.org/project/Jinja2/3.1.6/#files). The original pip report was not edited.

To recreate either environment, use a fresh CPython 3.12.14 virtual environment and install its published requirements list with pip's `--require-hashes --no-deps --only-binary=:all:` options. The list includes the complete dependency closure. Run `validate_environment()` inside that interpreter, then the archived ABI probe. Use a new bounded attempt and retain its receipts; archived scripts retain their original relative-path assumptions, documented in the inventory.

Set `PYTHONPATH` to the repository only. Set `HF_HOME`/`TRANSFORMERS_CACHE` and `MPLCONFIGDIR` to scoped writable build directories. The original ABI probes emitted warnings about default cache locations. Their receipts and source are retained; standalone stdout/stderr files were not saved. Routine successful installer logs and superseded successful preliminary package-check summaries are omitted as duplicates; the inventory lists these omissions.

This evidence establishes dependency identities, closure, isolation checks and tiny ABI execution. It does not establish full-model export parity, the six model graphs, the 6 GiB campaign-memory prerequisite or benchmark feasibility.
