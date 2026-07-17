from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.led_positions import write_positions


class PositionOutputRegressionTests(unittest.TestCase):
    def test_write_positions_creates_missing_nested_parent_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "missing" / "nested" / "positions.json"
            self.assertFalse(output.parent.exists())
            write_positions(output, {"schema_version": 1, "leds": []})
            self.assertTrue(output.parent.is_dir())
            self.assertTrue(output.is_file())
            self.assertEqual(json.loads(output.read_text()), {"schema_version": 1, "leds": []})


if __name__ == "__main__":
    unittest.main()
