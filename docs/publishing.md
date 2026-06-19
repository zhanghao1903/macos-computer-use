# Publishing

This repository is prepared for PyPI trusted publishing.

## Preconditions

1. The package name `macos-computer-use` is available or owned on PyPI.
2. PyPI Trusted Publisher is configured for this repository:
   - owner: `zhanghao1903`
   - repository: `macos-computer-use`
   - workflow: `release.yml`
   - environment: none, unless one is later added intentionally
3. TestPyPI should be used manually before the first real PyPI release.

## Dry-Run Build

Run locally:

```bash
python -m unittest discover -s tests
python -m build --sdist --wheel --outdir dist
python -m pip install dist/macos_computer_use-0.1.0-py3-none-any.whl
python -c "import macos_computer_use; print(macos_computer_use.__version__)"
```

## TestPyPI Flow

The repository does not automatically publish to TestPyPI. Use TestPyPI for the
first release candidate before creating the GitHub release:

```bash
python -m build --sdist --wheel --outdir dist
python -m twine upload --repository testpypi dist/*
```

Then validate in a clean virtual environment:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ macos-computer-use
python -c "import macos_computer_use; print(macos_computer_use.__version__)"
```

## PyPI Flow

After TestPyPI validation:

1. Update `CHANGELOG.md`.
2. Ensure `pyproject.toml` version matches the release.
3. Create and push a tag, for example `v0.1.0`.
4. Create a GitHub Release from that tag.
5. The `Release` workflow builds distributions and publishes to PyPI.

Do not commit PyPI API tokens.

## Post-Release Checks

Install from PyPI in a clean macOS virtual environment:

```bash
python -m pip install macos-computer-use
python -c "import macos_computer_use; print(macos_computer_use.__version__)"
```

Then run the manual TextEdit smoke from
[manual-smoke.md](manual-smoke.md).
