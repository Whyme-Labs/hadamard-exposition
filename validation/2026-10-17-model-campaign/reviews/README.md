# Independent review history

The reviews distinguish implementation acceptance from the still-blocked pretrained campaign. The two axes were assigned to separate agents, independently of the implementation authors. They are agent reviews, not external academic peer review.

| Stage | Source snapshot | Specification | Standards |
|---|---|---|---|
| Initial full implementation review | Published commit `bdb27ea4ae520d9da0ccece06a8a2665b56577b1` | [PASS for bounded scope](initial-specification.md) | [BLOCK: failure receipt and cleanup](initial-standards.md) |
| Incremental correction and evidence review | Published commit `8237ea186603b1b34aadbfdc9133bd956db41c05` | [PASS for bounded scope](final-specification.md) | [PASS; original finding resolved](final-standards.md) |

The initial review named local commit `9d1d5b1089055b623b918113f74153649b78cef9`. Its tree `176d41898e21b9bc1d28b39e34aa37e89e6afbd3` is exactly the published initial tree. This mapping preserves the original review identity after the source and evidence package were restored into a separate checkout.

The final reviewed source tree is `00a7e6b0914a8e8cd46a010a121dc430318e09ae`. The overall PR base remains `a38ea0445fab7702392a963b91a6602a8b780f97`; the frozen protocol and manifest did not change. The final source map has 30 entries and SHA256 `1dd75e9af0736795e4d83c26f866d15d9f7a3fe55003e399ddbd36951ab2d69e`, using UTF-8 JSON with sorted keys, compact separators and no terminal newline.

[review.json](../review.json) is the machine-readable source and review binding. The two final reports were copied unchanged from the reviewers' standalone output and hashed. The [publication check](publication-binding-check.json) verifies the reports and uses the production validator to check that the reviewed commit/tree contains all current bound sources. The documentation commit adding this packet does not change a bound implementation or protocol file.

## Scope and remaining work

The original failure-path finding remains visible and associated with its original source. The correction independently records unavailable final source/disk observations, retains the original failure, fails closed and guarantees lock cleanup. Seven real-function/atomic-publication/lock regressions passed under their separate low-memory allowance. Neither reviewer reran the tests or imported numerical/model packages during the incremental recheck.

No pretrained campaign acceptance follows. A qualified host with both exact environments, actual pinned acquisition, all six complete Pythia graphs, full reference/rotation/cached development parity, actual disjoint role identities, a bounded feasibility proof and execution lock, and all prescribed quality/cost outcomes remain required by issue #5. Issue #6 tracks the execution prerequisite.
