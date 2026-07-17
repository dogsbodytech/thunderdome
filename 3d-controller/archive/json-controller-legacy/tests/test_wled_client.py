import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from wled_client import WLEDClient, WLEDApiError
from wled_favorites import FavoritesError, FavoritesStore, cycle_favorites, validate_interval
from wledctl import parse_args, format_indexed_names


class FakeResponse:
    def __init__(self, body, status=200):
        self.body = body.encode("utf-8") if isinstance(body, str) else body
        self.status = status
        self.headers = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class WLEDClientTests(unittest.TestCase):
    def test_normalizes_base_url_and_fetches_state(self):
        with patch("urllib.request.urlopen", return_value=FakeResponse('{"on": true}')) as urlopen:
            client = WLEDClient("http://wled.local/")
            self.assertEqual(client.get_state(), {"on": True})
            request = urlopen.call_args.args[0]
            self.assertEqual(request.full_url, "http://wled.local/json/state")
            self.assertEqual(request.get_method(), "GET")

    def test_post_state_can_request_updated_state(self):
        with patch("urllib.request.urlopen", return_value=FakeResponse('{"on": true, "bri": 10}')) as urlopen:
            client = WLEDClient("http://wled.local")
            result = client.post_state({"on": True}, return_state=True)
            self.assertEqual(result, {"on": True, "bri": 10})
            request = urlopen.call_args.args[0]
            sent = json.loads(request.data.decode("utf-8"))
            self.assertEqual(sent, {"on": True, "v": True})
            self.assertEqual(request.full_url, "http://wled.local/json/state")
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request.headers["Content-type"], "application/json")

    def test_set_color_global_and_segment_payloads(self):
        with patch.object(WLEDClient, "post_state", return_value={}) as post_state:
            client = WLEDClient("http://wled.local")
            client.set_color((255, 0, 10))
            post_state.assert_called_with({"seg": [{"col": [[255, 0, 10]]}]}, return_state=False)
            client.set_color((0, 255, 200), segment_id=2)
            post_state.assert_called_with({"seg": [{"id": 2, "col": [[0, 255, 200]]}]}, return_state=False)

    def test_validation_rejects_bad_ranges(self):
        client = WLEDClient("http://wled.local")
        with self.assertRaises(ValueError):
            client.set_brightness(256)
        with self.assertRaises(ValueError):
            client.set_color((0, -1, 0))
        with self.assertRaises(ValueError):
            client.set_effect(-1)
        with self.assertRaises(ValueError):
            client.update_segment(-1, {"on": True})

    def test_effect_and_palette_validation_uses_counts_when_available(self):
        with patch.object(WLEDClient, "get_info", return_value={"fxcount": 3, "palcount": 2}):
            client = WLEDClient("http://wled.local")
            with self.assertRaises(ValueError):
                client.set_effect(3)
            with self.assertRaises(ValueError):
                client.set_palette(2)

    def test_invalid_json_raises_api_error(self):
        with patch("urllib.request.urlopen", return_value=FakeResponse('not json')):
            client = WLEDClient("http://wled.local")
            with self.assertRaises(WLEDApiError):
                client.get_info()

    def test_cli_accepts_common_options_after_subcommand(self):
        args = parse_args(["post", '{"on":true}', "--base-url", "http://wled.local", "--timeout", "0.1", "--return-state"])
        self.assertEqual(args.command, "post")
        self.assertEqual(args.base_url, "http://wled.local")
        self.assertEqual(args.timeout, 0.1)
        self.assertTrue(args.return_state)

    def test_individual_led_payload_uses_segment_list_form(self):
        with patch.object(WLEDClient, "post_state", return_value={}) as post_state:
            client = WLEDClient("http://wled.local")
            client.set_individual_leds(["FF0000", "00FF00"], segment_id=0)
            post_state.assert_called_with({"seg": [{"id": 0, "i": ["FF0000", "00FF00"]}]}, return_state=False)


