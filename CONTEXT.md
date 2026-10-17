# Research context

This repository studies the effect of an orthogonal Hadamard change of basis on quantization error. The deliverables are an illustrated article, exact mathematical checks, a small synthetic reference experiment, and prespecified follow-up experiments.

The reference workload uses 512 activation rows, 128 input features, 64 output features, four-bit symmetric maxabs quantization and 20 paired seeds. Each activation row and weight output column initially shares a scale across all 128 input features. The original script and results remain the reference evidence.

The first follow-up varies the quantization group size while preserving the full-width transform. Its frozen design is in `docs/experiments/group-size-v1.md`. Every result uses relative squared Frobenius output error against the same full-precision linear product. A rotation win means lower error within a matched seed and group size.

The work is an error simulation in float64. It measures no language model accuracy, packed integer memory consumption or hardware throughput. The power-of-two Hadamard construction is known mathematics. No claim of solving the general Hadamard conjecture or receiving a prize follows from these experiments.

Use GitHub issues and pull requests for work tracking. Read `docs/agents/issue-tracker.md` and `docs/agents/domain.md` for the repository conventions. Run the documented validation command before proposing changes. Preserve old results and negative outcomes, label exploratory follow-ups, and bind receipts to source and protocol hashes.

The related Lean execution qualification remains owned by autoresearch-harness issue #175 and PR #176. It is a separate runtime integration task.
