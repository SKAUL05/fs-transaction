import unittest
import os
import shutil
from pathlib import Path
from fs_transaction import Transaction

class TestFsTransaction(unittest.TestCase):
    def setUp(self):
        """Create a temporary sandbox directory for each test."""
        self.test_dir = Path("test_sandbox")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir()
        
        # Create some dummy files
        self.file_a = self.test_dir / "a.txt"
        self.file_a.write_text("Content A")
        
        self.dir_sub = self.test_dir / "subdir"
        self.dir_sub.mkdir()

    def tearDown(self):
        """Clean up the sandbox after each test."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_successful_commit(self):
        """Verify operations work when no error occurs."""
        dst = self.test_dir / "b.txt"
        
        with Transaction() as t:
            t.move(self.file_a, dst)
            t.write(self.test_dir / "new.txt", "New Content")
            
        self.assertFalse(self.file_a.exists())
        self.assertTrue(dst.exists())
        self.assertTrue((self.test_dir / "new.txt").exists())

    def test_rollback_on_error(self):
        """Verify rollback works: files should return to original state."""
        dst = self.test_dir / "b.txt"
        
        # Capture the state before transaction
        self.assertTrue(self.file_a.exists())
        self.assertFalse(dst.exists())

        try:
            with Transaction() as t:
                t.move(self.file_a, dst)
                # Intentionally raise an error to trigger rollback
                raise RuntimeError("Crash!")
        except RuntimeError:
            pass # Expected

        # ASSERTIONS: State should be exactly as it was before
        self.assertTrue(self.file_a.exists(), "Original file should be restored")
        self.assertFalse(dst.exists(), "Destination file should be gone")

    def test_rollback_write(self):
        """Verify that written files are removed on rollback."""
        target_file = self.test_dir / "should_not_exist.txt"
        
        try:
            with Transaction() as t:
                t.write(target_file, "This should disappear")
                raise RuntimeError("Crash!")
        except RuntimeError:
            pass

        self.assertFalse(target_file.exists(), "Written file should be cleaned up")

    def test_validation_prevents_partial_state(self):
        """Verify that if one action is invalid, NOTHING happens."""
        # 'a.txt' exists, but 'ghost.txt' does not.
        # The transaction should fail validation before moving a.txt
        dst = self.test_dir / "moved_a.txt"
        
        try:
            with Transaction() as t:
                t.move(self.file_a, dst)
                t.move("ghost.txt", "somewhere.txt") # This is invalid
        except FileNotFoundError:
            pass

        # Since 'ghost.txt' failed validation, 'a.txt' should NOT have moved.
        self.assertTrue(self.file_a.exists(), "File A moved despite validation error!")
        self.assertFalse(dst.exists())

if __name__ == "__main__":
    unittest.main()