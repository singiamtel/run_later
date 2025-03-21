import unittest
import json
import os
import socket
import sys
import tempfile
import threading
import time

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.run_later_client import send_message_to_server


class MockServer:
    def __init__(self):
        # Use a temporary unique socket path
        self.socket_path = os.path.join(tempfile.mkdtemp(), "test_run_later.sock")
        self.server_socket = None
        self.thread = None
        self.running = False
        self.received_messages = []
        self.response_to_send = {'status': 'success'}
    
    def start(self):
        # Make sure the socket doesn't already exist
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        # Create a Unix domain socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        self.server_socket.listen(5)
        
        # Start the server thread
        self.running = True
        self.thread = threading.Thread(target=self._server_loop)
        self.thread.daemon = True
        self.thread.start()
        
        # Give the server a moment to start
        time.sleep(0.1)
    
    def set_response(self, response):
        self.response_to_send = response
    
    def _server_loop(self):
        while self.running:
            try:
                # Set a timeout so we can check if we should stop
                self.server_socket.settimeout(0.5)
                try:
                    client, _ = self.server_socket.accept()
                except socket.timeout:
                    continue
                
                # Reset timeout for communication
                client.settimeout(None)
                
                # Handle the client
                self._handle_client(client)
            except Exception as e:
                print(f"Mock server error: {e}")
                break
    
    def _handle_client(self, client):
        try:
            # Receive data
            data = b""
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                data += chunk
            
            if data:
                # Parse the message
                message = json.loads(data.decode('utf-8'))
                self.received_messages.append(message)
                
                # Send response
                client.sendall(json.dumps(self.response_to_send).encode('utf-8'))
        finally:
            client.close()
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        
        if self.server_socket:
            self.server_socket.close()
        
        # Clean up the socket file
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)


class TestMockServer(unittest.TestCase):
    def setUp(self):
        self.mock_server = MockServer()
        self.mock_server.start()
    
    def tearDown(self):
        self.mock_server.stop()
    
    def test_send_message(self):
        # Test sending a message to the mock server
        test_message = {'action': 'test', 'data': 'test_data'}
        
        # Set a custom response
        expected_response = {'status': 'success', 'data': 'response_data'}
        self.mock_server.set_response(expected_response)
        
        # Send the message
        response = send_message_to_server(test_message, self.mock_server.socket_path)
        
        # Check that the server received the message
        self.assertEqual(len(self.mock_server.received_messages), 1)
        self.assertEqual(self.mock_server.received_messages[0], test_message)
        
        # Check that we got the expected response
        self.assertEqual(response, expected_response)
    
    def test_multiple_messages(self):
        # Test sending multiple messages
        test_messages = [
            {'action': 'test1', 'data': 'test_data_1'},
            {'action': 'test2', 'data': 'test_data_2'},
            {'action': 'test3', 'data': 'test_data_3'}
        ]
        
        expected_responses = [
            {'status': 'success', 'data': 'response_1'},
            {'status': 'success', 'data': 'response_2'},
            {'status': 'success', 'data': 'response_3'}
        ]
        
        for i, test_message in enumerate(test_messages):
            # Set the response for this message
            self.mock_server.set_response(expected_responses[i])
            
            # Send the message
            response = send_message_to_server(test_message, self.mock_server.socket_path)
            
            # Check that we got the expected response
            self.assertEqual(response, expected_responses[i])
        
        # Check that the server received all messages in order
        self.assertEqual(len(self.mock_server.received_messages), len(test_messages))
        for i, message in enumerate(test_messages):
            self.assertEqual(self.mock_server.received_messages[i], message)


if __name__ == "__main__":
    unittest.main() 