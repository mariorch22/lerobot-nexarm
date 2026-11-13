import importlib.util
import struct
from pathlib import Path

import pytest

from lerobot_robot_nexarm.bus import parse_frame


@pytest.fixture
def raw_teleop():
    path = Path(__file__).resolve().parents[1] / "scripts" / "teleoperate_raw.py"
    spec = importlib.util.spec_from_file_location("teleoperate_raw", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def arms(raw_teleop, serial_mock, monkeypatch):
    fake_class = type(serial_mock)
    leader = fake_class(positions=[2000, 1000, 2200, 2300, 1800, 1800])
    follower = fake_class(positions=[2040, 2100, 2000, 1900, 1800, 2048])
    devices = {"MOCK_F": follower, "MOCK_L": leader}
    events = []
    clock = [0.0]

    def open_port(**kwargs):
        port = kwargs["port"]
        assert port in devices, "Only explicitly mocked ports are allowed"
        events.append(("open", port, kwargs))
        return devices[port]

    def sleep(seconds):
        clock[0] += seconds

    for port, device in devices.items():
        original_write = device.write

        def write(frame, original_write=original_write, port=port):
            _, command, arguments = parse_frame(frame)
            events.append(("tx", port, command, arguments))
            return original_write(frame)

        monkeypatch.setattr(device, "write", write)
    monkeypatch.setattr("lerobot_robot_nexarm.bus.serial.Serial", open_port)
    monkeypatch.setattr(raw_teleop.time, "sleep", sleep)
    monkeypatch.setattr(raw_teleop.time, "monotonic", lambda: clock[0])
    return follower, leader, events


def test_old_startup_mapping_readback_and_disconnect_without_calibration(raw_teleop, arms):
    follower, leader, events = arms
    assert raw_teleop.teleoperate("MOCK_F", "MOCK_L", duration=1 / 30) == 1
    assert [event[1] for event in events if event[0] == "open"] == ["MOCK_L", "MOCK_F"]
    for event in events:
        if event[0] == "open":
            assert event[2] == {
                "port": event[1],
                "baudrate": 1_000_000,
                "timeout": 0.05,
                "write_timeout": 0.05,
            }
    assert leader.commands() == [(98, b"\x00"), (96, b"")]
    assert follower.commands() == [
        (68, b"\x01"),
        (98, b"\x01"),
        (96, b""),
        (97, struct.pack("<6h", 2000, 3096, 2200, 2300, 1800, 1841)),
        (96, b""),
        (68, b"\x00"),
    ]
    tx_roles = [event[1:3] for event in events if event[0] == "tx"]
    assert tx_roles[3:6] == [("MOCK_F", 96), ("MOCK_L", 96), ("MOCK_F", 97)]
    assert not follower.is_open and not leader.is_open


@pytest.mark.parametrize("role", ["Follower", "Leader"])
def test_initial_read_timeout_sends_no_targets_and_closes_both_ports(raw_teleop, arms, role):
    follower, leader, _ = arms
    (follower if role == "Follower" else leader).drop_replies = True
    with pytest.raises(TimeoutError, match=f"{role} on MOCK_"):
        raw_teleop.teleoperate("MOCK_F", "MOCK_L", duration=1 / 30)
    assert not any(command == 97 for command, _ in follower.commands())
    assert follower.commands()[-1] == (68, b"\x00")
    assert not follower.is_open and not leader.is_open


def test_readback_timeout_keeps_old_loop_behavior(raw_teleop, arms, monkeypatch):
    follower, leader, _ = arms
    original_write = follower.write

    def write(frame):
        result = original_write(frame)
        if frame[4] == 97:
            follower.drop_replies = True
        return result

    monkeypatch.setattr(follower, "write", write)
    assert raw_teleop.teleoperate("MOCK_F", "MOCK_L", duration=1 / 30) == 1
    assert [command for command, _ in follower.commands()].count(96) == 4
    assert not follower.is_open and not leader.is_open


def test_interrupted_read_closes_both_ports(raw_teleop, arms, monkeypatch):
    follower, leader, _ = arms

    def interrupt(size):
        raise KeyboardInterrupt

    monkeypatch.setattr(follower, "read", interrupt)
    with pytest.raises(KeyboardInterrupt):
        raw_teleop.teleoperate("MOCK_F", "MOCK_L", duration=1 / 30)
    assert follower.commands()[-1] == (68, b"\x00")
    assert not follower.is_open and not leader.is_open


def test_failed_bridge_entry_still_attempts_exit_and_closes_ports(raw_teleop, arms, monkeypatch):
    follower, leader, _ = arms
    original_write = follower.write

    def write(frame):
        if frame[4] == 68 and frame[5] == 1:
            raise OSError("bridge entry transport failure")
        return original_write(frame)

    monkeypatch.setattr(follower, "write", write)
    with pytest.raises(OSError, match="bridge entry"):
        raw_teleop.teleoperate("MOCK_F", "MOCK_L", duration=1 / 30)
    assert follower.commands() == [(68, b"\x00")]
    assert not follower.is_open and not leader.is_open


@pytest.mark.parametrize(
    "kwargs",
    [
        {"follower_port": "MOCK_L"},
        {"follower_port": " mock_l "},
        {"follower_port": " "},
        {"fps": 0},
        {"fps": float("nan")},
        {"fps": float("inf")},
        {"duration": -1},
        {"duration": float("nan")},
    ],
)
def test_invalid_arguments_fail_before_opening_any_port(raw_teleop, kwargs):
    arguments = {"follower_port": "MOCK_F", "leader_port": "MOCK_L", **kwargs}
    with pytest.raises(ValueError):
        raw_teleop.teleoperate(**arguments)
