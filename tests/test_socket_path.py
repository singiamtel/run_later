import unittest
import os
import sys
import tempfile

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.run_later_client import get_server_socket_path as client_get_socket_path
from src.run_later_server import get_server_socket_path as server_get_socket_path


class TestSocketPath(unittest.TestCase):
    def setUp(self):
        # Save original environment variables
        self.original_xdg_runtime_dir = os.environ.get('XDG_RUNTIME_DIR')
    
    def tearDown(self):
        # Restore original environment variables
        if self.original_xdg_runtime_dir:
            os.environ['XDG_RUNTIME_DIR'] = self.original_xdg_runtime_dir
        elif 'XDG_RUNTIME_DIR' in os.environ:
            del os.environ['XDG_RUNTIME_DIR']
    
    def test_client_get_socket_path_with_xdg_runtime_dir(self):
        # Test with XDG_RUNTIME_DIR set
        test_xdg_dir = tempfile.mkdtemp()
        os.environ['XDG_RUNTIME_DIR'] = test_xdg_dir
        
        socket_path = client_get_socket_path()
        expected_path = os.path.join(test_xdg_dir, "run_later.sock")
        
        self.assertEqual(socket_path, expected_path)
    
    def test_client_get_socket_path_without_xdg_runtime_dir(self):
        # Test without XDG_RUNTIME_DIR
        if 'XDG_RUNTIME_DIR' in os.environ:
            del os.environ['XDG_RUNTIME_DIR']
        
        socket_path = client_get_socket_path()
        expected_path = os.path.join(tempfile.gettempdir(), f"run_later-{os.getuid()}", "run_later.sock")
        
        self.assertEqual(socket_path, expected_path)
    
    def test_client_and_server_return_same_path(self):
        # Test that client and server return the same socket path
        
        # With XDG_RUNTIME_DIR
        test_xdg_dir = tempfile.mkdtemp()
        os.environ['XDG_RUNTIME_DIR'] = test_xdg_dir
        
        client_path = client_get_socket_path()
        server_path = server_get_socket_path()
        
        self.assertEqual(client_path, server_path)
        
        # Without XDG_RUNTIME_DIR
        if 'XDG_RUNTIME_DIR' in os.environ:
            del os.environ['XDG_RUNTIME_DIR']
        
        client_path = client_get_socket_path()
        server_path = server_get_socket_path()
        
        self.assertEqual(client_path, server_path)


if __name__ == "__main__":
    unittest.main() 