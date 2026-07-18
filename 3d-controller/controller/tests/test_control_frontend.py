import unittest
from pathlib import Path


STATIC = Path(__file__).resolve().parents[2] / "simulator" / "static"


class ControlFrontendTests(unittest.TestCase):
    def setUp(self):
        self.html = (STATIC / "index.html").read_text(encoding="utf-8")
        self.js = (STATIC / "control-ui.js").read_text(encoding="utf-8")

    def test_schema_driven_controls_and_local_control_endpoints_are_present(self):
        for value in ("boolean", "choice", "colour", "vector", "effect-list", "integer", "float"):
            self.assertIn(f"parameter.type === '{value}'", self.js)
        for endpoint in ("/api/control/capabilities", "/api/effects", "/api/runtime/status", "/api/runtime/baseline", "/api/runtime/stop"):
            self.assertIn(endpoint, self.js)
        self.assertIn("control-ui.js", self.html)

    def test_live_output_requires_capability_and_confirmation_without_external_assets(self):
        self.assertIn("option.disabled=!caps.live_ddp_available", self.js)
        self.assertIn("Confirm LIVE DOME output", self.js)
        self.assertIn("live-confirm", self.html)
        self.assertNotIn("http://", self.js)
        self.assertNotIn("https://", self.js)

    def test_auto_continuous_mode_and_command_busy_state_are_handled(self):
        self.assertIn("p.name==='cycles' && value===''", self.js)
        self.assertIn("buttons.forEach(button=>button.disabled=true)", self.js)

    def test_colour_controls_synchronize_and_submit_hex_values(self):
        self.assertIn("picker.oninput=()=>hex.value=picker.value.toUpperCase()", self.js)
        self.assertIn("hex.oninput=()=>", self.js)
        self.assertIn("Colours must use #RRGGBB.", self.js)
        self.assertIn("value=hex?.value || node?.value", self.js)

    def test_duration_controls_default_to_continuous_and_submit_existing_runtime_field(self):
        self.assertIn('id="continuous" type="checkbox" checked', self.html)
        self.assertIn("duration_seconds:duration", self.js)
        self.assertIn("Duration must be greater than zero.", self.js)

    def test_playlist_editor_preserves_order_and_cannot_be_emptied(self):
        for action in ("add", "remove", "up", "down"):
            self.assertIn(f'data-playlist-action="{action}"', self.js)
        self.assertIn("list.options.length>1", self.js)
        self.assertIn("[...node.options].map(option=>option.value)", self.js)


if __name__ == "__main__":
    unittest.main()
