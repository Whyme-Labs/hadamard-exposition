# Research context

This repository studies the effect of an orthogonal Hadamard change of basis on quantization error. The deliverables are an illustrated article, exact mathematical checks, a small synthetic reference experiment, and prespecified follow-up experiments.

The reference workload uses 512 activation rows, 128 input features, 64 output features, four-bit symmetric maxabs quantization and 20 paired seeds. Each activation row and weight output column initially shares a scale across all 128 input features. The original script and results remain the reference evidence.

The first follow-up varies the quantization group size while preserving the full-width transform. Its frozen design is in `docs/experiments/group-size-v1.md`. Every result uses relative squared Frobenius output error against the same full-precision linear product. A rotation win means lower error within a matched seed and group size.

The reference and group-size studies are error simulations in float64. The model design, `docs/experiments/model-benchmark-v1.md`, defines a matched six-arm Pythia-70M CPU benchmark. It targets four-bit weights with float32 activations in the six post-GELU MLP output projections. Its generated-input ONNX qualification checks actual packed-format execution, legal rotation placement and loss/data helpers. It measures no pretrained-model quality or inference improvement. Full-model development parity and resource feasibility remain prerequisites for the quality/timing campaign.

Issue #5 implements the pinned acquisition, complete GPTNeoX exporter, quality/timing runner and launch gates. `docs/experiments/model-execution-v1.md` records its execution decisions without changing the frozen design. Both isolated dependency closures and a small generated six-arm GPTNeoX export/cache probe pass.

The 18 October pretrained milestone is retained in `validation/2026-10-18-campaign-development/README.md`. Fresh host preflights passed the unchanged 6 GiB conservative available-memory requirement; all eight pinned inputs were acquired and all six graphs were exported and structurally checked. Issue #6 is closed as historical host/environment qualification. Every future launch still requires a fresh preflight. The pretrained campaign remains blocked by the unmodified reference model's own full-versus-cached absolute logit control, before ONNX development parity, cost proof, execution lock, quality evaluation or timing.

The separately reviewed version-2 diagnostic completed exactly six reference forwards and reproduced all six original recorded logit identities, all original cache identities and the preserved arrays. Its first numerical divergence in both development articles is the first attention QKV output, despite byte-identical last-token inputs under different call shapes. Shape-dependent FP32 linear evaluation is the leading explanation for this first divergence; no internal kernel or accumulation order has been identified. Earlier masks are numerically equivalent with different zero signs, so do not call all preceding bytes identical. Other linear operations also differ; the first QKV operation alone has not been shown to cause all later logit error.

The diagnostic's original acquisition verification is historical: a later unreferenced partial exists outside its consumed-model input map. Preserve the raw inventory and its append-only omission clarification, which distinguishes observed bytes from pinned input provenance. No complete pretrained campaign or quality/cost result is claimed. Issue #5 stays open; the next experiment needs a separate preregistration. Preserve the unchanged gates and every rejected attempt alongside accepted implementation and diagnostic checks.

The power-of-two Hadamard construction is known mathematics. No claim of solving the general Hadamard conjecture or receiving a prize follows from these experiments.

Use GitHub issues and pull requests for work tracking. Read `docs/agents/issue-tracker.md` and `docs/agents/domain.md` for the repository conventions. Run the documented validation command before proposing changes. Preserve old results and negative outcomes, label exploratory follow-ups, and bind receipts to source and protocol hashes.

The related Lean execution qualification remains owned by autoresearch-harness issue #175 and PR #176. It is a separate runtime integration task.
