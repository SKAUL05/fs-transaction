import os
import uuid
import threading
import logging
from pathlib import Path
from typing import Union, List

from .actions import BaseAction, FileMove, FileCopy, FileWrite, FileDelete

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


class Transaction:
    """A transactional context manager for filesystem operations.

    Groups multiple file operations (move, copy, write, delete) into a single
    atomic transaction. Either all operations succeed, or all are rolled back
    to the original state.

    Features:
        - Atomic commit: all-or-nothing execution
        - Automatic rollback on exceptions
        - Backup-before-overwrite for safe rollback
        - Thread-safe via internal locking
        - Optional fsync for crash safety
        - Dry-run mode for validation without execution

    Usage:
        with Transaction() as t:
            t.write("config.json", json.dumps(data), overwrite=True)
            t.move("old.txt", "archive/old.txt")
            t.copy("template.txt", "new_from_template.txt")
            t.delete("obsolete.txt")
        # All operations committed atomically
    """

    def __init__(self, dry_run: bool = False, fsync: bool = True) -> None:
        """Initialize a new transaction.

        Args:
            dry_run: If True, validate all actions without executing them.
            fsync: If True, call os.fsync() for crash-safe writes.
        """
        self._actions: List[BaseAction] = []
        self._temp_files: List[Path] = []
        self._lock = threading.Lock()
        self._committed = False
        self.dry_run = dry_run
        self.fsync = fsync

    def __enter__(self) -> 'Transaction':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type:
            # Exception raised inside the with block.
            # Clean up any temp files created during preparation.
            logger.debug("Transaction aborted due to exception: %s", exc_val)
            self._cleanup_temp_files()
            return False  # Propagate the exception

        # No exception: attempt commit.
        self.commit()
        return False  # Never suppress exceptions

    def move(self, src: PathLike, dst: PathLike, overwrite: bool = False) -> None:
        """Queue a file move operation.

        Args:
            src: Source file path.
            dst: Destination file path.
            overwrite: If True, overwrite existing destination.
        """
        self._actions.append(FileMove(src, dst, overwrite=overwrite))

    def copy(self, src: PathLike, dst: PathLike, overwrite: bool = False) -> None:
        """Queue a file copy operation.

        Args:
            src: Source file path.
            dst: Destination file path.
            overwrite: If True, overwrite existing destination.
        """
        self._actions.append(FileCopy(src, dst, overwrite=overwrite))

    def write(self, dst: PathLike, content: str, mode: str = 'w', overwrite: bool = False) -> None:
        """Queue an atomic file write operation.

        Data is written to a temporary file immediately. On commit, the temp
        file is atomically renamed to the destination using os.replace().

        Args:
            dst: Destination file path.
            content: Content to write.
            mode: File open mode ('w' for text, 'wb' for binary).
            overwrite: If True, overwrite existing destination.
        """
        dst_path = Path(dst)
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        temp_name = f".tmp_{uuid.uuid4().hex}_{dst_path.name}"
        temp_path = dst_path.parent / temp_name

        with open(temp_path, mode) as f:
            f.write(content)

        self._temp_files.append(temp_path)
        self._actions.append(FileWrite(temp_path, dst_path, overwrite=overwrite, fsync=self.fsync))

    def delete(self, path: PathLike) -> None:
        """Queue a file delete operation.

        The file is backed up before deletion. On rollback, the file is
        restored from the backup.

        Args:
            path: Path to the file to delete.
        """
        self._actions.append(FileDelete(path))

    def commit(self) -> None:
        """Commit all queued operations atomically.

        Executes a three-phase commit:
        1. Validation: Check all prerequisites
        2. Execution: Perform all operations
        3. Cleanup: Remove backups on success, or rollback on failure

        Raises:
            RuntimeError: If the transaction was already committed.
            Exception: Any exception from validation or execution (after rollback).
        """
        with self._lock:
            if self._committed:
                raise RuntimeError("Transaction already committed.")

            # Phase 1: Validation
            logger.info("Validating %d action(s)...", len(self._actions))
            for action in self._actions:
                action.validate()

            if self.dry_run:
                logger.info("Dry-run mode: skipping execution of %d action(s).", len(self._actions))
                self._cleanup_temp_files()
                self._committed = True
                return

            # Phase 2: Execution
            completed: List[BaseAction] = []
            try:
                for action in self._actions:
                    action.execute()
                    completed.append(action)
            except Exception as e:
                # Phase 3a: Rollback on failure
                logger.error("Transaction failed: %s. Rolling back %d action(s)...", e, len(completed))
                for action in reversed(completed):
                    try:
                        action.rollback()
                    except Exception as rb_e:
                        logger.critical("Rollback failed for %r: %s", action, rb_e)
                self._cleanup_temp_files()
                raise

            # Phase 3b: Cleanup on success
            for action in self._actions:
                if isinstance(action, FileDelete):
                    action.cleanup()

            self._temp_files = []
            self._committed = True
            logger.info("Transaction committed successfully: %d action(s).", len(self._actions))

    def _cleanup_temp_files(self) -> None:
        """Clean up temporary staging files if transaction aborts."""
        for f in self._temp_files:
            if f.exists():
                try:
                    os.remove(f)
                except OSError as e:
                    logger.warning("Failed to clean up temp file %s: %s", f, e)

    def __repr__(self) -> str:
        status = "committed" if self._committed else f"{len(self._actions)} pending"
        return f"Transaction({status}, dry_run={self.dry_run})"