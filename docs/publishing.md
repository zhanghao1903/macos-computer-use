# Publishing

This repository is prepared for PyPI trusted publishing of the app-control
tool package suite.

## Preconditions

1. These package names are available or owned on PyPI:
   - `app-control-protocol`
   - `computer-use-macos`
   - `wechat-desktop-tool`
2. PyPI Trusted Publisher is configured for each PyPI project:
   - owner: `zhanghao1903`
   - repository: `macos-computer-use`
   - workflow: `release.yml`
   - environment: none, unless one is later added intentionally
3. TestPyPI should be used manually before the first real PyPI release.

## Dry-Run Build

Run locally:

```bash
python scripts/dev_check.py

PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s tests
PYTHONPATH=packages/app-control-protocol/src \
  python -m unittest discover -s packages/app-control-protocol/tests
PYTHONPATH=packages/app-control-protocol/src:packages/computer-use-macos/src \
  python -m unittest discover -s packages/computer-use-macos/tests
PYTHONPATH=packages/app-control-protocol/src:packages/wechat-desktop-tool/src \
  python -m unittest discover -s packages/wechat-desktop-tool/tests

python scripts/release_preflight.py
python scripts/release_tag_check.py --tag vX.Y.Z

python -m build packages/app-control-protocol --sdist --wheel --outdir dist
python -m build packages/computer-use-macos --sdist --wheel --outdir dist
python -m build packages/wechat-desktop-tool --sdist --wheel --outdir dist
python scripts/release_preflight.py --wheel-dir dist --sdist-dir dist
```

## TestPyPI Flow

The repository does not automatically publish to TestPyPI. Use TestPyPI for the
first release candidate before creating the GitHub release:

```bash
python -m build packages/app-control-protocol --sdist --wheel --outdir dist
python -m build packages/computer-use-macos --sdist --wheel --outdir dist
python -m build packages/wechat-desktop-tool --sdist --wheel --outdir dist
python -m twine upload --repository testpypi dist/*
```

Then validate in a clean virtual environment:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ app-control-protocol
python -m pip install --index-url https://test.pypi.org/simple/ computer-use-macos
python -m pip install --index-url https://test.pypi.org/simple/ wechat-desktop-tool
python -c "import computer_use_macos; print(computer_use_macos.__version__)"
python -c "import wechat_desktop_tool; print(wechat_desktop_tool.__version__)"
```

Archive the install proof in JSON form:

```bash
python scripts/testpypi_install_report.py \
  --output ./testpypi-install.json
```

The generated report has this shape:

```json
{
  "source": "testpypi",
  "indexUrl": "https://test.pypi.org/simple/",
  "installPolicy": {
    "managedVirtualenv": true,
    "isolated": true,
    "indexOnly": true,
    "noCache": true,
    "forceReinstall": true
  },
  "packages": [
    {
      "name": "app-control-protocol",
      "version": "X.Y.Z",
      "installed": true,
      "imported": true,
      "apiSmoke": true
    },
    {
      "name": "computer-use-macos",
      "version": "X.Y.Z",
      "installed": true,
      "imported": true,
      "apiSmoke": true
    },
    {
      "name": "wechat-desktop-tool",
      "version": "X.Y.Z",
      "installed": true,
      "imported": true,
      "apiSmoke": true
    }
  ]
}
```

`apiSmoke` verifies the installed public API surface and command builders, not
only the package import. Strict preflight also requires `indexUrl` to be
TestPyPI, `installPolicy` to show an isolated managed clean virtual
environment with no-cache force reinstall and no extra index, and every
installed package `version` to match the current release.

Record release-blocking external proof in a local JSON file before publishing
to PyPI:

```json
{
  "helper_app_doctor": true,
  "textedit_smoke": true,
  "wechat_focus_draft_smoke": true,
  "wechat_submit_smoke": true,
  "testpypi_install": true,
  "pypi_trusted_publisher": true
}
```

`release-proof.json` is a summary and fallback for manually verified proof.
It must contain only known release proof keys, and every value must be a JSON
boolean.
When strict preflight also receives detailed reports such as
`helper-doctor.json`, `textedit-smoke.json`, `testpypi-install.json`, or
`trusted-publisher.json`, those detailed reports take precedence and cannot be
overridden by the summary file.

After checking each PyPI project in the PyPI UI, archive PyPI Trusted
Publisher proof in JSON form:

```bash
python scripts/trusted_publisher_report.py \
  --all-configured \
  --output ./trusted-publisher.json
