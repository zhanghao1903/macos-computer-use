# Release Checklist

Use this checklist before publishing the app-control tool package suite.

## Local Verification

- [ ] New developer quickstart has been exercised or reviewed:
      [quickstart.md](quickstart.md).
- [ ] Unified local developer check:
      ```bash
      python scripts/dev_check.py
      ```
- [ ] Root tests:
      ```bash
      PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
        python -m unittest discover -s tests
      ```
- [ ] Cross-package success-standard contract:
      ```bash
      PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
        python -m unittest tests.test_project_contract
      ```
- [ ] Protocol tests:
      ```bash
      PYTHONPATH=packages/app-control-protocol/src \
        python -m unittest discover -s packages/app-control-protocol/tests
      ```
- [ ] `computer-use-macos` tests:
      ```bash
      PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
        python -m unittest discover -s packages/computer-use-macos/tests
      ```
- [ ] `wechat-desktop-tool` tests:
      ```bash
      PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
        python -m unittest discover -s packages/wechat-desktop-tool/tests
      ```
- [ ] `python -m pip wheel --no-build-isolation --no-deps packages/app-control-protocol -w dist`
- [ ] `python -m pip wheel --no-build-isolation --no-deps packages/computer-use-macos -w dist`
- [ ] `python -m pip wheel --no-build-isolation --no-deps packages/wechat-desktop-tool -w dist`
- [ ] Verify built wheel contents:
      ```bash
      python scripts/release_preflight.py --wheel-dir dist
      ```
- [ ] Optional local wheel build/content/install-smoke gate without keeping
      `dist/`:
      ```bash
      python scripts/dev_check.py --check wheel-preflight
      ```
- [ ] Build all sdists/wheels with `python -m build` if available.
- [ ] Verify built wheel and sdist contents:
      ```bash
      python scripts/release_preflight.py --wheel-dir dist --sdist-dir dist
      ```
- [ ] Local release preflight:
      ```bash
      python scripts/release_preflight.py
      ```
- [ ] Verify release tag matches every package version:
      ```bash
      python scripts/release_tag_check.py --tag vX.Y.Z
      ```
- [ ] TestPyPI install report in a clean environment:
      ```bash
      python scripts/testpypi_install_report.py \
        --output ./testpypi-install.json
      ```
      The report must come from `https://test.pypi.org/simple/`, and every
      package version must match the current release version. Strict preflight
      also requires the generated `installPolicy` to show an isolated managed
      clean virtual environment, index-only install, no cache, and force
      reinstall.
- [ ] Confirm the production PyPI API token is stored as the GitHub repository
      secret `PYPI_API_TOKEN`. Verify only secret-name metadata with
      `gh secret list`, then generate the sanitized report:
      ```bash
      gh secret list --repo zhanghao1903/macos-computer-use
      python scripts/pypi_auth_report.py \
        --configured \
        --output ./pypi-auth.json
      ```
      The report must contain no token value, hash, fingerprint, or local path.
- [ ] TextEdit dry-run smoke:
      ```bash
      COMPUTER_USE_DRY_RUN=1 \
      python -m computer_use_macos.examples.textedit_smoke
      ```
- [ ] TextEdit real smoke on a macOS machine with Accessibility permission:
      ```bash
      python -m computer_use_macos.examples.textedit_smoke \
        > ./textedit-smoke.json
      ```
- [ ] WeChat dry-run smoke:
      ```bash
      WECHAT_TOOL_CONTACT="File Transfer" \
      WECHAT_TOOL_DRY_RUN=1 \
      python -m wechat_desktop_tool.examples.wechat_smoke
      ```
- [ ] WeChat focus/draft smoke from `docs/wechat-smoke.md`.
- [ ] WeChat submit smoke report from `docs/wechat-smoke.md` after explicit
      opt-in.
- [ ] WeChat selector-engine proof v2 from `docs/wechat-smoke.md`, generated
      from the exact release head. Confirm all three collection counts are at
      least 1, all timings are at most 3000 ms, `failedStep` is null, and no
      private debug report is retained or attached.
- [ ] Helper release verification:
      ```bash
      cd ./computer-use-helper
      ./build.sh
      computer-use-macos helper doctor \
        --manifest ./helper.json \
        --helper-app "./build/computer-use-helper.app" \
        --json
      ```
      The resulting `helper-doctor.json` must report `manifest`, `identity`,
      `endpoint`, `token`, and `helper_app` checks as `ok`. If you have an
      Apple Developer account, also run `./sign.sh`,
      `./notarize.sh`, and `computer-use-macos helper doctor` with
      `--verify-signature --verify-notarization`. Those checks are recommended
      for production helper distribution but are not required for this package
      release gate.

## Boundary Verification

