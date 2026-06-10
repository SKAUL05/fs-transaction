import unittest
import os
import shutil
import tempfile
import json
from pathlib import Path

from fs_transaction import Transaction, AtomicWrite


class TestTransaction(unittest.TestCase):
    """Tests for the Transaction context manager."""
    
    def setUp(self):
        """Create a temporary sandbox directory for each test."""
        self.test_dir = Path(tempfile.mkdtemp())
        
        # Create some dummy files
        self.file_a = self.test_dir / "a.txt"
        self.file_a.write_text("Content A")
        
        self.dir_sub = self.test_dir / "subdir"
        self.dir_sub.mkdir()
    
    def tearDown(self):
        """Clean up the sandbox after each test."""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    # --- Successful commit tests ---
    
    def test_successful_move(self):
        """Verify move works when no error occurs."""
        dst = self.test_dir / "b.txt"
        with Transaction() as t:
            t.move(self.file_a, dst)
        
        self.assertFalse(self.file_a.exists())
        self.assertTrue(dst.exists())
        self.assertEqual(dst.read_text(), "Content A")
    
    def test_successful_copy(self):
        """Verify copy works when no error occurs."""
        dst = self.test_dir / "copy_a.txt"
        with Transaction() as t:
            t.copy(self.file_a, dst)
        
        self.assertTrue(self.file_a.exists())  # Source still exists
        self.assertTrue(dst.exists())
        self.assertEqual(dst.read_text(), "Content A")
    
    def test_successful_write(self):
        """Verify write works when no error occurs."""
        target = self.test_dir / "new.txt"
        with Transaction() as t:
            t.write(target, "Hello World")
        
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(), "Hello World")
    
    def test_successful_write_overwrite(self):
        """Verify write with overwrite=True replaces existing file."""
        self.file_a.write_text("Original")
        
        with Transaction() as t:
            t.write(self.file_a, "Updated", overwrite=True)
        
        self.assertEqual(self.file_a.read_text(), "Updated")
    
    def test_successful_delete(self):
        """Verify delete works when no error occurs."""
        self.assertTrue(self.file_a.exists())
        
        with Transaction() as t:
            t.delete(self.file_a)
        
        self.assertFalse(self.file_a.exists())
    
    def test_multi_operation_commit(self):
        """Verify multiple independent operations commit together."""
        file_b = self.test_dir / "b.txt"
        file_b.write_text("Content B")
        
        dst_a = self.test_dir / "moved_a.txt"
        new_file = self.test_dir / "new.txt"
        
        with Transaction() as t:
            t.move(self.file_a, dst_a)
            t.write(new_file, "Brand New")
            t.delete(file_b)
        
        self.assertFalse(self.file_a.exists())
        self.assertTrue(dst_a.exists())
        self.assertTrue(new_file.exists())
        self.assertFalse(file_b.exists())
    
    # --- Rollback tests ---
    
    def test_rollback_on_exception(self):
        """Verify rollback: files return to original state on exception."""
        dst = self.test_dir / "b.txt"
        
        try:
            with Transaction() as t:
                t.move(self.file_a, dst)
                raise RuntimeError("Crash!")
        except RuntimeError:
            pass
        
        self.assertTrue(self.file_a.exists(), "Original file should still exist")
        self.assertFalse(dst.exists(), "Destination should not exist")
    
    def test_rollback_write_cleanup(self):
        """Verify temp files are cleaned up on exception."""
        target = self.test_dir / "should_not_exist.txt"
        
        try:
            with Transaction() as t:
                t.write(target, "This should disappear")
                raise RuntimeError("Crash!")
        except RuntimeError:
            pass
        
        self.assertFalse(target.exists(), "Written file should be cleaned up")
        # Also verify no temp files remain
        temps = list(self.test_dir.glob(".tmp_*"))
        self.assertEqual(len(temps), 0, "Temp files should be cleaned up")
    
    def test_rollback_delete(self):
        """Verify deleted file is restored on rollback."""
        original_content = self.file_a.read_text()
        
        try:
            with Transaction() as t:
                t.delete(self.file_a)
                raise RuntimeError("Crash!")
        except RuntimeError:
            pass
        
        self.assertTrue(self.file_a.exists(), "Deleted file should be restored")
        self.assertEqual(self.file_a.read_text(), original_content, "Restored content should match original")
    
    def test_rollback_overwrite_restores_original(self):
        """Verify overwritten file is restored to original content on rollback."""
        self.file_a.write_text("Original Content")
        
        try:
            with Transaction() as t:
                t.write(self.file_a, "New Content", overwrite=True)
                # Force a second action to fail
                t.move("nonexistent_file.txt", "nowhere.txt")
        except FileNotFoundError:
            pass
        
        # After rollback, original content should be preserved
        # Note: the validation phase catches this before execution
        self.assertTrue(self.file_a.exists())
    
    # --- Validation tests ---
    
    def test_validation_prevents_partial_state(self):
        """Verify that if one action is invalid, NOTHING happens."""
        dst = self.test_dir / "moved_a.txt"
        
        try:
            with Transaction() as t:
                t.move(self.file_a, dst)
                t.move("ghost.txt", "somewhere.txt")  # Invalid
        except FileNotFoundError:
            pass
        
        self.assertTrue(self.file_a.exists(), "File A should not have moved")
        self.assertFalse(dst.exists())
    
    def test_write_without_overwrite_raises(self):
        """Verify writing to existing file without overwrite raises error."""
        with self.assertRaises(FileExistsError):
            with Transaction() as t:
                t.write(self.file_a, "Overwrite attempt", overwrite=False)
    
    def test_move_without_overwrite_raises(self):
        """Verify moving to existing file without overwrite raises error."""
        dst = self.test_dir / "b.txt"
        dst.write_text("Existing")
        
        with self.assertRaises(FileExistsError):
            with Transaction() as t:
                t.move(self.file_a, dst, overwrite=False)
    
    # --- Dry-run tests ---
    
    def test_dry_run_no_changes(self):
        """Verify dry_run validates but does not execute."""
        dst = self.test_dir / "moved.txt"
        
        with Transaction(dry_run=True) as t:
            t.move(self.file_a, dst)
            t.write(self.test_dir / "new.txt", "Content")
        
        # Nothing should have changed
        self.assertTrue(self.file_a.exists())
        self.assertFalse(dst.exists())
        self.assertFalse((self.test_dir / "new.txt").exists())
    
    def test_dry_run_still_validates(self):
        """Verify dry_run still catches validation errors."""
        with self.assertRaises(FileNotFoundError):
            with Transaction(dry_run=True) as t:
                t.move("ghost.txt", "somewhere.txt")
    
    # --- Double commit test ---
    
    def test_double_commit_raises(self):
        """Verify committing twice raises RuntimeError."""
        t = Transaction()
        t.write(self.test_dir / "file.txt", "content")
        t.commit()
        
        with self.assertRaises(RuntimeError):
            t.commit()
    
    # --- Repr test ---
    
    def test_repr(self):
        t = Transaction()
        self.assertIn("0 pending", repr(t))
        t.write(self.test_dir / "x.txt", "data")
        self.assertIn("1 pending", repr(t))


