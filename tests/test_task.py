import unittest
import datetime
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.run_later_server import Task


class TestTask(unittest.TestCase):
    def test_init(self):
        # Test with required params
        now = datetime.datetime.now()
        task = Task("echo test", now)
        self.assertEqual(task.command, "echo test")
        self.assertEqual(task.target_time, now)
        self.assertIsNotNone(task.task_id)
        self.assertFalse(task.completed)
        self.assertIsNone(task.exit_code)
        self.assertIsNone(task.completion_time)
        
        # Test with all params
        task_id = "test-id"
        completion_time = now - datetime.timedelta(minutes=5)
        task = Task(
            "ls -la", 
            now, 
            task_id=task_id, 
            completed=True, 
            exit_code=0,
            completion_time=completion_time
        )
        self.assertEqual(task.command, "ls -la")
        self.assertEqual(task.target_time, now)
        self.assertEqual(task.task_id, task_id)
        self.assertTrue(task.completed)
        self.assertEqual(task.exit_code, 0)
        self.assertEqual(task.completion_time, completion_time)
    
    def test_to_dict(self):
        now = datetime.datetime.now()
        completion_time = now - datetime.timedelta(minutes=5)
        task = Task(
            "ls -la", 
            now, 
            task_id="test-id", 
            completed=True, 
            exit_code=0,
            completion_time=completion_time
        )
        
        task_dict = task.to_dict()
        self.assertEqual(task_dict["command"], "ls -la")
        self.assertEqual(task_dict["target_time"], now.isoformat())
        self.assertEqual(task_dict["task_id"], "test-id")
        self.assertTrue(task_dict["completed"])
        self.assertEqual(task_dict["exit_code"], 0)
        self.assertEqual(task_dict["completion_time"], completion_time.isoformat())
        
        # Test without optional fields
        task = Task("echo test", now)
        task_dict = task.to_dict()
        self.assertEqual(task_dict["command"], "echo test")
        self.assertEqual(task_dict["target_time"], now.isoformat())
        self.assertIsNotNone(task_dict["task_id"])
        self.assertFalse(task_dict["completed"])
        self.assertNotIn("exit_code", task_dict)
        self.assertNotIn("completion_time", task_dict)
    
    def test_from_dict(self):
        now = datetime.datetime.now()
        completion_time = now - datetime.timedelta(minutes=5)
        
        # Complete task data
        task_data = {
            "command": "ls -la",
            "target_time": now.isoformat(),
            "task_id": "test-id",
            "completed": True,
            "exit_code": 0,
            "completion_time": completion_time.isoformat()
        }
        
        task = Task.from_dict(task_data)
        self.assertEqual(task.command, "ls -la")
        self.assertEqual(task.target_time, now)
        self.assertEqual(task.task_id, "test-id")
        self.assertTrue(task.completed)
        self.assertEqual(task.exit_code, 0)
        self.assertEqual(task.completion_time, completion_time)
        
        # Minimal task data
        task_data = {
            "command": "echo test",
            "target_time": now.isoformat(),
            "task_id": "test-id-2"
        }
        
        task = Task.from_dict(task_data)
        self.assertEqual(task.command, "echo test")
        self.assertEqual(task.target_time, now)
        self.assertEqual(task.task_id, "test-id-2")
        self.assertFalse(task.completed)
        self.assertIsNone(task.exit_code)
        self.assertIsNone(task.completion_time)


if __name__ == "__main__":
    unittest.main() 