#!/usr/bin/env python3

import unittest
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the test modules
from tests.test_parse_time_string import TestParseTimeString
from tests.test_task import TestTask
from tests.test_socket_path import TestSocketPath
from tests.test_mock_server import TestMockServer
from tests.test_scheduling import TestScheduling, TestTaskServer


def create_test_suite():
    """Create a test suite containing all tests"""
    
    # Create a test suite
    test_suite = unittest.TestSuite()
    
    # Add test cases using TestLoader
    loader = unittest.TestLoader()
    test_suite.addTest(loader.loadTestsFromTestCase(TestParseTimeString))
    test_suite.addTest(loader.loadTestsFromTestCase(TestTask))
    test_suite.addTest(loader.loadTestsFromTestCase(TestSocketPath))
    test_suite.addTest(loader.loadTestsFromTestCase(TestMockServer))
    test_suite.addTest(loader.loadTestsFromTestCase(TestScheduling))
    test_suite.addTest(loader.loadTestsFromTestCase(TestTaskServer))
    
    return test_suite


if __name__ == "__main__":
    # Create a test runner
    runner = unittest.TextTestRunner(verbosity=2)
    
    # Run all tests
    result = runner.run(create_test_suite())
    
    # Exit with non-zero code if there were test failures
    sys.exit(not result.wasSuccessful()) 