class FavoritesTests(unittest.TestCase):
    def test_favorites_config_can_be_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wled_favourites.json"
            store = FavoritesStore(path)
            store.save(store.default_data())
            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text())["effects"], [])

    def test_favorite_effect_can_be_added_with_id_and_resolved_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FavoritesStore(Path(tmp) / "wled_favourites.json")
            entry, created = store.add_effect(9, ["Solid"] * 9 + ["Rainbow"], notes="Good full-dome colour test")
            self.assertTrue(created)
            self.assertEqual(entry, {"id": 9, "name": "Rainbow", "notes": "Good full-dome colour test"})
            self.assertEqual(store.list_effects(), [entry])

    def test_duplicate_favorite_does_not_create_duplicate_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FavoritesStore(Path(tmp) / "wled_favourites.json")
            effects = ["Solid", "Blink", "Rainbow"]
            store.add_effect(2, effects, notes="old")
            entry, created = store.add_effect(2, effects, notes="updated")
            self.assertFalse(created)
            self.assertEqual(entry["notes"], "updated")
            self.assertEqual(len(store.list_effects()), 1)

    def test_favorite_effect_can_be_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FavoritesStore(Path(tmp) / "wled_favourites.json")
            effects = ["Solid", "Blink", "Rainbow"]
            store.add_effect(2, effects)
            self.assertTrue(store.remove_effect(2))
            self.assertFalse(store.remove_effect(2))
            self.assertEqual(store.list_effects(), [])

    def test_cycle_uses_saved_effects_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FavoritesStore(Path(tmp) / "wled_favourites.json")
            store.save({
                "default_interval_seconds": 30,
                "effects": [
                    {"id": 9, "name": "Rainbow"},
                    {"id": 12, "name": "Fade"},
                ],
            })
            client = Mock()
            slept = []
            applied = cycle_favorites(client, store, interval=1, segment_id=0, sleep_fn=slept.append)
            self.assertEqual(applied, 2)
            self.assertEqual(slept, [1.0])
            self.assertEqual(client.set_effect.call_args_list[0].args, (9,))
            self.assertEqual(client.set_effect.call_args_list[0].kwargs, {"segment_id": 0, "return_state": False})
            self.assertEqual(client.set_effect.call_args_list[1].args, (12,))

    def test_invalid_effect_id_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FavoritesStore(Path(tmp) / "wled_favourites.json")
            with self.assertRaises(FavoritesError):
                store.add_effect(99, ["Solid"])

    def test_invalid_interval_is_rejected(self):
        with self.assertRaises(FavoritesError):
            validate_interval(0)
        with self.assertRaises(FavoritesError):
            validate_interval(-1)

    def test_set_default_interval_creates_config_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wled_favourites.json"
            store = FavoritesStore(path)
            store.set_default_interval(10)
            data = json.loads(path.read_text())
            self.assertEqual(data["default_interval_seconds"], 10)
            self.assertEqual(data["effects"], [])

    def test_set_default_interval_preserves_existing_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FavoritesStore(Path(tmp) / "wled_favourites.json")
            store.save({
                "default_interval_seconds": 30,
                "effects": [{"id": 9, "name": "Rainbow", "notes": "keep me"}],
            })
            store.set_default_interval(5.5)
            data = store.load()
            self.assertEqual(data["default_interval_seconds"], 5.5)
            self.assertEqual(data["effects"], [{"id": 9, "name": "Rainbow", "notes": "keep me"}])

    def test_set_default_interval_rejects_invalid_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FavoritesStore(Path(tmp) / "wled_favourites.json")
            with self.assertRaises(FavoritesError):
                store.set_default_interval(0)

    def test_cli_parses_favorites_commands(self):
        args = parse_args(["favorites", "cycle", "--interval", "10", "--segment", "0", "--favorites-file", "./mine.json"])
        self.assertEqual(args.command, "favorites")
        self.assertEqual(args.favorites_command, "cycle")
        self.assertEqual(args.interval, 10)
        self.assertEqual(args.segment, 0)
        self.assertEqual(args.favorites_file, "./mine.json")

    def test_cli_parses_favorites_interval_command(self):
        args = parse_args(["favorites", "interval", "10", "--favorites-file", "./mine.json"])
        self.assertEqual(args.command, "favorites")
        self.assertEqual(args.favorites_command, "interval")
        self.assertEqual(args.seconds, 10)
        self.assertEqual(args.favorites_file, "./mine.json")

    def test_cli_parses_palettes_filter(self):
        args = parse_args(["palettes", "--filter", "rainbow"])
        self.assertEqual(args.command, "palettes")
        self.assertEqual(args.filter, "rainbow")

    def test_format_indexed_names_matches_effects_style_and_filters(self):
        lines = format_indexed_names(["Default", "* Random Cycle", "Rainbow"], query="r")
        self.assertEqual(lines, ["   1  * Random Cycle", "   2  Rainbow"])

    def test_cli_parses_mapping_clock_frame(self):
        args = parse_args(["mapping", "clock-frame", "led_positions_2d.json", "--host", "192.168.12.11", "--angle", "90"])
        self.assertEqual(args.command, "mapping")
        self.assertEqual(args.mapping_command, "clock-frame")
        self.assertEqual(args.host, "192.168.12.11")
        self.assertEqual(args.angle, 90)

    def test_cli_parses_mapping_clock_hand_sweep(self):
        args = parse_args(["mapping", "clock-hand-sweep", "led_positions_2d.json", "--dry-run"])
        self.assertEqual(args.command, "mapping")
        self.assertEqual(args.mapping_command, "clock-hand-sweep")
        self.assertEqual(args.duration, 3.0)
        self.assertEqual(args.step_deg, 1.0)
        self.assertEqual(args.pitch_mm, 30.0)
        self.assertEqual(args.hand_width_pitches, 10.0)
        self.assertEqual(args.repeat, 1)
        self.assertFalse(args.loop)
        self.assertTrue(args.dry_run)

    def test_cli_parses_clock_hand_sweep_loop(self):
        args = parse_args(["mapping", "clock-hand-sweep", "led_positions_2d.json", "--loop"])
        self.assertTrue(args.loop)
        self.assertIsNone(args.repeat)

    def test_cli_parses_clock_hand_sweep_repeat(self):
        args = parse_args(["mapping", "clock-hand-sweep", "led_positions_2d.json", "--repeat", "5"])
        self.assertFalse(args.loop)
        self.assertEqual(args.repeat, 5)

    def test_cli_rejects_clock_hand_sweep_loop_and_repeat_together(self):
        with self.assertRaises(SystemExit):
            parse_args(["mapping", "clock-hand-sweep", "led_positions_2d.json", "--loop", "--repeat", "5"])

    def test_cli_parses_ddp_commands(self):
        clear = parse_args(["ddp", "clear", "--host", "192.168.12.11", "--led-count", "5000"])
        self.assertEqual(clear.command, "ddp")
        self.assertEqual(clear.ddp_command, "clear")
        solid = parse_args(["ddp", "solid", "--host", "192.168.12.11", "--led-count", "5000", "--color", "FF0000", "--brightness", "64"])
        self.assertEqual(solid.ddp_command, "solid")
        pixel = parse_args(["ddp", "pixel", "--host", "192.168.12.11", "--led-count", "5000", "--index", "1234"])
        self.assertEqual(pixel.index, 1234)
        rng = parse_args(["ddp", "range", "--host", "192.168.12.11", "--led-count", "5000", "--start", "1000", "--count", "50"])
        self.assertEqual(rng.start, 1000)
        self.assertEqual(rng.count, 50)

    def test_cli_parses_clock_hand_sweep_ddp_transport(self):
        args = parse_args(["mapping", "clock-hand-sweep", "led_positions_2d.json", "--transport", "ddp", "--led-count", "5000", "--ddp-port", "4048", "--ddp-chunk-leds", "480"])
        self.assertEqual(args.transport, "ddp")
        self.assertEqual(args.led_count, 5000)
        self.assertEqual(args.ddp_port, 4048)
        self.assertEqual(args.ddp_chunk_leds, 480)


if __name__ == "__main__":
    unittest.main()
