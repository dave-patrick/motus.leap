import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import tempfile
import shutil
from datetime import datetime

# Add the parent directory to sys.path so we can import scheduler and server
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import scheduler
import server

class TestScheduler(unittest.TestCase):
    def setUp(self):
        # Create a temp directory for settings and logs to avoid polluting the workspace
        self.temp_dir = tempfile.mkdtemp()
        
        # Save original scheduler values to restore later
        self.orig_file = getattr(scheduler, '__file__', None)
        self.orig_datetime = scheduler.datetime
        self.orig_time = scheduler.time
        self.orig_subprocess = scheduler.subprocess
        self.orig_requests = scheduler.requests
        self.orig_thread = scheduler.threading.Thread
        
        # Mock settings.json in the temp directory so webhook notifications return early
        self.settings_path = os.path.join(self.temp_dir, "settings.json")
        with open(self.settings_path, "w") as f:
            f.write('{"notification_webhook": ""}')
            
        # Point scheduler's __file__ to the temp directory
        scheduler.__file__ = os.path.join(self.temp_dir, "scheduler.py")
        
        # Mock requests, time
        scheduler.requests = MagicMock()
        scheduler.time = MagicMock()
        
        # Setup mock subprocess
        scheduler.subprocess = MagicMock()
        self.mock_completed_proc = MagicMock()
        self.mock_completed_proc.stdout = "mock stdout\n"
        self.mock_completed_proc.stderr = "mock stderr\n"
        scheduler.subprocess.run.return_value = self.mock_completed_proc
        
        # Ensure active_job is reset
        scheduler.active_job = None

    def tearDown(self):
        # Restore scheduler originals
        scheduler.__file__ = self.orig_file
        scheduler.datetime = self.orig_datetime
        scheduler.time = self.orig_time
        scheduler.subprocess = self.orig_subprocess
        scheduler.requests = self.orig_requests
        scheduler.threading.Thread = self.orig_thread
        scheduler.active_job = None
        
        # Clean up temp directory
        shutil.rmtree(self.temp_dir)

    def test_pipeline_sequence_success(self):
        """Test that run_pipeline_sequence runs the 4 steps in the correct order."""
        # Call the pipeline
        scheduler.run_pipeline_sequence()
        
        # Verify it ran exactly 4 subprocesses
        self.assertEqual(scheduler.subprocess.run.call_count, 4)
        
        # Check command order
        calls = scheduler.subprocess.run.call_args_list
        self.assertIn("scan", calls[0][0][0])
        self.assertIn("auto-sort", calls[1][0][0])
        self.assertIn("generate_maintenance.py", calls[2][0][0])
        self.assertIn("apply_maintenance.py", calls[3][0][0])
        self.assertIn("--force", calls[3][0][0])
        
        # Verify active_job is cleared
        self.assertIsNone(scheduler.active_job)

    def test_pipeline_lock_prevents_duplicate_runs(self):
        """Test that if active_job is set, run_pipeline_sequence returns immediately without running steps."""
        scheduler.active_job = "running_some_job"
        
        scheduler.run_pipeline_sequence()
        
        # Subprocess run should not be called
        scheduler.subprocess.run.assert_not_called()
        
        # active_job should remain unchanged
        self.assertEqual(scheduler.active_job, "running_some_job")

    def test_time_trigger_logic(self):
        """Test that scheduler triggers runs exactly at 5 PM and 11 PM, and only once per hour."""
        # We will feed a list of times to datetime.now() and verify when threading.Thread is called
        test_times = [
            datetime(2026, 5, 20, 16, 59, 0),  # Not trigger
            datetime(2026, 5, 20, 17, 0, 0),   # Trigger (5 PM)
            datetime(2026, 5, 20, 17, 0, 30),  # Not trigger (already run this hour)
            datetime(2026, 5, 20, 17, 1, 0),   # Not trigger
            datetime(2026, 5, 20, 22, 59, 30), # Not trigger
            datetime(2026, 5, 20, 23, 0, 0),   # Trigger (11 PM)
            datetime(2026, 5, 20, 23, 0, 30),  # Not trigger
            datetime(2026, 5, 21, 17, 0, 0),   # Trigger (next day 5 PM)
        ]
        
        times_iter = iter(test_times)
        
        # Mock datetime class
        class MockDatetime:
            @staticmethod
            def now():
                try:
                    return next(times_iter)
                except StopIteration:
                    # Raise exception to break the infinite while loop in scheduler
                    raise KeyboardInterrupt("Finished times")
        
        scheduler.datetime = MockDatetime
        
        # Mock Thread creation
        mock_thread = MagicMock()
        scheduler.threading.Thread = mock_thread
        
        # Run the loop
        try:
            scheduler.run_scheduler_loop()
        except KeyboardInterrupt:
            pass
            
        # Verify thread was started 3 times (5 PM, 11 PM, next day 5 PM)
        self.assertEqual(mock_thread.call_count, 3)
        for call in mock_thread.call_args_list:
            self.assertEqual(call[1]['target'], scheduler.run_pipeline_sequence)
            self.assertEqual(call[1]['daemon'], True)

    def test_locking_coordination(self):
        """Test coordination between TaskManager and scheduler.
        
        Verify that running a task in TaskManager locks the scheduler from running,
        and that they share the active_job state correctly.
        """
        # Patch subprocess.Popen in server.py's task_manager to avoid running real command
        mock_popen = MagicMock()
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc
        
        # We need to mock sys.executable, builtins.open, etc. if we call run_task directly.
        # Let's mock subprocess.Popen in server
        with patch('server.subprocess.Popen', mock_popen), \
             patch('server.open', MagicMock()):
             
            # 1. Start a task via TaskManager
            success, msg = server.task_manager.run_task("scan", ["cli.py", "scan"])
            self.assertTrue(success)
            self.assertEqual(server.task_manager.active_job, "scan")
            
            # 2. Verify scheduler.active_job is set to "scan"
            self.assertEqual(scheduler.active_job, "scan")
            
            # 3. Trigger scheduler's pipeline. It should skip because scheduler.active_job is "scan"
            scheduler.run_pipeline_sequence()
            scheduler.subprocess.run.assert_not_called()
            
            # 4. Simulate task completion via _monitor_process
            server.task_manager._monitor_process(mock_proc, "scan", MagicMock())
            
            # 5. Verify that active_job is cleared in both places
            self.assertIsNone(server.task_manager.active_job)
            self.assertIsNone(scheduler.active_job)

if __name__ == "__main__":
    unittest.main()
