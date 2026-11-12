from dataclasses import replace
from unittest.mock import patch

import pytest

from lerobot_robot_nexarm.bus import CMD_READ_POS, SYSTEM_ID, build_frame, parse_frame
from lerobot_robot_nexarm.calibration import JOINT_NAMES


@pytest.fixture(autouse=True)
def forbid_real_serial():
    # Even a forgotten mock must fail before pyserial can open a real device.
    with patch("serial.Serial", side_effect=AssertionError("Real serial ports are forbidden in tests")):
        yield


@pytest.fixture
def calibration():
    from lerobot.motors import MotorCalibration

    values = {
        name: MotorCalibration(id=i + 1, drive_mode=0, homing_offset=2000, range_min=500, range_max=3500)
        for i, name in enumerate(JOINT_NAMES)
    }
    values["gripper"] = replace(values["gripper"], range_min=1195, range_max=2833, homing_offset=2048)
    return values


class FakeSerial:
    """Actual byte-stream transport mock, responding only after a CMD 96 write."""

    def __init__(self, positions=None):
        self.is_open = True
        self.positions = positions or [2000, 2000, 2000, 2000, 2000, 2048]
        self.buffer = bytearray()
        self.writes = []
        self.drop_replies = False
        self.short_checksum = False

    @property
    def in_waiting(self):
        return len(self.buffer)

    def reset_input_buffer(self):
        self.buffer.clear()

    def write(self, frame):
        self.writes.append(frame)
        _, cmd, _ = parse_frame(frame)
        if cmd == CMD_READ_POS and not self.drop_replies:
            import struct

            args = struct.pack("<6h", *self.positions)
            reply = build_frame(SYSTEM_ID, cmd, args)
            if self.short_checksum:
                reply = reply[:-1] + bytes([(~sum(reply[2:5])) & 255])
            self.buffer.extend(b"[POS] debug\r\n" + reply)
        return len(frame)

    def read(self, size):
        chunk = bytes(self.buffer[:size])
        del self.buffer[:size]
        return chunk

    def close(self):
        self.is_open = False

    def commands(self):
        return [(parse_frame(frame)[1], parse_frame(frame)[2]) for frame in self.writes]


@pytest.fixture
def serial_mock(monkeypatch):
    fake = FakeSerial()

    # Overrides the fail-closed global guard for this test, never calls the real class.
    def reopen(**kwargs):
        fake.is_open = True
        return fake

    monkeypatch.setattr("lerobot_robot_nexarm.bus.serial.Serial", reopen)
    monkeypatch.setattr("lerobot_robot_nexarm.bus.time.sleep", lambda _: None)
    return fake
