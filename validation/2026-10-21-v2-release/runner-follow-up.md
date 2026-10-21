# Automatic workflow follow-up

The locally validated archive completed at 2026-10-21T02:58:40.935099Z. Its milestone and receipt report the execution surface for that acceptance run: the assistant environment. No runner supplied any of its 49 package files or acceptance results.

A later push of commit `efc9f2d7896f0fbf66d38d4dbdc8e5ab1a7ed53c` to PR 14 unexpectedly triggered the pre-existing pull-request retention workflow. Run `39536817779`, titled `Retain v2 reproduction evidence`, completed successfully on the workflow configured for Blacksmith. It is a redundant, separate hosted reproduction and must not be substituted for the local release receipt. The legacy home-runner workflow also queued run `39536825246`. Its result is not used for this milestone.

The prior README and PR wording saying that this continuation used no runner should be read as scoped to the reported local release validation, not all automatic side effects after the later push. This note records the distinction rather than hiding the hosted run.

Both retention/build workflows are now manual-only. The v2 workflow selects the self-hosted Linux X64 runner and verifies `RUNNER_NAME=home-ci-01`. It no longer automatically selects Blacksmith. A last-resort Blacksmith execution must be a separate deliberate action with a documented local and home-runner blocker.

This is a workflow-policy correction. The accepted local archive, mathematical statements, empirical protocol, raw observations and test results are unchanged.
