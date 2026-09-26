# Contributing

Thanks for considering contributing!

## Reporting Bugs

Open an issue with: steps to reproduce, expected vs actual, environment.

## Suggesting Features

Open an issue titled `[Feature] ...` with a clear use case.

## Pull Requests

1. Fork and create a branch: `git checkout -b feature/my-feature`
2. Follow PEP 8 for Python, 2-space indent for HTML/CSS.
3. Run tests: `pytest tests/e2e_test.py -v`
4. Write a clear commit message.
5. Open a PR describing **what** and **why**.

## Code Style

- **Python:** PEP 8, max line length 100.
- **Templates:** no frontend frameworks (Vanilla JS only).
- Keep `store/services.py` provider-agnostic.
