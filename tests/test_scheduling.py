import unittest
import datetime
import sys
import os
import json
import tempfile

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.run_later_client import parse_time_string, schedule_task
from src.run_later_server import Task, TaskServer
from tests.test_mock_server import MockServer


class TestScheduling(unittest.TestCase):
    def setUp(self):
        self.mock_server = MockServer()
        # Set a mock response with target_time to avoid KeyError
        self.mock_server.set_response({
            'status': 'success',
            'task_id': 'mock-task-id',
            'target_time': datetime.datetime.now().isoformat(),
            'message': 'Task scheduled'
        })
        self.mock_server.start()
    
    def tearDown(self):
        self.mock_server.stop()
    
    def test_schedule_task_message_format(self):
        """Test that the schedule_task function sends the correct message format"""
        
        # Define test data
        test_command = "echo 'Hello, world!'"
        test_delay_str = "5 minutes"
        expected_delay_seconds = 5 * 60
        
        # Clear any previously received messages
        self.mock_server.received_messages = []
        
        # Schedule the task
        schedule_task(test_command, test_delay_str, socket_path=self.mock_server.socket_path)
        
        # The schedule_task function might send multiple messages, such as a check if server is running
        # Find the schedule message among the received messages
        schedule_messages = [msg for msg in self.mock_server.received_messages if msg.get('action') == 'schedule']
        self.assertEqual(len(schedule_messages), 1, "Should have exactly one schedule message")
        message = schedule_messages[0]
        
        # Check message format
        self.assertEqual(message['action'], 'schedule')
        self.assertEqual(message['command'], test_command)
        
        # Check that the delay was calculated correctly
        self.assertIn('delay_seconds', message)
        delay_seconds = message['delay_seconds']
        
        # Allow for a small margin of error (1 second)
        self.assertTrue(abs(delay_seconds - expected_delay_seconds) <= 1)


class TestTaskServer(unittest.TestCase):
    def setUp(self):
        # Create a temporary socket path for testing
        self.temp_socket_path = os.path.join(tempfile.mkdtemp(), "test_server.sock")
        
        # Create a test TaskServer with the temporary socket
        self.server = TaskServer(self.temp_socket_path)
        # Don't start the server - we'll just test the process_message directly
    
    def tearDown(self):
        # Clean up server 
        if hasattr(self.server, 'running') and self.server.running:
            self.server.stop()
        
        # If the socket file still exists, remove it
        if os.path.exists(self.temp_socket_path):
            os.unlink(self.temp_socket_path)
    
    def test_handle_schedule(self):
        """Test that the TaskServer can handle schedule messages"""
        
        # Create a schedule message
        command = "echo 'Test command'"
        delay_seconds = 300  # 5 minutes
        
        message = {
            'action': 'schedule',
            'command': command,
            'delay_seconds': delay_seconds
        }
        
        # Process the message directly without starting the server
        response = self.server.process_message(message)
        
        # Check the response
        self.assertEqual(response['status'], 'success')
        self.assertIn('task_id', response)
        
        # Check that the task was added to the server's task list
        task_id = response['task_id']
        self.assertIn(task_id, self.server.tasks)
        
        # Check the task properties
        task = self.server.tasks[task_id]
        self.assertEqual(task.command, command)
        self.assertFalse(task.completed)


if __name__ == "__main__":
    unittest.main() 