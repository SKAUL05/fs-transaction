import os
import uuid
from pathlib import Path
from .actions import FileMove, FileCopy, FileWrite

class Transaction:
    def __init__(self):
        self._actions = []
        self._temp_files = [] # Track temps for cleanup if script crashes
    
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            # Code block failed (Python error). 
            # Clean up any temp files created during preparation.
            self._cleanup_temp_files()
            return False # Propagate exception
        
        # Code block succeeded. Attempt commit.
        self.commit()
        return True

    def move(self, src, dst):
        self._actions.append(FileMove(src, dst))

    def copy(self, src, dst):
        self._actions.append(FileCopy(src, dst))

    def write(self, dst, content, mode='w'):
        """
        Writes to a temporary file immediately. 
        Queues a rename operation for the commit phase.
        """
        dst_path = Path(dst)
        # Create a hidden temp file in the same directory to ensure atomic move later
        # If directory doesn't exist, we must create it now or write to global temp
        # For safety, we write to a .tmp file alongside the destination
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        
        temp_name = f".tmp_{uuid.uuid4().hex}_{dst_path.name}"
        temp_path = dst_path.parent / temp_name
        
        with open(temp_path, mode) as f:
            f.write(content)
            
        self._temp_files.append(temp_path)
        self._actions.append(FileWrite(temp_path, dst_path))

    def commit(self):
        # 1. Validation Phase
        for action in self._actions:
            action.validate()

        # 2. Execution Phase
        completed = []
        try:
            for action in self._actions:
                action.execute()
                completed.append(action)
        except Exception as e:
            # 3. Rollback Phase
            print(f"Transaction failed: {e}. Rolling back {len(completed)} actions...")
            for action in reversed(completed):
                try:
                    action.rollback()
                except Exception as rb_e:
                    print(f"CRITICAL: Rollback failed for {action}: {rb_e}")
            self._cleanup_temp_files()
            raise e
            
        # Success cleanup
        self._temp_files = [] 

    def _cleanup_temp_files(self):
        """Clean up staging files if transaction aborts."""
        for f in self._temp_files:
            if f.exists():
                try:
                    os.remove(f)
                except OSError:
                    pass