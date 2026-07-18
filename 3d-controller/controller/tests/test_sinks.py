import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.sinks import DDPFrameSink
from thunderdome.wled.multi import WLEDOperationResult


class DDPFrameSinkTests(unittest.TestCase):
    def test_sets_controller_brightness_to_maximum_before_opening_ddp(self):
        controllers = Mock()
        session = Mock()

        def set_brightness(config, operation):
            self.assertIs(config, controllers)
            client = Mock()
            operation(client)
            client.set_brightness.assert_called_once_with(255)
            return []

        with patch("thunderdome.sinks.load_controllers", return_value=controllers), patch(
            "thunderdome.sinks.run_wled_operation", side_effect=set_brightness
        ), patch("thunderdome.sinks.MultiControllerDDPSession", return_value=session) as create_session:
            sink = DDPFrameSink("controllers.json")
            sink.open()

        create_session.assert_called_once_with(controllers)
        self.assertIs(sink._session, session)

    def test_refuses_to_start_ddp_when_brightness_preparation_fails(self):
        controllers = Mock()
        failures = [WLEDOperationResult(2, "controller-2", error="timeout")]

        with patch("thunderdome.sinks.load_controllers", return_value=controllers), patch(
            "thunderdome.sinks.run_wled_operation", return_value=failures
        ), patch("thunderdome.sinks.MultiControllerDDPSession") as create_session:
            with self.assertRaisesRegex(OSError, "controller 2: timeout"):
                DDPFrameSink("controllers.json").open()

        create_session.assert_not_called()


if __name__ == "__main__":
    unittest.main()
