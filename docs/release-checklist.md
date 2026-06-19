# Release Checklist

Use this checklist before publishing `macos-computer-use`.

## Local Verification

- [ ] `python -m unittest discover -s tests`
- [ ] `python -m pip install -e .`
- [ ] `python -c "import macos_computer_use; print(macos_computer_use.__version__)"`
- [ ] `python -m pip wheel . -w dist`
- [ ] `python -m build --sdist --wheel` if the `build` package is available.
- [ ] `python examples/textedit_smoke.py` on a macOS machine with
      Accessibility permission.

## Boundary Verification

- [ ] Package imports no Plato / Taskweavn modules.
- [ ] Package imports no LLM SDKs.
- [ ] Package imports no Agent frameworks.
- [ ] Package imports no UI frameworks.
- [ ] High-risk actions return blocked result with risk metadata.
- [ ] README states the caller owns confirmation and audit.

## Publish Flow

1. Tag release, for example `v0.1.0`.
2. Publish to TestPyPI.
3. Install from TestPyPI in a clean macOS virtual environment.
4. Run import and TextEdit smoke.
5. Configure PyPI trusted publishing for `.github/workflows/release.yml`.
6. Create a GitHub Release to publish to PyPI.
7. Create GitHub release notes from `CHANGELOG.md`.

Prefer PyPI trusted publishing. Do not commit tokens.
