# Own-file cache maintenance before the frozen campaign

Date: 18 October 2026. Tracks [issue #6](https://github.com/Whyme-Labs/hadamard-exposition/issues/6) and [issue #5](https://github.com/Whyme-Labs/hadamard-exposition/issues/5). Baseline is commit `1b501f564750d0938adbe0ece3314dc0960bbc26`.

## Decision before execution

The [fresh unchanged preflight](preflight-before-cache/preflight.json) reports 5,222,633,472 conservative available bytes against 6,442,450,944 required bytes. Runtime, CPU and disk checks pass. No model or dataset has been acquired.

The two installation-cache trees contain 938,358,380 logical bytes. Their data footprint alone cannot close the 1,219,817,472-byte gap. The two prepared environments add 1,749,284,440 logical bytes and must remain intact. Their counts and sizes match the [accepted restoration](../2026-10-18-environment-recovery/dependencies/qualification.json). Its [archive inventory](../2026-10-18-environment-recovery/dependencies/inventory.json) identifies the installation caches as regenerable omissions and retains receipts separately.

Make one bounded advisory pass over these exact repository-relative roots:

- `build/environment-recovery-002/pip-cache`
- `build/environment-recovery-002/pip-temporary`
- `build/recovered-envs-002`

The [helper](sources/release-owned-cache.py) opens single-link, current-user-owned regular files read-only. It anchors traversal to directory descriptors, skips symlinks and checks each opened file's identity before hashing and after the advisory call. It records per-file content hashes before the hint and metadata afterward. The repository's existing campaign lock excludes concurrent cooperating model work.

The pass has a 120-second deadline and a 512 MiB address-space ceiling. It performs no file deletion, data modification, network access, global synchronization, global cache control, cgroup write or memory-pressure allocation. Every attempted regular file receives a journal entry. An error stops the pass and preserves completed entries. This is resource maintenance, not a numerical qualification.

## Why this can help

POSIX requires file advice to preserve data-operation semantics while allowing performance changes. Linux describes `POSIX_FADV_DONTNEED` as a nonbinding attempt to release the indicated file's cached pages. Dirty and partial pages may remain. A successful call therefore means that the kernel accepted advice, not that it released any particular number of bytes. Sources: [POSIX semantics](https://man7.org/linux/man-pages/man3/posix_fadvise.3p.html) and [Linux behavior](https://man7.org/linux/man-pages/man2/posix_fadvise.2.html).

The [kernel memory-ownership documentation](https://docs.kernel.org/admin-guide/cgroup-v2.html#memory-ownership) discusses using this advice to relinquish cached-file memory. File ownership, residency and cgroup charge are distinct. The inventory cannot attribute every page to this cgroup or establish which pages are active.

Under the frozen formula, releasing clean inactive cache can reduce both charged memory and credited inactive cache by the same amount. Releasing clean active cache can increase the conservative availability estimate. The actual before/after observations determine whether this attempt helps. Hashing after the final hint would load the same files again, so the helper performs its content hash before the hint and records metadata-only identity checks afterward.

## Subsequent execution gate

After the single pass, retain one fresh receipt from the unchanged `benchmarks/run_model.py preflight`. The existing 6 GiB memory requirement and every other experiment requirement remain unchanged. A passing preflight permits the existing reviewed campaign command to attempt acquisition, all six full-model development parity checks and the bounded development cost proof. Only its immutable execution lock permits quality evaluation.

Use the restored runtime and converter interpreters, the frozen dependency lock, and `validation/2026-10-17-model-campaign/review.json`. The recovery review has a different schema and does not replace the model-source review. The campaign itself rechecks both complete installed closures and generated ABI probes before acquisition.

If any gate fails, retain its original receipts and stop at that gate. The maintenance result cannot substitute for a successful preflight, full-model parity or feasibility proof. Dependencies may reload during the real campaign, and the campaign's second host gate and all resource guards still apply.
