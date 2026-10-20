# Research context

This repository studies the effect of an orthogonal Hadamard change of basis on quantization error. The deliverables are an illustrated article, exact mathematical checks, a small synthetic reference experiment, and prespecified follow-up experiments.

The reference workload uses 512 activation rows, 128 input features, 64 output features, four-bit symmetric maxabs quantization and 20 paired seeds. Each activation row and weight output column initially shares a scale across all 128 input features. The original script and results remain the reference evidence.

The first follow-up varies the quantization group size while preserving the full-width transform. Its frozen design is in `docs/experiments/group-size-v1.md`. Every result uses relative squared Frobenius output error against the same full-precision linear product. A rotation win means lower error within a matched seed and group size.

The reference and group-size studies are error simulations in float64. The next design, `docs/experiments/model-benchmark-v1.md`, defines a matched six-arm Pythia-70M CPU benchmark. It targets four-bit weights with float32 activations in the six post-GELU MLP output projections. Its generated-input ONNX qualification checks actual packed-format execution, legal rotation placement and loss/data helpers. It measures no pretrained-model quality or inference improvement. Full-model acquisition, export parity and resource feasibility remain prerequisites for a later execution revision.

Issue #5 implements the pinned acquisition, complete GPTNeoX exporter, quality/timing runner and launch gates. `docs/experiments/model-execution-v1.md` records its execution decisions without changing the frozen design. Both isolated dependency closures and a small generated six-arm GPTNeoX export/cache probe pass. The 6 GiB conservative available-memory gate blocks the current host before pretrained acquisition or model evaluation. No complete pretrained campaign or quality/cost result is claimed; retain that blocker and every rejected attempt alongside the accepted implementation checks.

The power-of-two Hadamard construction is known mathematics. No claim of solving the general Hadamard conjecture or receiving a prize follows from these experiments.

Use GitHub issues and pull requests for work tracking. Read `docs/agents/issue-tracker.md` and `docs/agents/domain.md` for the repository conventions. Run the documented validation command before proposing changes. Preserve old results and negative outcomes, label exploratory follow-ups, and bind receipts to source and protocol hashes.

The related Lean execution qualification remains owned by autoresearch-harness issue #175 and PR #176. It is a separate runtime integration task.
