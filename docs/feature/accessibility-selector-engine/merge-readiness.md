# Accessibility Selector Engine Merge Record

- Updated: 2026-07-18
- Feature branch: `codex/accessibility-selector-engine`
- Pull request: https://github.com/zhanghao1903/macos-computer-use/pull/3
- Merged at: `2026-07-17T18:35:35Z`
- Merged feature head: `31404a933f29ef9a50d671a0fe2a5d75a3a36b5d`
- Squash merge on `main`: `44e90e817d4db51e0a7fcab71927ad85dc1b7646`
- Latest authoritative review:
  [`pr-review-macos-computer-use-3-31404a9.md`](./pr-review-macos-computer-use-3-31404a9.md)
- Review decision: `REQUEST_CHANGES`
- Merge disposition: maintainer-directed risk acceptance

## Merge Outcome

PR #3 was merged after the maintainer explicitly accepted four open findings.
The merge does not resolve, waive, or invalidate the review evidence. The
squash commit tree matches the reviewed feature head and its message records
the same follow-up finding ids.

GitHub Actions `CI / test` passed on the feature head and on squash merge
`44e90e8`. The configured tests do not include the independent counterexamples
that keep the following findings open:

| Finding | Accepted residual risk | Release mitigation |
| --- | --- | --- |
| `PRR-039` | Contradictory query completeness aliases can authorize a later WeChat mutation. | Treat any observed completeness inconsistency as terminal and keep unattended submission disabled. |
| `PRR-042` | Duplicate, outer, or nested query evidence can resolve and cache despite a contradiction. | Use only the bundled first-party backend and do not accept externally constructed query responses. |
| `PRR-043` | Partial names, hidden duplicates, malformed paths, or wrong provenance can reach contact mutation and send. | Require application-level recipient confirmation; do not submit to ambiguous or partial contact names. |
| `PRR-044` | Malformed roots and ineffective or unknown matchers can broaden an override profile. | Load only trusted, application-owned static profile files. |

## Lifecycle Status

- F0-F5 implementation and verification: complete for the merged internal MVP.
- F6 review: completed with `REQUEST_CHANGES`; merge proceeded by explicit
  maintainer risk acceptance.
- F7 release preparation: active for coordinated package version `0.2.0`.
- F8 post-release traceability: pending publication.

The release must preserve these findings as known issues, attach strict release
proof, and must not describe the findings as fixed. Follow-up remediation will
use a separate branch after the release unless the maintainer reprioritizes it.
