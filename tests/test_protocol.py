import struct

import pytest

from lerobot_robot_nexarm.bus import (
    CMD_READ_POS,
    NexArmMotorsBus,
    build_frame,
    map_leader_to_follower,
    parse_frame,
)


@pytest.mark.parametrize(
    "cmd,args,hex_bytes",
    [
        (96, b"", "ff ff ff 02 60 9e"),
        (97, bytes(12), "ff ff ff 0e 61 00 00 00 00 00 00 00 00 00 00 00 00 91"),
        (98, b"\x01", "ff ff ff 03 62 01 9a"),
        (98, b"\x00", "ff ff ff 03 62 00 9b"),
        (68, b"\x01", "ff ff ff 03 44 01 b8"),
        (68, b"\x00", "ff ff ff 03 44 00 b9"),
        (
            96,
            bytes.fromhex("00 08 00 04 00 0c 00 02 a0 0f d0 07"),
            "ff ff ff 0e 60 00 08 00 04 00 0c 00 02 a0 0f d0 07 f2",
        ),
    ],
)
def test_literal_protocol_vectors(cmd, args, hex_bytes):
    expected = bytes.fromhex(hex_bytes)
    assert build_frame(255, cmd, args) == expected
    assert parse_frame(expected) == (255, cmd, args)


def test_accept_full_and_firmware_short_checksum():
    full = bytes.fromhex("ff ff ff 0e 60 00 08 00 04 00 0c 00 02 a0 0f d0 07 f2")
    short = full[:-1] + b"\x92"
    assert parse_frame(short) == parse_frame(full)
    assert parse_frame(full[:-1] + b"\x00") is None


@pytest.mark.parametrize(
    "frame", [b"", b"\xff", bytes.fromhex("00 00 ff 02 60 9e"), bytes.fromhex("ff ff ff 0e 60 00 08")]
)
def test_reject_bad_header_or_truncated_frame(frame):
    assert parse_frame(frame) is None


@pytest.mark.parametrize("position,expected", [(0, 4095), (1, 4095), (1000, 3096), (2048, 2048), (4095, 1)])
def test_fixed_shoulder_mirror(position, expected):
    assert map_leader_to_follower([2000, position, 2000, 2000, 2000, 2048])[1] == expected


@pytest.mark.parametrize(
    "position,expected", [(0, 1195), (1639, 1197), (1800, 1841), (2048, 2833), (4095, 2833)]
)
def test_fixed_gripper_mapping(position, expected):
    assert map_leader_to_follower([2000] * 5 + [position])[5] == expected


def test_real_bus_read_write_and_stream_resynchronization(serial_mock):
    serial_mock.short_checksum = True
    bus = NexArmMotorsBus("MOCK")
    bus.connect()
    assert bus.read_positions() == serial_mock.positions
    bus.write_positions([500, 1000, 1500, 2000, 2500, 2800])
    assert serial_mock.commands()[-1] == (97, struct.pack("<6h", 500, 1000, 1500, 2000, 2500, 2800))
    bus.disconnect()
    assert not serial_mock.is_open


def test_read_timeout_preserves_three_attempts(serial_mock):
    serial_mock.drop_replies = True
    bus = NexArmMotorsBus("MOCK")
    bus.connect()
    with pytest.raises(TimeoutError):
        bus.read_positions()
    assert len([cmd for cmd, _ in serial_mock.commands() if cmd == CMD_READ_POS]) == 3


def test_fragmented_reply_and_noise(serial_mock):
    bus = NexArmMotorsBus("MOCK")
    buffer = bytearray(b"[WARN] debug" + bytes.fromhex("ff ff ff 0e 60 00"))
    assert bus._try_parse(buffer) is None
    buffer.extend(bytes.fromhex("08 00 04 00 0c 00 02 a0 0f d0 07 f2"))
    assert bus._try_parse(buffer) == (96, bytes.fromhex("00 08 00 04 00 0c 00 02 a0 0f d0 07"))
