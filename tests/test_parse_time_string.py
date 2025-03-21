import unittest
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.run_later_client import parse_time_string


class TestParseTimeString(unittest.TestCase):
    def test_parse_seconds(self):
        self.assertEqual(parse_time_string("30 seconds"), 30)
        self.assertEqual(parse_time_string("1 second"), 1)
        self.assertEqual(parse_time_string("  45  seconds  "), 45)
    
    def test_parse_minutes(self):
        self.assertEqual(parse_time_string("5 minutes"), 5 * 60)
        self.assertEqual(parse_time_string("1 minute"), 60)
        self.assertEqual(parse_time_string("  10  minutes  "), 10 * 60)
    
    def test_parse_hours(self):
        self.assertEqual(parse_time_string("2 hours"), 2 * 3600)
        self.assertEqual(parse_time_string("1 hour"), 3600)
        self.assertEqual(parse_time_string("  3  hours  "), 3 * 3600)
    
    def test_invalid_format(self):
        with self.assertRaises(ValueError):
            parse_time_string("invalid")
        
        with self.assertRaises(ValueError):
            parse_time_string("5m")
        
        with self.assertRaises(ValueError):
            parse_time_string("2h30m")
    
    def test_unknown_unit(self):
        with self.assertRaises(ValueError):
            parse_time_string("5 days")


if __name__ == "__main__":
    unittest.main() 