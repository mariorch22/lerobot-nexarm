import struct

import pytest

from lerobot_robot_nexarm import NexArmFollower, NexArmFollowerConfig, NexArmLeader, NexArmLeaderConfig
from lerobot_robot_nexarm.bus import build_frame
from lerobot_robot_nexarm.validated_bus import ValidatedNexArmMotorsBus

CAPTURED_BAD_FRAME = bytes.fromhex("ff ff ff 0e 60 01 00 ff ff cd 52 01 40 20 02 00 20 f1")
CAPTURED_NEXT_POSITIONS = [2080, 3307, 1025, 2109, 2003, 2782]


def supply_replies(serial_mock, monkeypatch, replies, request_command=96):
    replies = iter(replies)
    original_write = serial_mock.write

    def write(frame):
        result = original_write(frame)
        if frame[4] == request_command:
            serial_mock.buffer.clear()
            serial_mock.buffer.extend(next(replies))
        return result

    monkeypatch.setattr(serial_mock, "write", write)


def test_captured_invalid_frame_is_retried_before_any_clipping(serial_mock, monkeypatch, caplog):
    valid = build_frame(255, 96, struct.pack("<6h", *CAPTURED_NEXT_POSITIONS))
    supply_replies(serial_mock, monkeypatch, [CAPTURED_BAD_FRAME, valid])
    bus = ValidatedNexArmMotorsBus("MOCK")
    bus.connect()
    try:
        assert bus.read_positions() == CAPTURED_NEXT_POSITIONS
        assert bus.rejected_position_replies == 1
        assert serial_mock.commands() == [(96, b""), (96, b"")]
        assert "[1, -1, 21197, 16385, 544, 8192]" in caplog.text
    finally:
        bus.disconnect()


def test_persistently_invalid_samples_exhaust_original_three_attempts(serial_mock, monkeypatch):
    supply_replies(serial_mock, monkeypatch, [CAPTURED_BAD_FRAME] * 3)
    bus = ValidatedNexArmMotorsBus("MOCK")
    bus.connect()
    try:
        with pytest.raises(TimeoutError, match="No position reply"):
            bus.read_positions()
        assert bus.rejected_position_replies == 3
        assert serial_mock.commands() == [(96, b"")] * 3
    finally:
        bus.disconnect()


@pytest.mark.parametrize("short_checksum", [False, True])
def test_real_12bit_boundaries_and_gripper_below_nominal_min_are_not_filtered(serial_mock, short_checksum):
    serial_mock.positions = [0, 4095, 1, 4094, 2048, 1191]
    serial_mock.short_checksum = short_checksum
    bus = ValidatedNexArmMotorsBus("MOCK")
    bus.connect()
    try:
        assert bus.read_positions() == serial_mock.positions
        assert bus.rejected_position_replies == 0
        assert serial_mock.commands() == [(96, b"")]
    finally:
        bus.disconnect()


@pytest.mark.parametrize("command,payload", [(97, bytes(12)), (96, bytes(10)), (96, bytes(14))])
def test_wrong_command_or_payload_length_is_not_a_position_sample(serial_mock, monkeypatch, command, payload):
    supply_replies(serial_mock, monkeypatch, [build_frame(255, command, payload)] * 3)
    bus = ValidatedNexArmMotorsBus("MOCK")
    bus.connect()
    try:
        with pytest.raises(TimeoutError):
            bus.read_positions()
        assert bus.rejected_position_replies == 3
        assert serial_mock.commands() == [(96, b"")] * 3
    finally:
        bus.disconnect()


def test_non_position_request_keeps_original_reply_handling(serial_mock, monkeypatch):
    supply_replies(serial_mock, monkeypatch, [build_frame(255, 1, b"\x01\x02\x03")], request_command=1)
    bus = ValidatedNexArmMotorsBus("MOCK")
    bus.connect()
    try:
        assert bus._send(build_frame(255, 1)) == (1, b"\x01\x02\x03")
        assert bus.rejected_position_replies == 0
    finally:
        bus.disconnect()


def test_both_device_classes_use_position_validation(tmp_path):
    follower = NexArmFollower(NexArmFollowerConfig(port="MOCK", calibration_dir=tmp_path))
    leader = NexArmLeader(
        NexArmLeaderConfig(
            port="MOCK", calibration_dir=tmp_path, follower_calibration_path=tmp_path / "f.json"
        )
    )
    assert isinstance(follower.bus, ValidatedNexArmMotorsBus)
    assert isinstance(leader.bus, ValidatedNexArmMotorsBus)
