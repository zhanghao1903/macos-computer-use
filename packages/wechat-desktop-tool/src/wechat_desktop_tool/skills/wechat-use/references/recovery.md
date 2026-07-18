# WeChat Failure And Recovery

Use structured `status`, `error.failureKind`, operation evidence, and mutation
phase fields together. Do not decide from free-text summaries alone.

## Recovery Matrix

| Condition | Required response | Automatic retry |
| --- | --- | --- |
| `contact_ambiguous` | Present safe candidates when available or ask for a more precise contact. | No unchanged retry. |
| `contact_not_found` | Report no verified match and ask for a corrected name. | No unchanged retry. |
| `wechat_not_ready` | Explain that WeChat could not be verified as ready. | Only after foreground/configuration state changes. |
| `wechat_not_logged_in` | Ask the user to log in manually. | Only after login. |
| Missing Accessibility permission | Identify the application/helper that needs permission. | Only after permission changes. |
| Read timeout or read transport failure | Report unavailable or partial data. | One bounded read-only retry when application policy permits. |
| `wechat_query_truncated` | Report partial visible data and reduce the requested scope. | Optional bounded read-only retry. |
| Invalid input or unsupported operation | Correct the call using the registered schema. | Never retry unchanged input. |
| Deterministic pre-submit failure | Report that no verified send completed. | Retry only with explicit evidence that no submit was attempted and authorization remains valid. |
| `submit_unknown` | Require the user to inspect WeChat manually. | Never. |
| `send_unverified` | State that a send was attempted but could not be verified. | Never. |
| `status=unknown` after any mutation | Require manual inspection. | Never. |
| Transport loss after a possible submit | Treat the outcome as unknown. | Never. |

## Determine Whether A Mutation May Have Happened

Treat the operation as possibly completed when any of these conditions holds:

- `status` is `unknown`;
- `error.failureKind` is `submit_unknown` or `send_unverified`;
- `sendAttempted` is true;
- `failedPhase` is `submit_draft` and the result does not prove the submit was
  rejected before execution;
- the transport disconnected or timed out after submission began;
- structured evidence is missing or contradictory.

When a mutation may have happened:

1. Do not call `submit_draft` or `send_message` again.
2. Tell the user the result is uncertain rather than failed.
3. Ask the user to inspect the target chat manually.
4. Resume only from newly observed state and a new explicit instruction.

Do not use `error.retryable=true` as authority to replay a mutation. Generic
transport retry hints cannot establish that a message was not submitted.

## Safe Read Recovery

Read-only operations may be retried conservatively when the application permits
it:

1. keep the same exact target;
2. keep or reduce the requested limit;
3. perform at most one immediate retry;
4. report truncation or partial data;
5. stop when readiness, login, permission, or target verification is missing.

Do not convert a read recovery into a coordinate click or raw Accessibility
query. Use only registered semantic WeChat operations.

## Clarification And Confirmation

Ask for clarification when the contact, message content, or requested action is
missing or materially uncertain. Preserve the user's exact text in the eventual
tool call.

Before sending, use the embedding application's confirmation mechanism. A
previous confirmation no longer applies when the target or message changes.
The skill text itself does not authorize a send.

## Reporting Templates

For an ambiguous contact:

```text
I found multiple verified matches for that contact. Which one should I open?
```

For an unknown send outcome:

```text
The send was attempted, but the result could not be verified. Check the target
chat in WeChat before asking me to send again.
```

For visible-message limits:

```text
These are the messages currently visible and loaded in WeChat, not a complete
chat-history export.
```
