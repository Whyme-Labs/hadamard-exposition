# Specification review

**PASS** for the proposed single own-file cache advisory pass and its subsequent unchanged campaign gates. No material specification defect found.

Reviewed `validation/2026-10-18-campaign-development/plan.md`, the retained preflight, and `sources/release-owned-cache.py` against baseline `1b501f564750d0938adbe0ece3314dc0960bbc26`, the frozen execution protocol, and issue #6.

The reviewed helper SHA256 is:

`f277b0b7fcc5cfdceb11f5cf6a872d36b4609386098dd05f5c32a411e1f91091`

The helper implements the plan's three fixed repository-relative roots. It opens qualifying files read-only, requires current-user ownership and a single hard link, rejects unexpected file types, skips symlinks, and traverses through directory descriptors. It hashes each opened file before advice and checks its identity before and afterward. The existing campaign process lock excludes cooperating campaign execution.

The operation has a 120-second deadline and a 512 MiB address-space ceiling. The reviewed source contains no input-data write, deletion, network operation, global cache control, cgroup modification, global synchronization, or deliberate memory-pressure allocation. It preserves completed journal entries when an operation fails.

The plan correctly treats accepted advice as an advisory outcome. It does not equate logical file sizes with resident memory, attribute every page to this cgroup, or guarantee reclamation. It also acknowledges that prepared dependencies can reload during subsequent execution.

The unchanged preflight remains the acceptance gate. Its current observation is 5,222,633,472 available bytes against the frozen 6,442,450,944-byte requirement. The plan preserves the memory formula, CPU requirements, dependency identities, model review, six arms, numerical controls, acquisition allowance, and campaign deadlines. It requires full-model parity, a passing development cost proof, and the immutable execution lock before quality evaluation.

This review accepts the concrete maintenance procedure, not a successful memory qualification or pretrained result. A failed maintenance pass or subsequent gate must retain its original evidence and stop the planned sequence.

This was a read-only review. I did not execute the helper, change files, install packages, download model or dataset inputs, or run numerical tests.
