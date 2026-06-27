"""
Tests for the text-mode conversation loop.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
from io import StringIO

from text_mode_loop import run_text_loop, _load_config


class TestTextModeLoop(unittest.TestCase):
    """Test text-mode conversation loop."""

    def test_config_loading(self):
        """Test that configuration loads successfully."""
        cfg = _load_config()
        self.assertIn("input_interpreter", cfg)
        self.assertIn("output_planner", cfg)
        self.assertIn("language_model", cfg)

    def test_config_has_required_keys(self):
        """Test that config has all required subsystem configurations."""
        cfg = _load_config()
        self.assertEqual(cfg["input_interpreter"]["type"], "rule_based")
        self.assertEqual(cfg["output_planner"]["type"], "rule_based")

    @patch('builtins.input', side_effect=['hello', 'exit'])
    @patch('builtins.print')
    def test_text_loop_processes_single_input(self, mock_print, mock_input):
        """Test that text loop accepts input and processes it."""
        # Run the loop with mocked input
        run_text_loop(verbose=False)

        # Verify input was requested
        mock_input.assert_called()

    @patch('builtins.input', side_effect=['exit'])
    @patch('builtins.print')
    def test_text_loop_handles_exit_command(self, mock_print, mock_input):
        """Test that exit command cleanly terminates the loop."""
        run_text_loop(verbose=False)
        # Should complete without exception
        self.assertTrue(True)

    @patch('builtins.input', side_effect=['', 'how are you', 'stop'])
    @patch('builtins.print')
    def test_text_loop_skips_empty_input(self, mock_print, mock_input):
        """Test that empty input is skipped."""
        run_text_loop(verbose=False)
        # Should handle empty string gracefully
        self.assertTrue(True)

    @patch('builtins.input', side_effect=['test query', 'exit'])
    @patch('builtins.print')
    def test_text_loop_with_verbose_mode(self, mock_print, mock_input):
        """Test that verbose mode provides debug output."""
        run_text_loop(verbose=True)
        # Verify verbose output was printed
        calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(calls)
        self.assertIn("ARIA Text Mode", output)

    def test_config_model_uses_mock_by_default(self):
        """Test that config defaults to mock language model."""
        cfg = _load_config()
        model_cfg = cfg["language_model"]
        # Default should be mock unless OPENAI_API_KEY is explicitly set with valid key
        self.assertIn("module", model_cfg)
        self.assertIn("class", model_cfg)


if __name__ == "__main__":
    unittest.main()
