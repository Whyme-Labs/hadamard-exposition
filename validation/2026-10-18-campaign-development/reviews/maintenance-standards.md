# Standards review

**PASS** for the proposed pre-execution cache-maintenance helper. No material Standards defect found.

Reviewed the uncommitted candidate on `work/issue6-campaign-development` against base `1b501f564750d0938adbe0ece3314dc0960bbc26`.

Helper SHA256:

`f277b0b7fcc5cfdceb11f5cf6a872d36b4609386098dd05f5c32a411e1f91091`

Plan SHA256:

`05b5c10d0ffd141232a313f8f5d5bdd0ac2550b67e5abfb9cf6bcdcbe08d9d0d`

Preflight SHA256:

`cdacad612016f904b841f09a6bfe01b64031f9dddf20adad9cd3628a65e4629c`

## Findings

The helper keeps a narrow, cohesive responsibility. Its three fixed roots match the documented maintenance scope. Directory descriptors anchor traversal. It skips symlinks, opens files read-only without following links, rejects unexpected file types, ownership and link counts, and compares descriptor identities before hashing and after advice.

The implementation applies a 120-second deadline through monotonic checks and an alarm, plus a 512 MiB address-space limit. It uses the existing campaign lock with a nonblocking exclusive acquisition. It contains no deletion, target-data write, network operation, pressure allocation or global memory-control operation.

Per-file hashes precede advisory calls. Metadata checks follow them without rereading file contents. Per-file records include caught failures, and the final record binds the journal and helper hashes. Final source changes or deadline expiry prevent completed status.

All benchmark and experiment sources remain unchanged. The retained preflight still reports the original memory blocker. The plan correctly distinguishes accepted advice from actual reclamation and requires a fresh unchanged preflight before campaign execution.

## Boundaries

This review assumes the documented single maintenance worker and no noncooperating writer inside the prepared trees. A cooperative lock does not prevent arbitrary external filesystem changes. Abrupt execution-service loss can interrupt journal finalization, so an incomplete receipt must remain incomplete.

The helper's own logs and lock are expected evidence writes. Its zero target-data-write claim applies to the advised files. No result establishes reclaimed bytes or campaign feasibility until execution produces the corresponding observations.

This was a read-only review. I ran no helper, cache hints, tests, installations, downloads or model evaluations.
