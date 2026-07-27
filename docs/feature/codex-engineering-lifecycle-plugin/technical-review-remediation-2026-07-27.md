# Technical Review Remediation: Codex Engineering Lifecycle Plugin

- Date: 2026-07-27
- Source review: `technical-review-2026-07-27.md`
- Remediated artifacts: `design.md`, `implementation-plan.md`
- Status: Ready for re-review

| Finding | Resolution |
| --- | --- |
| TR-1 — completed Goal cannot resume | Replaced the singular Goal record with ordered immutable `GoalRun` entries. Initial implementation and every code-remediation cycle create distinct deterministic runs; only one may be active globally. |
| TR-2 — composition skills implicitly invocable | Kept `SKILL.md` and runtime resources byte-identical while adding `policy.allow_implicit_invocation: false` to packaged agent metadata. Role wrappers invoke them explicitly and runtime task-ID guards remain authoritative. |
| TR-3 — untyped release targets | Added typed GitHub Release and PyPI targets, mandatory artifact digests, exact per-target results, partial-failure state, and an all-authorized-targets-success closure invariant. |
| TR-4 — review branch retry ambiguity | Added create-if-absent, exact state-recorded proof reuse, wrong-base/tip/report conflict rejection, persist-before-delivery, and no-force-push rules. |

The diagrams, field matrices, failure table, concurrency rules, test strategy,
skill contracts, and implementation slices now reflect the remediated model.
