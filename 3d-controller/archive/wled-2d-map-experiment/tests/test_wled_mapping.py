import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from wled_mapping import (
    LedPosition,
    MappingError,
    angular_distance_deg,
    build_clock_hand_sweep_frames,
    build_ddp_clock_hand_frame,
    chunk_seg_i_payload,
    clock_hand_width_mm,
    load_positions,
    print_clock_hand_sweep_summary,
    run_clock_hand_sweep,
    select_clock_hand_band_leds,
    select_clock_hand_leds,
    sparse_diff_payload,
    validate_ledmap,
)


class MappingTests(unittest.TestCase):
    def write_json(self, tmp: str, name: str, data: dict) -> Path:
        path = Path(tmp) / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_ledmap_validation_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_json(tmp, "ledmap.json", {"width": 3, "height": 2, "map": [-1, 0, 1, -1, 2, -1]})
            report = validate_ledmap(path)
            self.assertEqual(report.width, 3)
            self.assertEqual(report.height, 2)
            self.assertEqual(report.total_cells, 6)
            self.assertEqual(report.mapped_leds, 3)
            self.assertEqual(report.blank_cells, 3)
            self.assertEqual(report.min_led_index, 0)
            self.assertEqual(report.max_led_index, 2)
            self.assertEqual(report.duplicate_count, 0)

    def test_ledmap_validation_catches_wrong_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_json(tmp, "bad.json", {"width": 3, "height": 2, "map": [-1, 0, 1]})
            with self.assertRaises(MappingError):
                validate_ledmap(path)

    def test_ledmap_validation_catches_duplicate_led_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_json(tmp, "dup.json", {"width": 2, "height": 2, "map": [0, 1, 1, -1]})
            with self.assertRaises(MappingError):
                validate_ledmap(path)

    def test_angle_wrapping(self):
        self.assertEqual(angular_distance_deg(359, 1), 2)
        self.assertEqual(angular_distance_deg(1, 359), 2)
        self.assertEqual(angular_distance_deg(180, 0), 180)

    def test_clock_frame_led_selection(self):
        positions = [
            LedPosition(0, 10, 0),      # 0 degrees
            LedPosition(1, 0, 10),      # 90 degrees
            LedPosition(2, -10, 0),     # 180 degrees
            LedPosition(3, 0, -10),     # 270 degrees
            LedPosition(4, 10, 1),      # near 0 degrees
        ]
        selected = select_clock_hand_leds(positions, angle_deg=0, hand_width_deg=12, radius_max_mm=100)
        self.assertEqual(selected, {0, 4})

    def test_sparse_diff_generation_between_frames(self):
        payload = sparse_diff_payload({1, 2, 3}, {2, 3, 4}, hand_color="FF0000", background_color="000000")
        self.assertEqual(payload, [1, "000000", 4, "FF0000"])

    def test_chunking_seg_i_payloads(self):
        payload = [0, "FF0000", 1, "00FF00", 2, "0000FF", 3, "FFFFFF"]
        chunks = chunk_seg_i_payload(payload, max_pairs=2)
        self.assertEqual(chunks, [[0, "FF0000", 1, "00FF00"], [2, "0000FF", 3, "FFFFFF"]])

    def test_chunking_rejects_odd_payload(self):
        with self.assertRaises(MappingError):
            chunk_seg_i_payload([0, "FF0000", 1], max_pairs=2)

    def test_loader_accepts_physical_index_and_excludes_tail_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_json(tmp, "positions.json", {
                "positions": [
                    {"physical_index": 10, "x_mm": 0, "y_mm": 0, "on_dome_path": True},
                    {"physical_index": 11, "x_mm": 0, "y_mm": 100, "on_dome_path": False, "note": "tail"},
                ]
            })
            positions, _ = load_positions(path)
            self.assertEqual([p.led_index for p in positions], [10])
            positions_with_tail, _ = load_positions(path, include_tail=True)
            self.assertEqual([p.led_index for p in positions_with_tail], [10, 11])

    def test_default_hand_width_is_10_pitches_times_30_mm(self):
        self.assertEqual(clock_hand_width_mm(None, pitch_mm=30, hand_width_pitches=10), 300)
        self.assertEqual(clock_hand_width_mm(450, pitch_mm=30, hand_width_pitches=10), 450)

    def test_hand_selects_by_perpendicular_distance_not_angle_wedge(self):
        positions = [
            LedPosition(0, 1000, 0),    # on centreline
            LedPosition(1, 1000, 149),  # inside 300 mm band
            LedPosition(2, 1000, 151),  # outside 300 mm band
        ]
        selected = select_clock_hand_band_leds(positions, angle_deg=0, hand_width_mm=300)
        self.assertEqual(selected, {0, 1})

    def test_hand_does_not_select_leds_behind_centre_or_beyond_radius(self):
        positions = [
            LedPosition(0, -10, 0),    # behind centre for 0 degrees
            LedPosition(1, 3001, 0),   # beyond dome edge
            LedPosition(2, 3000, 0),   # edge included
        ]
        selected = select_clock_hand_band_leds(positions, angle_deg=0, hand_width_mm=300, radius_max_mm=3000)
        self.assertEqual(selected, {2})

    def test_zero_degree_hand_selects_positive_x(self):
        positions = [LedPosition(0, 100, 0), LedPosition(1, 0, 100)]
        self.assertEqual(select_clock_hand_band_leds(positions, angle_deg=0, hand_width_mm=10), {0})

    def test_ninety_degree_hand_selects_positive_y(self):
        positions = [LedPosition(0, 100, 0), LedPosition(1, 0, 100)]
        self.assertEqual(select_clock_hand_band_leds(positions, angle_deg=90, hand_width_mm=10), {1})

    def test_duration_three_seconds_with_one_degree_step_produces_360_frames(self):
        frames = build_clock_hand_sweep_frames([LedPosition(0, 100, 0)], duration=3.0, step_deg=1.0, hand_width_mm=300)
        self.assertEqual(len(frames), 360)
        self.assertEqual(frames[0].angle_deg, 0.0)
        self.assertEqual(frames[-1].angle_deg, 359.0)
        self.assertAlmostEqual(frames[0].delay_seconds, 3.0 / 360.0)

    def test_dry_run_does_not_send_http_requests(self):
        client = Mock()
        output = io.StringIO()
        run_clock_hand_sweep(
            client,
            [LedPosition(0, 100, 0)],
            duration=0.1,
            step_deg=90,
            dry_run=True,
            output=output,
        )
        client.post_state.assert_not_called()
        client.set_individual_leds.assert_not_called()
        self.assertIn("Clock hand sweep", output.getvalue())

    def test_high_brightness_warning_is_emitted(self):
        output = io.StringIO()
        print_clock_hand_sweep_summary(
            [type("Frame", (), {"angle_deg": 0.0, "lit_leds": {1}, "delay_seconds": 0.1})()],
            loaded_count=1,
            include_tail=False,
            duration=3,
            step_deg=1,
            pitch_mm=30,
            hand_width_pitches=10,
            hand_width_mm=300,
            brightness=200,
            output=output,
        )
        self.assertIn("Warning: brightness 200 is high", output.getvalue())

    def test_default_clock_hand_sweep_is_one_sweep(self):
        client = Mock()
        run_clock_hand_sweep(
            client,
            [LedPosition(0, 100, 0)],
            duration=0.1,
            step_deg=180,
            sleep_fn=lambda _: None,
            output=io.StringIO(),
        )
        # Two frames in one sweep: on at 0°, off at 180°.
        self.assertEqual(client.set_individual_leds.call_count, 2)

    def test_repeat_three_generates_three_full_sweeps(self):
        client = Mock()
        output = io.StringIO()
        run_clock_hand_sweep(
            client,
            [LedPosition(0, 100, 0)],
            duration=0.1,
            step_deg=180,
            repeat=3,
            sleep_fn=lambda _: None,
            output=output,
        )
        self.assertEqual(client.set_individual_leds.call_count, 6)
        self.assertIn("Repeat mode: 3 sweeps.", output.getvalue())
        self.assertIn("Sweep 3, frame 2/2", output.getvalue())

    def test_ctrl_c_clears_lit_leds(self):
        client = Mock()

        def interrupt(_delay: float) -> None:
            raise KeyboardInterrupt

        run_clock_hand_sweep(
            client,
            [LedPosition(0, 100, 0)],
            duration=0.1,
            step_deg=180,
            sleep_fn=interrupt,
            output=io.StringIO(),
        )
        calls = [call.args[0] for call in client.set_individual_leds.call_args_list]
        self.assertIn([0, "FFFFFF"], calls)
        self.assertIn([0, "000000"], calls)

    def test_ddp_clock_sweep_builds_full_frame_not_sparse_http(self):
        client = Mock()
        positions = [LedPosition(0, 100, 0), LedPosition(1, 0, 100)]
        with patch("wled_mapping.send_frame") as send_frame_mock:
            run_clock_hand_sweep(
                client,
                positions,
                duration=0.1,
                step_deg=180,
                transport="ddp",
                host="192.0.2.1",
                led_count=2,
                sleep_fn=lambda _: None,
                output=io.StringIO(),
            )
        client.post_state.assert_not_called()
        client.set_individual_leds.assert_not_called()
        first_frame = send_frame_mock.call_args_list[0].args[1]
        self.assertEqual(len(first_frame), 6)
        self.assertEqual(first_frame[:3], bytes([64, 64, 64]))

    def test_build_ddp_clock_hand_frame_uses_physical_index_slots(self):
        positions = [LedPosition(3, 100, 0)]
        frame = build_ddp_clock_hand_frame(positions, {3}, led_count=5, color="FF0000", brightness=64)
        self.assertEqual(frame[9:12], bytes([64, 0, 0]))
        self.assertEqual(len(frame), 15)


if __name__ == "__main__":
    unittest.main()
