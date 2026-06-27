"""
Tests for ALang serialization utilities.
"""

import unittest
from output_planner.alang_serialization import alang_to_str


class TestAlangToStr(unittest.TestCase):
    """Test ALang term rendering."""

    def test_simple_string(self):
        """Test rendering a plain string."""
        self.assertEqual(alang_to_str("hello"), '"hello"')

    def test_number(self):
        """Test rendering a number."""
        self.assertEqual(alang_to_str(42), "42")

    def test_simple_dict_with_keyword(self):
        """Test rendering a dict with a keyword constructor."""
        term = {":inform": "Hello"}
        self.assertEqual(alang_to_str(term), ':inform "Hello"')

    def test_nested_dict(self):
        """Test rendering nested ALang terms."""
        term = {":warning": {":level": 3}}
        result = alang_to_str(term)
        self.assertIn(":warning", result)
        self.assertIn(":level", result)

    def test_list_of_terms(self):
        """Test rendering a list."""
        term = [":atom1", ":atom2"]
        result = alang_to_str(term)
        self.assertIn("[", result)
        self.assertIn("]", result)

    def test_complex_nested_structure(self):
        """Test rendering a complex nested structure."""
        term = {":query": [{":field": "name"}, {":value": "test"}]}
        result = alang_to_str(term)
        self.assertIn(":query", result)
        self.assertIn(":field", result)
        self.assertIn(":value", result)

    def test_dict_without_keyword_fallback(self):
        """Test rendering a dict without keyword keys."""
        term = {"key1": "value1", "key2": "value2"}
        result = alang_to_str(term)
        self.assertIn("key1", result)
        self.assertIn("value1", result)

    def test_empty_list(self):
        """Test rendering an empty list."""
        self.assertEqual(alang_to_str([]), "[]")

    def test_empty_dict(self):
        """Test rendering an empty dict."""
        self.assertEqual(alang_to_str({}), "{}")


if __name__ == "__main__":
    unittest.main()
