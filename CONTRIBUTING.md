# Contributing

Thanks for your interest! A few rules matter more than usual here because the
project handles health data.

## Golden rule: no real data, ever

Never attach, commit or paste real scans, patient names, ID numbers or recognised
text in issues, pull requests, tests or screenshots. Use `quillvault templates` to
create synthetic material. The pre-commit hook and CI block images and documents
outside `tests/fixtures/synthetic/` and `docs/assets/`.

## Setup

```bash
uv sync --extra cpu --extra templates --extra pdf   # add --extra ui / --extra trocr if needed
uv run pre-commit install
```

## Before opening a pull request

```bash
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src
uv run pytest --cov
```

* New behaviour needs tests. Generate test images in code (see `tests/conftest.py`).
* Keep the privacy guarantees in [SECURITY.md](SECURITY.md) intact. A change that adds a
  network call, a log line containing document content, or a file written outside the
  private temp dir will not be merged.
* Update `CHANGELOG.md` under *Unreleased*.

## Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, …).
