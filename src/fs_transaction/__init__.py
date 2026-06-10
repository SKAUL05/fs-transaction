"""fs-transaction: Atomic filesystem operations for safe batch processing."""

from .core import Transaction
from .atomic import AtomicWrite
from .actions import FileMove, FileCopy, FileWrite, FileDelete, BaseAction

__version__ = "0.2.0"

__all__ = [
    "Transaction",
    "AtomicWrite",
    "FileMove",
    "FileCopy",
    "FileWrite",
    "FileDelete",
    "BaseAction",
]