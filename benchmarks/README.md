# Matched model benchmark

The [version 1 protocol](../docs/experiments/model-benchmark-v1.md) and [machine-readable contract](model-benchmark-v1.json) define a six-arm Pythia-70M W4A32 experiment. This directory implements the design validator, packed-operator controls, pinned acquisition, full-model exporter, quality/timing statistics and a gated campaign runner. The [execution supplement](../docs/experiments/model-execution-v1.md) records its operating decisions. Full pretrained-model parity and the measured campaign remain outstanding in [issue #5](https://github.com/Whyme-Labs/hadamard-exposition/issues/5).

## Model runner and launch qualification

Use separate converter and runtime environments. The complete [wheel lock](model-dependencies-v1.json) and the [converter](locks/converter-requirements.txt)/[runtime](locks/runtime-requirements.txt) install lists retain exact sources and SHA256 hashes. Install each list in a fresh CPython 3.12.14 environment with `pip --require-hashes --no-deps --only-binary=:all:`. The runtime environment must invoke the parent command; the runner probes both actual installed closures and their ABI compatibility before acquisition.

```bash
build/model-runtime-venv/bin/python benchmarks/run_model.py preflight \
  --output build/model-preflight-001

build/model-runtime-venv/bin/python benchmarks/run_model.py run \
  --output build/model-campaign-001 \
  --converter-python build/model-converter-venv/bin/python \
  --runtime-python build/model-runtime-venv/bin/python \
  --dependency-lock benchmarks/model-dependencies-v1.json \
  --review validation/2026-10-17-model-campaign/review.json
```

Every attempt requires a fresh output path. The command refuses a failed host gate before downloading files or starting a model worker. A source review, artifact/role identities, all six development parity checks and one conservative cost proof must pass before an immutable execution lock permits quality evaluation. The 6 GiB conservative available-memory requirement, 4 GiB cache/output limit and 600/600/600-second phase budgets are unchanged.

The [implementation and launch evidence](../validation/2026-10-17-model-campaign/README.md) distinguish installed dependencies and generated-model conformance from actual Pythia results. The real pinned Torch/Transformers export probe checks six variants, dynamic/cache paths and independent numerical references on a small untrained GPTNeoX. Its result does not substitute for the two-article pretrained development gate.

## Reproduce the local qualification

Use Python 3.12.14 in an isolated environment and install the pinned CPU dependencies from the repository root:

```bash
python3 -m venv .venv-benchmark
. .venv-benchmark/bin/activate
python3 -m pip install -r requirements-benchmark.txt
python3 benchmarks/qualify.py --output build/benchmark-qualification-v1
```

The qualifier uses one CPU/BLAS thread, a 180-second subprocess deadline and a sampled 1 GiB worker-RSS ceiling. It reads no pretrained model or dataset and makes no network requests. Use a new output path for a later run; the command refuses to overwrite an existing observation.

For this workspace's temporary dependency installation, the equivalent invocation is:

```bash
PYTHONPATH=build/benchmark-deps python3 benchmarks/qualify.py --output build/benchmark-qualification-v1
```

The output contains the receipt, child-process output and the ONNX controls' generated graphs, runtime logs and CPU profiles. The receipt records environment observations, source hashes, tests, numerical errors and incomplete model-launch prerequisites. A passing `design_qualified` field establishes local design and generated-input conformance. `campaign_ready` remains false for this source revision.

The [retained evidence](../validation/2026-10-17-model-benchmark/README.md) includes the accepted run and both earlier resource-check corrections. The accepted run passed 38 tests and 20 controls with valid worker RSS sampling. Its original receipt and runtime profiles remain available for inspection.

All offline benchmark tests can be run without the full-shape retained sweep:

```bash
python3 -m unittest discover -s benchmarks -p 'test_*.py' -v
```

The original exposition has its own independent validation command:

```bash
python3 scripts/validate.py
```

## Evidence boundaries

`contract.py` validates prespecified inputs and computes data/loss primitives. `onnx_controls.py` constructs real CPU graphs and compares their packed behavior with independent scalar/float64 references. `qualify.py` binds the run to source bytes and enforces its outer resource controls.

Generated graph/profile timestamps and measured elapsed time are observations, so their artifact hashes can change across runs. Deterministic input generation, packed bytes, graph construction, tolerances and invariants must still match the fixed source. Reproduction creates a new receipt rather than asserting byte identity of timing observations.

The full-model adapter preserves batch/sequence shape, attention, normalization, residuals, cache and tokenizer behavior, then requires the protocol's development-only parity and resource checks before test evaluation. The implementation remains subject to those actual full-model checks. Packed payload arithmetic and successful generated controls do not establish model quality or inference savings.
