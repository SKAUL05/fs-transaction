# fs-transaction

**Stop writing half-broken file scripts.** `fs-transaction` brings database-style atomicity to filesystem operations.

## The Problem
You write a script to process 1,000 files. It crashes on file #500. Now you have a corrupted state: 500 files moved, 500 remaining. You have to manually cleanup the mess.

## The Solution
Wrap your operations in a `Transaction`. If **any** error occurs, **nothing** happens on disk.

```python

from fs_transaction import Transaction

# No changes applied until the block finishes successfully
with Transaction() as t:
    t.move("data.csv", "archive/data_2023.csv")
    t.write("manifest.txt", "Archived successfully")
    
    # If this raises an error, the move is undone and manifest is never written.
    t.copy("backup.img", "cloud/backup.img")