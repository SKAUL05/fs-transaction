# fs-transaction 🛡️

[![PyPI version](https://badge.fury.io/py/fs-transaction.svg)](https://badge.fury.io/py/fs-transaction)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python Versions](https://img.shields.io/pypi/pyversions/fs-transaction.svg)](https://pypi.org/project/fs-transaction/)

**Stop writing corrupted files.**

`fs-transaction` provides a Python context manager for **Atomic (ACID-compliant) file operations**. It ensures that your file writes are "all-or-nothing," preventing data corruption during crashes, power failures, or concurrent access.


## 💥 The Problem
In standard Python, writing to a file is risky:
```python
# DANGEROUS CODE
with open("database.json", "w") as f:
    f.write(start_processing())
    # <--- CRASH HERE (Power loss, Exception, OOM)
    f.write(finish_processing()) 
# RESULT: "database.json" is now half-written and corrupted forever.
```

## ✅ The Solution
`fs-transaction` uses the <b>Write-Replace Pattern:</b>

1. It writes data to a temporary file.
2. It successfully closes the file.
3. It performs an atomic `os.replace` to swap the new file with the old one.

If the script crashes at any point before step 3, your original file remains 100% untouched and valid.

## 🆚 Why use fs-transaction?
| Feature | Standard `open()` | `fs-transaction` |
| :--- | :---: | :---: |
| **Atomic Writes** | ❌ No (Partial writes possible) | ✅ **Yes** (All or nothing) |
| **Crash Safety** | ❌ Low (Data corruption risk) | ✅ **High** (Original file safe) |
| **Concurrency** | ❌ Manual locking required | ✅ **Thread-Safe** implementation |
| **Cleanup** | ❌ Manual `try/finally` blocks | ✅ **Automatic** temp file cleanup |
| **Ease of Use** | 🟡 Native | 🟢 **Native-like** Context Manager |

## 📦 Installation

```bash
pip install fs-transaction
```

## 🚀 Usage

### Basic Atomic Write
Use `AtomicWrite` exactly like you use standard `open`.

```python
from fs_transaction import AtomicWrite
import json

data = {"status": "processing", "items": [1, 2, 3]}

# Even if this block raises an Exception, 'config.json' will NOT be touched.
with AtomicWrite("config.json", mode="w") as f:
    f.write(json.dumps(data))

print("File written successfully and atomically.")
```

## 🤝 Contributing
Contributions, issues, and feature requests are welcome!
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request
