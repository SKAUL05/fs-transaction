import os
import shutil
import uuid
import logging
from pathlib import Path
from typing import Union, Optional

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]


class BaseAction:
    """Base class for all transactional filesystem actions."""

    def validate(self) -> None:
        """Check prerequisites before any disk changes happen."""
        pass

    def execute(self) -> None:
        """Perform the operation."""
        raise NotImplementedError

    def rollback(self) -> None:
        """Undo the operation."""
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


class FileMove(BaseAction):
    def __init__(self, src: PathLike, dst: PathLike, overwrite: bool = False) -> None:
        self.src = Path(src)
        self.dst = Path(dst)
        self.overwrite = overwrite
        self._executed = False
        self._backup_path: Optional[Path] = None  # backup of dst if overwriting

    def validate(self) -> None:
        if not self.src.exists():
            raise FileNotFoundError(f"Source file not found: {self.src}")
        if self.dst.exists() and not self.overwrite:
            raise FileExistsError(f"Destination already exists: {self.dst}. Use overwrite=True to replace.")

    def execute(self) -> None:
        self.dst.parent.mkdir(parents=True, exist_ok=True)
        # Backup existing destination if overwriting
        if self.dst.exists() and self.overwrite:
            self._backup_path = self.dst.parent / f".tmp_backup_{uuid.uuid4().hex}_{self.dst.name}"
            shutil.copy2(str(self.dst), str(self._backup_path))
        shutil.move(str(self.src), str(self.dst))
        self._executed = True

    def rollback(self) -> None:
        if self._executed:
            if self.dst.exists():
                # Move the file back to source
                shutil.move(str(self.dst), str(self.src))
            # Restore backup if we had overwritten
            if self._backup_path and self._backup_path.exists():
                shutil.move(str(self._backup_path), str(self.dst))
        self._cleanup_backup()

    def _cleanup_backup(self) -> None:
        if self._backup_path and self._backup_path.exists():
            try:
                os.remove(self._backup_path)
            except OSError:
                pass

    def __repr__(self) -> str:
        return f"FileMove(src={self.src!r}, dst={self.dst!r}, overwrite={self.overwrite})"


class FileCopy(BaseAction):
    def __init__(self, src: PathLike, dst: PathLike, overwrite: bool = False) -> None:
        self.src = Path(src)
        self.dst = Path(dst)
        self.overwrite = overwrite
        self._created_file = False
        self._backup_path: Optional[Path] = None

    def validate(self) -> None:
        if not self.src.exists():
            raise FileNotFoundError(f"Source file not found: {self.src}")
        if self.dst.exists() and not self.overwrite:
            raise FileExistsError(f"Destination already exists: {self.dst}. Use overwrite=True to replace.")

    def execute(self) -> None:
        self.dst.parent.mkdir(parents=True, exist_ok=True)
        if self.dst.exists() and self.overwrite:
            self._backup_path = self.dst.parent / f".tmp_backup_{uuid.uuid4().hex}_{self.dst.name}"
            shutil.copy2(str(self.dst), str(self._backup_path))
        shutil.copy2(str(self.src), str(self.dst))
        self._created_file = True

    def rollback(self) -> None:
        if self._created_file:
            if self._backup_path and self._backup_path.exists():
                # Restore original
                shutil.move(str(self._backup_path), str(self.dst))
            elif self.dst.exists():
                os.remove(self.dst)
        self._cleanup_backup()

    def _cleanup_backup(self) -> None:
        if self._backup_path and self._backup_path.exists():
            try:
                os.remove(self._backup_path)
            except OSError:
                pass

    def __repr__(self) -> str:
        return f"FileCopy(src={self.src!r}, dst={self.dst!r}, overwrite={self.overwrite})"


class FileWrite(BaseAction):
    """Handles atomic writes using write-replace pattern.

    Data is written to a temp file immediately. The 'execute' step
    atomically replaces the destination with the temp file using os.replace().
    """

    def __init__(self, temp_path: Path, final_path: Path, overwrite: bool = False, fsync: bool = True) -> None:
        self.temp_path = Path(temp_path)
        self.final_path = Path(final_path)
        self.overwrite = overwrite
        self.fsync = fsync
        self._executed = False
        self._backup_path: Optional[Path] = None

    def validate(self) -> None:
        if self.final_path.exists() and not self.overwrite:
            raise FileExistsError(
                f"Destination already exists: {self.final_path}. Use overwrite=True to replace."
            )

    def execute(self) -> None:
        self.final_path.parent.mkdir(parents=True, exist_ok=True)

        # Preserve permissions from existing file
        if self.final_path.exists():
            try:
                original_stat = self.final_path.stat()
                os.chmod(self.temp_path, original_stat.st_mode)
            except OSError:
                pass

        # Backup existing file for rollback
        if self.final_path.exists() and self.overwrite:
            self._backup_path = self.final_path.parent / f".tmp_backup_{uuid.uuid4().hex}_{self.final_path.name}"
            shutil.copy2(str(self.final_path), str(self._backup_path))

        # fsync the temp file for crash safety
        if self.fsync:
            fd = os.open(str(self.temp_path), os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)

        # Atomic replace
        os.replace(self.temp_path, self.final_path)
        self._executed = True

        # fsync the parent directory for crash safety
        if self.fsync:
            dir_fd = os.open(str(self.final_path.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)

    def rollback(self) -> None:
        if self._executed:
            # Restore from backup if available
            if self._backup_path and self._backup_path.exists():
                shutil.move(str(self._backup_path), str(self.final_path))
            elif self.final_path.exists():
                os.remove(self.final_path)
        # Clean up temp file if execute didn't run
        if self.temp_path.exists():
            os.remove(self.temp_path)
        self._cleanup_backup()

    def _cleanup_backup(self) -> None:
        if self._backup_path and self._backup_path.exists():
            try:
                os.remove(self._backup_path)
            except OSError:
                pass

    def __repr__(self) -> str:
        return f"FileWrite(temp={self.temp_path!r}, dst={self.final_path!r}, overwrite={self.overwrite})"


class FileDelete(BaseAction):
    """Deletes a file within a transaction, with rollback support.

    On execute, the file is moved to a temp backup location.
    On commit success, the backup is cleaned up.
    On rollback, the file is restored from the backup.
    """

    def __init__(self, path: PathLike) -> None:
        self.path = Path(path)
        self._backup_path: Optional[Path] = None
        self._executed = False

    def validate(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(f"File not found: {self.path}")

    def execute(self) -> None:
        # Move to backup instead of deleting (for safe rollback)
        self._backup_path = self.path.parent / f".tmp_backup_{uuid.uuid4().hex}_{self.path.name}"
        shutil.move(str(self.path), str(self._backup_path))
        self._executed = True

    def rollback(self) -> None:
        if self._executed and self._backup_path and self._backup_path.exists():
            shutil.move(str(self._backup_path), str(self.path))

    def cleanup(self) -> None:
        """Called after successful commit to remove the backup."""
        if self._backup_path and self._backup_path.exists():
            try:
                os.remove(self._backup_path)
            except OSError:
                pass

    def __repr__(self) -> str:
        return f"FileDelete(path={self.path!r})"