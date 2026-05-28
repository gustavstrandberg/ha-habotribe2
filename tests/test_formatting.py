"""Tests for HABO Tribe2 formatting helpers."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
import unittest


def load_formatting_module():
    """Load formatting.py without requiring Home Assistant to be installed."""

    path = Path(__file__).parents[1] / "custom_components/habo_tribe2/formatting.py"
    spec = spec_from_file_location("habo_tribe2_formatting_test", path)
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FormattingTest(unittest.TestCase):
    def setUp(self):
        self.formatting = load_formatting_module()

    def test_duration_text_uses_app_format(self):
        self.assertEqual(self.formatting.duration_text(1124183), "13 d 0 h 16 m 23 s")
        self.assertEqual(self.formatting.duration_text(1138), "0 d 0 h 18 m 58 s")
        self.assertIsNone(self.formatting.duration_text(None))


if __name__ == "__main__":
    unittest.main()
