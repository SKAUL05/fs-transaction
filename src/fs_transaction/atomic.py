import os
import uuid
import logging
from pathlib import Path
from typing import Union, Optional, IO, Any

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


class AtomicWrite:
    """A context manager for atomic single-file writes.

    Works as a drop-in replacement for the built-in open() function.
    Uses the Write-Replace pattern:

    1. Writes data to a temporary file in the same directory.
    2. Calls os.fsync() for crash safety.
    3. Atomically replaces the destination with os.replace().

    If the context manager exits due to an exception, the original file
    remains completely untouched.

    Usage:
        from fs_transaction import AtomicWrite
        import json

        data = {"key": "value"}
        with AtomicWrite("config.json", mode="w") as f:
            f.write(json.dumps(data, indent=2))
        # config.json is now atomically updated

    Args:
        path: The target file path to write to.
        mode: File open mode. Must be a write mode ('w', 'wb', 'wt').
        overwrite: If True (default), overwrite existing files. If False,
            raise FileExistsError if the file already exists.
        fsync: If True (default), call os.fsync() before replacing
            for crash safety.
        **kwargs: Additional keyword arguments passed to open().
    """

    def __init__(
        self,
        path: PathLike,
        mode: str = 'w',
        overwrite: bool = True,
        fsync: bool = True,
        **kwargs: Any,
    ) -> None:
        if 'r' in mode and 'w' not in mode and '+' not in mode:
            raise ValueError(f"AtomicWrite requires a write mode, got: {mode!r}")

        self._path = Path(path)
        self._mode = mode
        self._overwrite = overwrite
        self._fsync = fsync
        self._kwargs = kwargs
        self._temp_path: Optional[Path] = None
        self._file: Optional[IO] = None

    def __enter__(self) -> IO:
        # Validate before doing anything
        if self._path.exists() and not self._overwrite:
            raise FileExistsError(
                f"File already exists: {self._path}. Use overwrite=True to replace."
            )

        # Create parent directories if needed
        self._path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp file in the same directory (required for atomic os.replace)
        temp_name = f".tmp_{uuid.uuid4().hex}_{self._path.name}"
        self._temp_path = self._path.parent / temp_name

        self._file = open(self._temp_path, self._mode, **self._kwargs)
        return self._file

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if self._file is not None:
            self._file.close()

        if exc_type is not None:
            # Exception occurred: clean up temp file, leave original untouched
            self._cleanup()
            return False  # Propagate the exception

        if self._temp_path is None:
            return False

        try:
            # Preserve original file permissions
            if self._path.exists():
                try:
                    original_stat = self._path.stat()
                    os.chmod(self._temp_path, original_stat.st_mode)
                except OSError:
                    pass

            # fsync for crash safety
            if self._fsync:
                fd = os.open(str(self._temp_path), os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)

            # Atomic replace
            os.replace(self._temp_path, self._path)

            # fsync parent directory
            if self._fsync:
                dir_fd = os.open(str(self._path.parent), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)

            logger.debug("AtomicWrite completed: %s", self._path)
        except Exception:
            self._cleanup()
            raise

        return False

    def _cleanup(self) -> None:
        """Remove the temporary file."""
        if self._temp_path and self._temp_path.exists():
            try:
                os.remove(self._temp_path)
            except OSError as e:
                logger.warning("Failed to clean up temp file %s: %s", self._temp_path, e)

    def __repr__(self) -> str:
        return f"AtomicWrite(path={self._path!r}, mode={self._mode!r})"