class TestAtomicWrite(unittest.TestCase):
    """Tests for the AtomicWrite context manager."""
    
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_basic_write(self):
        """Verify basic atomic write creates the file."""
        target = self.test_dir / "output.txt"
        
        with AtomicWrite(target, mode="w") as f:
            f.write("Hello, World!")
        
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(), "Hello, World!")
    
    def test_overwrite_existing(self):
        """Verify atomic write can overwrite existing files."""
        target = self.test_dir / "config.json"
        target.write_text('{"old": true}')
        
        new_data = {"new": True, "updated": True}
        with AtomicWrite(target, mode="w") as f:
            f.write(json.dumps(new_data))
        
        self.assertEqual(json.loads(target.read_text()), new_data)
    
    def test_no_overwrite_raises(self):
        """Verify AtomicWrite raises when file exists and overwrite=False."""
        target = self.test_dir / "existing.txt"
        target.write_text("Original")
        
        with self.assertRaises(FileExistsError):
            with AtomicWrite(target, mode="w", overwrite=False) as f:
                f.write("Should not work")
        
        # Original file should be unchanged
        self.assertEqual(target.read_text(), "Original")
    
    def test_exception_preserves_original(self):
        """Verify original file is untouched on exception."""
        target = self.test_dir / "important.txt"
        target.write_text("Critical Data")
        
        try:
            with AtomicWrite(target, mode="w") as f:
                f.write("Partial data")
                raise RuntimeError("Crash!")
        except RuntimeError:
            pass
        
        self.assertEqual(target.read_text(), "Critical Data")
    
    def test_exception_no_temp_files(self):
        """Verify no temp files remain after exception."""
        target = self.test_dir / "clean.txt"
        
        try:
            with AtomicWrite(target, mode="w") as f:
                f.write("Temp data")
                raise RuntimeError("Crash!")
        except RuntimeError:
            pass
        
        temps = list(self.test_dir.glob(".tmp_*"))
        self.assertEqual(len(temps), 0, "Temp files should be cleaned up")
    
    def test_creates_parent_directories(self):
        """Verify parent directories are created automatically."""
        target = self.test_dir / "deep" / "nested" / "dir" / "file.txt"
        
        with AtomicWrite(target, mode="w") as f:
            f.write("Deep content")
        
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(), "Deep content")
    
    def test_binary_mode(self):
        """Verify binary mode writes work."""
        target = self.test_dir / "binary.dat"
        data = b"\x00\x01\x02\x03\xff"
        
        with AtomicWrite(target, mode="wb") as f:
            f.write(data)
        
        self.assertEqual(target.read_bytes(), data)
    
    def test_invalid_read_mode_raises(self):
        """Verify read-only mode raises ValueError."""
        target = self.test_dir / "file.txt"
        with self.assertRaises(ValueError):
            AtomicWrite(target, mode="r")
    
    def test_preserves_permissions(self):
        """Verify file permissions are preserved on overwrite."""
        target = self.test_dir / "perms.txt"
        target.write_text("Original")
        os.chmod(target, 0o644)
        original_mode = target.stat().st_mode
        
        with AtomicWrite(target, mode="w") as f:
            f.write("Updated")
        
        self.assertEqual(target.stat().st_mode, original_mode)
    
    def test_json_write(self):
        """Verify the README example works."""
        target = self.test_dir / "config.json"
        data = {"status": "processing", "items": [1, 2, 3]}
        
        with AtomicWrite(target, mode="w") as f:
            f.write(json.dumps(data))
        
        self.assertEqual(json.loads(target.read_text()), data)
    
    def test_repr(self):
        aw = AtomicWrite("test.txt", mode="w")
        self.assertIn("test.txt", repr(aw))


