import os
import shutil
from pathlib import Path

class BaseAction:
    def validate(self):
        """Check prerequisites before any disk changes happen."""
        pass
        
    def execute(self):
        """Perform the operation."""
        raise NotImplementedError
        
    def rollback(self):
        """Undo the operation."""
        pass

class FileMove(BaseAction):
    def __init__(self, src, dst):
        self.src = Path(src)
        self.dst = Path(dst)
        self._executed = False

    def validate(self):
        if not self.src.exists():
            raise FileNotFoundError(f"Source file not found: {self.src}")
        if self.dst.exists():
            raise FileExistsError(f"Destination already exists: {self.dst}")

    def execute(self):
        # Create parent directories if they don't exist
        self.dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(self.src), str(self.dst))
        self._executed = True

    def rollback(self):
        if self._executed and self.dst.exists():
            shutil.move(str(self.dst), str(self.src))

class FileCopy(BaseAction):
    def __init__(self, src, dst):
        self.src = Path(src)
        self.dst = Path(dst)
        self._created_file = False

    def validate(self):
        if not self.src.exists():
            raise FileNotFoundError(f"Source file not found: {self.src}")
        if self.dst.exists():
            raise FileExistsError(f"Destination already exists: {self.dst}")

    def execute(self):
        self.dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(self.src), str(self.dst))
        self._created_file = True

    def rollback(self):
        if self._created_file and self.dst.exists():
            os.remove(self.dst)

class FileWrite(BaseAction):
    """
    Handles atomic writes.
    The actual writing happens to a temp file immediately, 
    but the 'Action' is the renaming of temp -> final.
    """
    def __init__(self, temp_path, final_path):
        self.temp_path = Path(temp_path)
        self.final_path = Path(final_path)
        self._executed = False

    def validate(self):
        if self.final_path.exists():
            raise FileExistsError(f"Destination already exists: {self.final_path}")

    def execute(self):
        self.final_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(self.temp_path, self.final_path)
        self._executed = True

    def rollback(self):
        if self._executed and self.final_path.exists():
            os.remove(self.final_path)
        # If we didn't execute yet, clean up the temp file
        if self.temp_path.exists():
            os.remove(self.temp_path)