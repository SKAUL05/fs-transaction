# fs-transaction 🛡️

[![PyPI version](https://badge.fury.io/py/fs-transaction.svg)](https://badge.fury.io/py/fs-transaction)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python Versions](https://img.shields.io/pypi/pyversions/fs-transaction.svg)](https://pypi.org/project/fs-transaction/)
[![Tests](https://github.com/SKAUL05/fs-transaction/actions/workflows/test.yml/badge.svg)](https://github.com/SKAUL05/fs-transaction/actions/workflows/test.yml)

**Stop writing corrupted files.**

`fs-transaction` provides Python context managers for **atomic, crash-safe file operations**. It ensures your file writes are "all-or-nothing," preventing data corruption during crashes, power failures, or concurrent access.

## 💥 The Problem

In standard Python, writing to a file is risky:

```python
# ⚠️ DANGEROUS CODE
with open("database.json", "w") as f:
    f.write(start_processing())
    # <--- CRASH HERE (Power loss, Exception, OOM)
    f.write(finish_processing())
# RESULT: "database.json" is now half-written and corrupted forever.
```

## ✅ The Solution

`fs-transaction` uses the **Write-Replace Pattern**:

1. It writes data to a temporary file in the same directory.
2. It calls `os.fsync()` for crash safety.
3. It performs an atomic `os.replace()` to swap the new file with the old one.

If the script crashes at any point before step 3, your original file remains 100% untouched and valid.

## 🆚 Why use fs-transaction?

| Feature | Standard `open()` | `fs-transaction` |
| :--- | :---: | :---: |
| **Atomic Writes** | ❌ No (Partial writes possible) | ✅ **Yes** (All or nothing) |
| **Crash Safety** | ❌ Low (Data corruption risk) | ✅ **High** (`fsync` + atomic replace) |
| **Concurrency** | ❌ Manual locking required | ✅ **Thread-safe** implementation |
| **Cleanup** | ❌ Manual `try/finally` blocks | ✅ **Automatic** temp file cleanup |
| **Rollback** | ❌ Not possible | ✅ **Automatic** on failure |
| **Overwrite Safety** | ❌ Destroys original | ✅ **Backup + restore** on failure |
| **Ease of Use** | 🟡 Native | 🟢 **Drop-in** replacement |

## 📦 Installation

```bash
pip install fs-transaction
```

## 🚀 Usage

### Quick Start: `AtomicWrite`

Use `AtomicWrite` as a drop-in replacement for `open()` when you need crash-safe single-file writes:

```python
from fs_transaction import AtomicWrite
import json

data = {"status": "processing", "items": [1, 2, 3]}

# Even if this block raises an Exception, 'config.json' will NOT be corrupted.
with AtomicWrite("config.json", mode="w") as f:
    f.write(json.dumps(data, indent=2))

print("File written safely and atomically!")
```

### Batch Operations: `Transaction`

Use `Transaction` to group multiple file operations into a single atomic unit:

```python
from fs_transaction import Transaction

with Transaction() as t:
    t.write("config.json", json.dumps(new_config), overwrite=True)
    t.move("data/old.csv", "archive/old.csv")
    t.copy("templates/default.yaml", "config/app.yaml")
    t.delete("cache/stale.tmp")
# ✅ All 4 operations succeed together, or none of them happen.
```

### Overwriting Existing Files

By default, operations raise `FileExistsError` if the destination exists. Use `overwrite=True` to safely replace:

```python
# AtomicWrite overwrites by default (like open())
with AtomicWrite("existing_file.txt") as f:
    f.write("Updated content")

# Transaction methods require explicit overwrite=True
with Transaction() as t:
    t.write("existing_file.txt", "Updated", overwrite=True)
    t.copy("src.txt", "existing_dst.txt", overwrite=True)
    t.move("new.txt", "existing.txt", overwrite=True)
```

### Dry-Run Mode

Validate all operations without executing them:

```python
with Transaction(dry_run=True) as t:
    t.move("important.txt", "archive/important.txt")
    t.write("report.txt", generate_report())
# ✅ Validation passed, but no files were changed.
```

### Deleting Files Safely

```python
with Transaction() as t:
    t.delete("obsolete_config.json")
    t.delete("old_data.csv")
# Files are backed up before deletion.
# If something fails, they are restored automatically.
```

## 🔧 API Reference

### `AtomicWrite(path, mode='w', overwrite=True, fsync=True, **kwargs)`

Context manager for atomic single-file writes.

| Parameter | Type | Default | Description |
|:----------|:-----|:--------|:------------|
| `path` | `str \| Path` | — | Target file path |
| `mode` | `str` | `'w'` | File open mode (`'w'`, `'wb'`, etc.) |
| `overwrite` | `bool` | `True` | Replace existing files |
| `fsync` | `bool` | `True` | Call `os.fsync()` for crash safety |
| `**kwargs` | — | — | Passed to `open()` |

### `Transaction(dry_run=False, fsync=True)`

Context manager for batching multiple file operations atomically.

| Parameter | Type | Default | Description |
|:----------|:-----|:--------|:------------|
| `dry_run` | `bool` | `False` | Validate without executing |
| `fsync` | `bool` | `True` | Call `os.fsync()` for crash safety |

**Methods:**

| Method | Description |
|:-------|:------------|
| `write(dst, content, mode='w', overwrite=False)` | Atomic file write |
| `move(src, dst, overwrite=False)` | Move/rename a file |
| `copy(src, dst, overwrite=False)` | Copy a file |
| `delete(path)` | Delete a file (with backup for rollback) |
| `commit()` | Manually commit (auto-called on `__exit__`) |

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────┐
│                  Transaction                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ │
│  │FileMove │ │FileCopy │ │FileWrite│ │FileDel │ │
│  └────┬────┘ └────┬────┘ └────┬────┘ └───┬────┘ │
│       │           │           │           │      │
│  ┌────▼───────────▼───────────▼───────────▼────┐ │
│  │           1. Validate All                   │ │
│  │           2. Execute All (with backups)      │ │
│  │           3. Cleanup / Rollback              │ │
│  └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## 🛡️ Safety Guarantees

- **Atomicity**: Operations are committed as a single unit. Partial state is impossible.
- **Crash Safety**: `os.fsync()` ensures data hits disk before the atomic rename.
- **Backup-Restore**: Original files are backed up before overwrite. On failure, they are restored.
- **Thread Safety**: Internal locking prevents concurrent commits.
- **Automatic Cleanup**: Temp files are always cleaned up, even on exceptions.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## 📄 License

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.

## 📋 Changelog

See [CHANGELOG.md](CHANGELOG.md) for a list of changes.
