# Initial independent Standards review — BLOCK

Reviewer: `/root/campaign_standards_review`, an independent agent. This report records the original review before the correction; its blocking verdict is not retroactively replaced by a later pass.

- Base: `a38ea0445fab7702392a963b91a6602a8b780f97`
- Original local head: `9d1d5b1089055b623b918113f74153649b78cef9`
- Reviewed tree: `176d41898e21b9bc1d28b39e34aa37e89e6afbd3`
- Published commit with exactly that tree: `bdb27ea4ae520d9da0ccece06a8a2665b56577b1`

## Finding

**P2 — Finalization can suppress the failed campaign receipt.** In `benchmarks/run_model.py:610–612` of the reviewed snapshot, the `finally` block repeats source hashing and directory accounting without protecting either operation. If `directory_bytes()` already failed during execution—for example, its explicit symlink or I/O refusal—the repeated call raises before `campaign.json` is published at line 625 and before explicit process-lock cleanup at lines 626–627.

A read-only evaluation of the exact `run_campaign` function with in-memory dependencies reproduced this: directory accounting failed twice, only `preflight.json` was retained, and neither explicit unlock nor close was reached. No filesystem writes, workers, numerical imports, or network calls occurred.

**Required correction:** Preserve the original exception, record unavailable final observations as unavailable, and put lock release/close in an unconditional nested `finally`. This follows the failure-preservation requirements in `CONTEXT.md:15` and `docs/agents/issue-tracker.md:5`, and the retained-failure behavior documented in `docs/experiments/model-execution-v1.md:64`.

**Nonblocking navigation defect:** `validation/2026-10-17-model-campaign/dependencies/README.md:5` has three lock links beginning `../../../../benchmarks/`; each needs `../../../benchmarks/`.

## Source and evidence identity

All **29 bound source files** matched the reviewed head. Source-map SHA256: `662f2aab49de288a45b898ab8eb5a6793cbdd770bf51c14c97cb521cf9836efd`, using UTF-8 JSON with sorted keys, compact separators and no terminal newline. `run_model.py` SHA256: `1aa4792430599d5df6203e758e387b218db3be1fde6e656458203498138f1010`.

The reviewer checked the pinned diff, required repository standards, production-module boundaries and failure paths, and relevant tests. The delegated evidence review verified all **58 archived members**, all **25 contemporaneous probe source bindings**, and preserved rejected outcomes. No other blocking maintainability or evidence-integrity finding emerged.

## Limits

This is a standards review, not campaign acceptance. No heavy tests or model/network operations ran. The full pretrained campaign and full current-source suite remain subject to the disclosed memory blockers from their respective attempts. These are agent reviews, not external academic peer review.
