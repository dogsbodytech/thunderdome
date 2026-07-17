import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from thunderdome.transport.ddp import (
    DDP_CHUNK_LEDS,
    DDP_DATATYPE_RGB8,
    DDP_DESTINATION_ID,
    DDP_PUSH,
    DDP_VER1,
    build_ddp_packet,
    chunk_frame,
    empty_frame,
    packets_for_frame,
    parse_hex_color,
    pixel_frame,
    range_frame,
    scale_color,
    send_frame,
    set_pixel,
    solid_frame,
)


class DDPTests(unittest.TestCase):
    def test_parse_hex_colour(self):
        self.assertEqual(parse_hex_color("#FF0080"), (255, 0, 128))

    def test_brightness_scaling(self):
        self.assertEqual(scale_color((255, 0, 0), 64), (64, 0, 0))

    def test_build_rgb_frame_of_correct_length(self):
        frame = solid_frame(5, "00FF00", brightness=255)
        self.assertEqual(len(frame), 15)
        self.assertEqual(frame[:6], bytes([0, 255, 0, 0, 255, 0]))

    def test_set_individual_pixel_colour_at_byte_offset(self):
        frame = empty_frame(5)
        set_pixel(frame, 3, (1, 2, 3))
        self.assertEqual(frame[9:12], bytes([1, 2, 3]))
        self.assertEqual(frame[:9], bytes(9))

    def test_pixel_frame_lights_one_index(self):
        frame = pixel_frame(4, 2, "FFFFFF", brightness=64)
        self.assertEqual(frame, bytearray([0, 0, 0, 0, 0, 0, 64, 64, 64, 0, 0, 0]))

    def test_range_frame_lights_correct_indexes(self):
        frame = range_frame(5, start=1, count=2, color="FF0000", brightness=255)
        self.assertEqual(frame, bytearray([0, 0, 0, 255, 0, 0, 255, 0, 0, 0, 0, 0, 0, 0, 0]))

    def test_ddp_chunking_splits_frame(self):
        frame = bytes(5 * 3)
        chunks = chunk_frame(frame, chunk_leds=2)
        self.assertEqual([chunk.led_offset for chunk in chunks], [0, 2, 4])
        self.assertEqual([chunk.byte_offset for chunk in chunks], [0, 6, 12])
        self.assertEqual([len(chunk.payload) for chunk in chunks], [6, 6, 3])
        self.assertFalse(chunks[0].is_last)
        self.assertTrue(chunks[-1].is_last)

    def test_ddp_packet_builder_uses_header_offset_and_length(self):
        payload = bytes([1, 2, 3, 4, 5, 6])
        packet = build_ddp_packet(payload, byte_offset=1440, is_last=True)
        flags, seq, data_type, dest, offset, length = struct.unpack("!BBBBLH", packet[:10])
        self.assertEqual(flags, DDP_VER1 | DDP_PUSH)
        self.assertEqual(seq, 0)
        self.assertEqual(data_type, DDP_DATATYPE_RGB8)
        self.assertEqual(dest, DDP_DESTINATION_ID)
        self.assertEqual(offset, 1440)
        self.assertEqual(length, len(payload))
        self.assertEqual(packet[10:], payload)

    def test_packets_for_frame_offsets(self):
        packets = packets_for_frame(bytes(5 * 3), chunk_leds=2)
        self.assertEqual(struct.unpack("!L", packets[0][4:8])[0], 0)
        self.assertEqual(struct.unpack("!L", packets[1][4:8])[0], 6)
        self.assertEqual(struct.unpack("!L", packets[2][4:8])[0], 12)

    def test_send_frame_uses_mocked_udp_socket(self):
        sock = Mock()
        count = send_frame("192.0.2.1", bytes(5 * 3), port=4048, chunk_leds=2, sock=sock)
        self.assertEqual(count, 3)
        self.assertEqual(sock.sendto.call_args_list[0].args[1], ("192.0.2.1", 4048))
        sock.close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