```

The generated report has this shape:

```json
{
  "source": "pypi",
  "verification": "manual",
  "generatedAt": "2026-06-28T00:00:00Z",
  "projects": [
    {
      "name": "app-control-protocol",
      "trustedPublisher": true,
      "publisher": {
        "owner": "zhanghao1903",
        "repository": "macos-computer-use",
        "workflow": "release.yml",
        "environment": null
      }
    },
    {
      "name": "computer-use-macos",
      "trustedPublisher": true,
      "publisher": {
        "owner": "zhanghao1903",
        "repository": "macos-computer-use",
        "workflow": "release.yml",
        "environment": null
      }
    },
    {
      "name": "wechat-desktop-tool",
      "trustedPublisher": true,
      "publisher": {
        "owner": "zhanghao1903",
        "repository": "macos-computer-use",
        "workflow": "release.yml",
        "environment": null
      }
    }
  ]
}
```

For helper proof, archive the JSON output from:

```bash
cd ./computer-use-helper
./build.sh
computer-use-macos helper doctor \
  --manifest ./helper.json \
  --helper-app "./build/computer-use-helper.app" \
  --json
```

The strict release gate requires the helper doctor report to pass the core
helper checks: `manifest`, `identity`, `endpoint`, `token`, and `helper_app`.
If you have an Apple Developer account, also run `./sign.sh`,
`./notarize.sh`, and the doctor `--verify-signature` /
`--verify-notarization` checks before production helper distribution.

For TextEdit proof, archive the real smoke JSON output:

```bash
python -m computer_use_macos.examples.textedit_smoke \
  > ./textedit-smoke.json
```

Strict preflight accepts this report only when it is a real run with
`"dryRun": false`, `"success": true`, and successful protocol observations for
`readiness`, `open_app`, `focus_app`, `observe`, and `type_text`.

Then run the strict preflight:

```bash
python scripts/release_preflight.py \
  --wheel-dir dist \
  --sdist-dir dist \
  --helper-doctor-report ./helper-doctor.json \
  --textedit-smoke-report ./textedit-smoke.json \
  --wechat-smoke-report ./wechat-focus-draft-smoke.json \
  --wechat-smoke-report ./wechat-submit-smoke.json \
  --testpypi-install-report ./testpypi-install.json \
  --trusted-publisher-report ./trusted-publisher.json \
  --proof ./release-proof.json \
  --require-external
```

To prepare the exact GitHub Release asset directory expected by the release
workflow, run:

```bash
python scripts/release_proof_bundle.py \
  --output-dir ./release-proof \
  --helper-doctor-report ./helper-doctor.json \
  --textedit-smoke-report ./textedit-smoke.json \
  --wechat-focus-draft-report ./wechat-focus-draft-smoke.json \
  --wechat-submit-report ./wechat-submit-smoke.json \
  --testpypi-install-report ./testpypi-install.json \
  --trusted-publisher-report ./trusted-publisher.json
```

The bundled proof directory can be checked through the unified developer gate:

```bash
python scripts/dev_check.py --check release-proof-preflight
```

`release_proof_bundle.py` exits non-zero when any strict proof is missing. Its
JSON output includes `missingProofs`, which lists the exact proof keys that
still need real external evidence. Use `--allow-incomplete` only when you want
to write the asset directory for diagnostics; the strict release preflight and
GitHub release workflow will still reject incomplete proof.

The GitHub release workflow enforces the same strict preflight before the PyPI
publish step. Attach these JSON files to the GitHub Release before publishing
it:

```text
helper-doctor.json
textedit-smoke.json
wechat-focus-draft-smoke.json
wechat-submit-smoke.json
testpypi-install.json
trusted-publisher.json
release-proof.json
```

## PyPI Flow

After TestPyPI validation:

1. Update `CHANGELOG.md`.
2. Ensure all package `pyproject.toml` versions match the release.
3. Verify the GitHub Release tag matches every package version:
   ```bash
   python scripts/release_tag_check.py --tag vX.Y.Z
   ```
4. Run strict release preflight with external proof.
5. Create and push a tag, for example `vX.Y.Z`.
6. Create a draft GitHub Release from that tag.
7. Attach the external proof JSON files listed above.
8. Publish the GitHub Release.
9. The `Release` workflow builds distributions, downloads the proof assets,
   runs strict preflight, and publishes to PyPI only if all proofs pass.

Do not commit PyPI API tokens.

## Post-Release Checks

Install from PyPI in a clean macOS virtual environment:

```bash
python -m pip install app-control-protocol
python -m pip install computer-use-macos
python -m pip install wechat-desktop-tool
python -c "import computer_use_macos; print(computer_use_macos.__version__)"
python -c "import wechat_desktop_tool; print(wechat_desktop_tool.__version__)"
```

Then run the manual TextEdit smoke from
[manual-smoke.md](manual-smoke.md).
