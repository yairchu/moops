# Agent Instructions

## Tests

Only add or change tests when they document a bug or surprising behavior discovered while working on the task.

Do not add tests just to prove straightforward wrapper behavior, mirror an existing test for a nearly identical control, or satisfy a generic expectation that every change needs a test. Prefer using existing tests and examples for routine coverage.

When adding a test for a newly discovered bug, keep it focused on the observed failure. If the fix is not ready, mark the test `xfail` with a reason that explains the current limitation.
