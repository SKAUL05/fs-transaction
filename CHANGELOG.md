# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2025-06-10

### Added
- `AtomicWrite` context manager — drop-in replacement for `open()` with atomic writes.
- `FileDelete` action for transactional file deletion with rollback.
- `overwrite` parameter for `write()`, `move()`, and `copy()` operations.
- Backup-before-overwrite for safe rollback of overwritten files.
- `dry_run` mode for validating transactions without executing.
- `os.fsync()` support for true crash safety.
- File permission preservation on overwrite.
- Thread-safe commit via `threading.Lock`.
- Type hints on all public APIs.
- `__repr__` methods on all classes for better debugging.
- `py.typed` marker for PEP 561 compliance.
- Comprehensive test suite with 30+ test cases.

### Changed
- `__exit__` no longer returns `True` (was silently swallowing exceptions).
- Replaced `print()` statements with Python `logging` module.
- Tests now use `tempfile.mkdtemp()` for proper isolation.

### Fixed
- `FileWrite.rollback()` now restores original file from backup instead of just deleting.
- License mismatch between README (GPL v3) and pyproject.toml (MIT) — now consistently GPL v3.

## [0.1.1] - 2025-01-01

### Changed
- Updated project URLs in pyproject.toml.

## [0.1.0] - 2025-01-01

### Added
- Initial release with `Transaction` context manager.
- `FileMove`, `FileCopy`, and `FileWrite` actions.
- Basic rollback support.