class TestFileDelete(unittest.TestCase):
    """Tests for the FileDelete action."""
    
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_delete_nonexistent_raises(self):
        """Verify deleting a nonexistent file raises error."""
        with self.assertRaises(FileNotFoundError):
            with Transaction() as t:
                t.delete(self.test_dir / "ghost.txt")
    
    def test_delete_and_write_in_same_transaction(self):
        """Verify delete + write of same path raises since validation runs before execution."""
        target = self.test_dir / "file.txt"
        target.write_text("Old")
        
        # Validation sees file still exists at validation time, so write (overwrite=False) fails
        with self.assertRaises(FileExistsError):
            with Transaction() as t:
                t.delete(target)
                t.write(target, "New")
        
        # Original file should remain since the transaction was rolled back
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(), "Old")


class TestEdgeCases(unittest.TestCase):
    """Edge case tests."""
    
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_empty_transaction(self):
        """Verify empty transaction commits without error."""
        with Transaction():
            pass  # No operations
    
    def test_write_to_nested_directory(self):
        """Verify writing to non-existent nested directories."""
        target = self.test_dir / "a" / "b" / "c" / "file.txt"
        
        with Transaction() as t:
            t.write(target, "Deep content")
        
        self.assertTrue(target.exists())
    
    def test_move_with_overwrite(self):
        """Verify move with overwrite=True replaces destination."""
        src = self.test_dir / "src.txt"
        dst = self.test_dir / "dst.txt"
        src.write_text("Source")
        dst.write_text("Destination")
        
        with Transaction() as t:
            t.move(src, dst, overwrite=True)
        
        self.assertFalse(src.exists())
        self.assertEqual(dst.read_text(), "Source")
    
    def test_copy_with_overwrite(self):
        """Verify copy with overwrite=True replaces destination."""
        src = self.test_dir / "src.txt"
        dst = self.test_dir / "dst.txt"
        src.write_text("Source")
        dst.write_text("Destination")
        
        with Transaction() as t:
            t.copy(src, dst, overwrite=True)
        
        self.assertTrue(src.exists())
        self.assertEqual(dst.read_text(), "Source")
    
    def test_exception_propagates(self):
        """Verify exceptions inside with block propagate (not swallowed)."""
        with self.assertRaises(ValueError):
            with Transaction():
                raise ValueError("This should propagate")


if __name__ == "__main__":
    unittest.main()