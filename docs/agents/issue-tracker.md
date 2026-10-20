# Issue tracking

Use https://github.com/Whyme-Labs/hadamard-exposition/issues as the task tracker. Issue #1 owns the completed exposition/group-size implementation in PR #3. Issue #2 owns the matched model-benchmark design and generated-input qualification in PR #4. Issue #5 owns pretrained-model acquisition, export, launch qualification and measurement. Its implementation can be reviewed while full campaign acceptance remains blocked; preserve the distinction in every update. The user explicitly selected the GitHub connector for hosted operations.

Record an experiment's protocol before running it. Keep that protocol stable, then add dated result comments and source identities to its issue. A follow-up design gets a new protocol version or issue. Preserve failures and do not relabel an earlier source receipt as acceptance of a later revision.

Use scoped branches and reviewable PRs. Link a PR to its owning issue and record validation and independent review there. Keep existing user content and unrelated changes intact. Do not close an issue solely because implementation files exist; compare the result with its stated acceptance criteria.

The repository has no custom triage vocabulary. Use ordinary issue state and explicit blocker links. Do not introduce labels merely to emulate a larger engineering project.

## Execution order

The user requires this order for experiments, tests, and builds:

1. Run in the assistant's current local environment first. Check installed dependencies and available resources, retrieve required source and data through the connected tools when needed, and verify their identities. Restricted shell networking alone does not establish that local execution is impossible.
2. If the specific workload cannot run locally, use the home CI runner in GitHub Actions. Check its actual availability and labels rather than assuming them.
3. Use Blacksmith runners in GitHub Actions only as the last resort after the local and home-runner paths are unsuitable or have failed.

Record the concrete blocker and execution evidence before escalating. Keep local computation, source retrieval, hosted CI, repository creation, and public publication as separate capabilities. Do not hand an executable local task back to the user because a hosted runner failed.

Distinguish an independently reimplemented numerical check from execution of the unmodified repository validation and release builder. Same-seed reproduction checks implementation consistency; it is not a new-data confirmation, a pretrained-model result, or acceptance of the complete public release.
