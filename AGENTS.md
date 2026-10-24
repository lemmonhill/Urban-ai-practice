# AGENTS.md

Python package boilerplate for IDU (Institute of Design and Urban Studies). The package is named `my_package` and the repo is a template meant to be renamed/copied for real projects.

## Layout
- `my_package/` - library code (`my_module.py` is the only module; `__init__.py` holds metadata).
- `tests/` - pytest tests (`test_*.py`, `test_*` functions).
- `docs/source/` - Sphinx sources (`.rst`, mostly Russian); `examples/` holds runnable Jupyter notebooks + data.
- `Makefile` at root defines the dev workflow; `.github/workflows/` has tests, docs, and PyPI jobs.

## Commands
`make` is **not installed on the Windows dev machine** (docs recommend WSL/Ubuntu). Either use WSL or run the underlying command directly.

- Format: `make format` -> `isort my_package` then `black my_package` (line length 120).
- Lint: `make lint` -> `pylint my_package`. No typechecker is configured.
- Test: `make tests` -> `pytest tests`; coverage: `make tests-cov` -> `pytest tests --cov`.
- Install (editable): `pip install -e ".[dev]"`, `".[tests]"`, `".[docs]"`.
- Docs build: `sphinx-build docs/source docs/build`.
- Package build: `python -m build`.

## Known mismatches (do not copy blindly)
- Makefile targets are `tests` / `tests-cov` (plural), but `.github/workflows/tests.yml` and `docs/source/guide/testing.rst` call `make test` / `make test-cov`, which do not exist. CI is broken as written; the real targets are plural.
- Makefile `install-test` runs `pip install -e '.[test]'`, but the extra in `pyproject.toml` is named `tests`. Use `".[tests]"`.
- `pyproject.toml` sets `license = { file = "LICENCE" }` while the file on disk is `LICENSE`.
- `README.rst` shows `from my_package.my_module_1 import MyClass`; the actual module is `my_package.my_module`.

## Conventions
- Style: black + isort, `line-length = 120`, target `py310`; pre-commit runs trailing-whitespace/eof/black hooks.
- Docstrings: numpydoc style (Sphinx uses napoleon).
- Version is dynamic via `setuptools_scm` (derived from git tags). `my_package/__init__.py` reads it with `importlib.metadata.version("my_package")`, so the package must be installed before it can be imported.
- README is included into Sphinx via `.. include::` using `logo-start/logo-end` and `readme-start/readme-end` markers in `README.rst` - keep those markers when editing.

## Release/docs flow
- Push to `main` builds docs and deploys to the `documentation` branch (GitHub Pages).
- PyPI publishes on `v*` tags: pre-releases from `develop`, releases from `main` (see `.github/workflows/pypi.yml`).
