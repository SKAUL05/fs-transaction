# Contributing to fs-transaction

Thank you for your interest in contributing! Here's how to get started.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/SKAUL05/fs-transaction.git
cd fs-transaction

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[dev]"
```

## Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=fs_transaction --cov-report=html

# Run a specific test
python -m pytest tests/test_transaction.py::TestAtomicWrite::test_basic_write -v
```

## Code Style

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
# Check for issues
ruff check src/ tests/

# Auto-fix issues
ruff check --fix src/ tests/

# Format code
ruff format src/ tests/
```

## Pull Request Process

1. Fork the repo and create a feature branch from `main`.
2. Add tests for any new functionality.
3. Ensure all tests pass and linting is clean.
4. Update the README if you're adding new public API.
5. Add an entry to CHANGELOG.md under `[Unreleased]`.
6. Submit a pull request.

## Reporting Bugs

Please open an issue on GitHub with:
- A clear title and description.
- Steps to reproduce the bug.
- Expected vs actual behavior.
- Python version and OS.