- [ ] Packages import no Plato / Taskweavn modules.
- [ ] Packages import no LLM SDKs.
- [ ] Packages import no Agent frameworks.
- [ ] Packages import no UI frameworks.
- [ ] `computer-use-macos` imports no `wechat-desktop-tool`.
- [ ] `wechat-desktop-tool` imports no macOS backend package.
- [ ] High-risk direct primitive calls return blocked `ComputerUseResult`
      metadata, while protocol `run_command(...)` returns a structured failed
      `ToolObservation` with the original direct status preserved as
      `legacyStatus`.
- [ ] README states the caller owns confirmation and audit.
- [ ] `docs/permissions.md` reflects the current permission subject.
- [ ] `docs/migration-notes.md` reflects current import paths.
- [ ] Strict external proof preflight before publishing:
      ```bash
      python scripts/release_preflight.py \
        --wheel-dir dist \
        --sdist-dir dist \
        --helper-doctor-report ./helper-doctor.json \
        --textedit-smoke-report ./textedit-smoke.json \
        --wechat-smoke-report ./wechat-focus-draft-smoke.json \
        --wechat-smoke-report ./wechat-submit-smoke.json \
        --wechat-smoke-report ./wechat-selector-engine-smoke.json \
        --testpypi-install-report ./testpypi-install.json \
        --pypi-auth-report ./pypi-auth.json \
        --proof ./release-proof.json \
        --expected-source-sha "$(git rev-parse HEAD)" \
        --require-external
      ```

Example `release-proof.json`:

```json
{
  "helper_app_doctor": true,
  "textedit_smoke": true,
  "wechat_focus_draft_smoke": true,
  "wechat_submit_smoke": true,
  "wechat_selector_engine_smoke": true,
  "testpypi_install": true,
  "pypi_publish_auth": true
}
```

`testpypi_install` can be supplied by `./testpypi-install.json` instead of the
manual proof file.
`pypi_publish_auth` must be supplied by one detailed authentication report in
strict mode. The active token workflow uses `./pypi-auth.json`; a future OIDC
workflow may instead use `./trusted-publisher.json`, but both are never allowed.
`release-proof.json` accepts only known proof keys from the example shape, and
every value must be a JSON boolean, not a string.
When both a detailed report and `release-proof.json` are supplied, the detailed
report takes precedence. A manual `release-proof.json` cannot override a failed
helper doctor, TextEdit smoke, WeChat smoke, TestPyPI install, or PyPI
authentication report.
When `--expected-source-sha` is present, the selector proof boolean cannot come
from `release-proof.json`; a validated v2 selector report from that exact source
commit is mandatory.

- [ ] Attach the strict-preflight proof JSON files to the draft GitHub Release
      before publishing it. The release workflow downloads these exact asset
      names and blocks PyPI publishing if any are missing or fail validation:
      `helper-doctor.json`, `textedit-smoke.json`,
      `wechat-focus-draft-smoke.json`,
      `wechat-submit-smoke.json`, `wechat-selector-engine-smoke.json`,
      `testpypi-install.json`,
      `pypi-auth.json`, and `release-proof.json`.
- [ ] Prefer generating the release asset directory with:
      ```bash
      python scripts/release_proof_bundle.py \
        --output-dir ./release-proof \
        --helper-doctor-report ./helper-doctor.json \
        --textedit-smoke-report ./textedit-smoke.json \
        --wechat-focus-draft-report ./wechat-focus-draft-smoke.json \
        --wechat-submit-report ./wechat-submit-smoke.json \
        --wechat-selector-engine-report ./wechat-selector-engine-smoke.json \
        --testpypi-install-report ./testpypi-install.json \
        --pypi-auth-report ./pypi-auth.json \
        --expected-source-sha "$(git rev-parse HEAD)"
      ```
- [ ] Re-run the unified strict release gate against `./release-proof/`:
      ```bash
      python scripts/dev_check.py --check release-proof-preflight
      ```
      If the bundle command fails, inspect the generated JSON summary's
      `missingProofs` list. `--allow-incomplete` may be used to write a
      diagnostic bundle, but incomplete proof remains release-blocking.

## Publish Flow

1. Verify the release tag with `python scripts/release_tag_check.py --tag vX.Y.Z`.
2. Tag release, for example `vX.Y.Z`.
3. Publish to TestPyPI.
4. Install all distributions from TestPyPI in a clean macOS virtual
   environment.
5. Run imports, TextEdit smoke, and WeChat focus/draft smoke.
6. Verify the `PYPI_API_TOKEN` GitHub repository secret and generate
   `pypi-auth.json`.
7. Create a draft GitHub Release and attach the proof JSON assets.
8. Publish the GitHub Release to run the token-authenticated PyPI workflow.
9. Create GitHub release notes from `CHANGELOG.md`.

Do not commit tokens, place them in proof assets, or pass them through workflow
inputs. Trusted Publisher remains the preferred future migration when all three
project bindings are configured and the workflow is reviewed for OIDC mode.
