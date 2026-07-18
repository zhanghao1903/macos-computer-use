# PyPI Token Publishing Verification

## Lifecycle Status

| Field | Value |
| --- | --- |
| Feature | PyPI API-token publishing mode |
| Phase | F5 verification, examples, and documentation |
| Branch | `codex/release-token-publishing` |
| Implementation commit | `b0138ae` |
| Verification date | 2026-07-19 |
| Production publication | Not performed |

## Documentation Verification

Updated stable maintainer documentation:

- `docs/publishing.md` now defines the active GitHub Secret token flow,
  sanitized report schema, exact-one authentication mode, strict commands,
  release assets, failure boundary, and Trusted Publisher migration path.
- `docs/release-checklist.md` now uses `PYPI_API_TOKEN`, `pypi-auth.json`,
  `pypi_publish_auth`, and the token-mode workflow sequence.

No package-consumer example was added because this feature has no runtime API,
command, observation, configuration, or package behavior surface. The relevant
consumer is the repository maintainer, and the executable examples are the
publishing and checklist commands above.

## Automated Evidence

### Focused Release Tests

Command:

```bash
python -m unittest tests.test_release_preflight
```

Result:

- `108` tests passed;
- report producer, strict loader, malformed/mismatched input, boolean-type
  checks, unknown-field rejection, dual-mode ambiguity, proof bundle,
  compatibility, workflow, and developer-check contracts were covered.

### Unified Repository Gate

Command:

```bash
python scripts/dev_check.py
```

Result:

| Check | Result |
| --- | --- |
| Root repository suite | `145` passed |
| `app-control-protocol` suite | `55` passed |
| `computer-use-macos` suite | `168` passed, `1` skipped |
| `wechat-desktop-tool` suite | `172` passed |
| Local release preflight | Passed |

The skipped `computer-use-macos` test and preflight warning both reflect the
current restricted environment's inability to bind the Unix socket used by the
local-service smoke. No token-publishing behavior depends on that socket.

### Static And Syntax Checks

Commands:

```bash
python -m py_compile \
  scripts/pypi_auth_report.py \
  scripts/release_preflight.py \
  scripts/release_proof_bundle.py \
  scripts/dev_check.py \
  tests/test_release_preflight.py
git diff --check
```

Result: passed.

The release preflight also validated all JSON examples in the updated
publishing documents and confirmed that the workflow:

- omits unused OIDC permission;
- checks the expected GitHub Secret before publication;
- downloads `pypi-auth.json`;
- runs strict external proof with `--pypi-auth-report`;
- supplies the token username and encrypted secret to the official action.

## Security Verification

- The report generator has no token, token-file, arbitrary secret-name, or
  arbitrary target argument.
- Tests reject added credential/publisher fields and integer `1` in place of
  JSON boolean `true`.
- Strict mode resets aggregate authentication proof before loading a detailed
  report.
- Token and Trusted Publisher reports cannot coexist in preflight or bundling.
- The workflow contains no plaintext credential, `.pypirc` fallback, workflow
  token input, or `id-token: write` permission.
- The feature branch contains no generated auth report, local proof bundle,
  distribution, or credential file.

## External Evidence Status

The following are intentionally not claimed by F5:

| Evidence | Status | Required next action |
| --- | --- | --- |
| GitHub `PYPI_API_TOKEN` secret metadata | Pending | Configure through stdin and verify only the secret name after merge readiness. |
| Sanitized production `pypi-auth.json` | Pending | Generate after the repository secret is confirmed. |
| Pull request CI | Pending | Open the F6 PR and require green checks. |
| Final-source selector-engine proof | Pending | Regenerate against the final merged/tagged SHA. |
| Complete strict proof bundle | Pending | Rebuild with the final selector proof and token-auth report. |
| Production PyPI upload/install | Pending | Perform only in F7 after merge and all strict gates pass. |

Existing TestPyPI and desktop evidence tied to
`1b2c9a53abde68fe1373a7fff21fbb2e87950280` remains useful candidate evidence,
but it is not relabeled as final proof for the post-merge source SHA.

## F5 Decision

The implementation and stable documentation satisfy local verification. The
feature can enter F6 review and merge readiness. Production publication remains
blocked on the explicit external evidence listed above.
