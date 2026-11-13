import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def diagnostics():
    path = Path(__file__).resolve().parents[1] / "scripts" / "diagnose_nexarm.py"
    spec = importlib.util.spec_from_file_location("diagnose_nexarm", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("drop_replies", [False, True])
@pytest.mark.parametrize("startup_wait", [0.0, 2.0])
@pytest.mark.parametrize("probe", [False, True])
def test_diagnosis_logs_transport_and_cleans_up_without_motion_targets(
    diagnostics, serial_mock, capsys, drop_replies, startup_wait, probe
):
    serial_mock.drop_replies = drop_replies
    assert (
        diagnostics.diagnose("MOCK", reads=1, startup_wait=startup_wait, probe_before_torque_off=probe)
        is not drop_replies
    )
    commands = serial_mock.commands()
    assert commands[0] == (68, b"\x01")
    first_off = commands.index((98, b"\x00"))
    assert any(cmd == 96 for cmd, _ in commands[:first_off]) is probe
    assert commands[-2:] == [(98, b"\x00"), (68, b"\x00")]
    assert all(cmd in (68, 96, 98) for cmd, _ in commands)
    assert all(arg == b"\x00" for cmd, arg in commands if cmd == 98)
    assert not serial_mock.is_open
    output = capsys.readouterr().out
    assert "TX CMD 96" in output
    if drop_replies:
        assert "TIMEOUT:" in output
        assert "RX buffer" not in output
    else:
        assert "RX buffer" in output
        assert "Parsed CMD 96" in output
        assert "POSITIONS:" in output


def test_extra_wait_precedes_first_bridge_command(diagnostics, serial_mock, monkeypatch):
    events = []
    original_write = serial_mock.write

    def write(frame):
        events.append(("tx", frame[4]))
        return original_write(frame)

    monkeypatch.setattr(serial_mock, "write", write)
    monkeypatch.setattr(diagnostics.time, "sleep", lambda seconds: events.append(("sleep", seconds)))
    assert diagnostics.diagnose("MOCK", reads=1, startup_wait=2.0)
    assert events.index(("sleep", 2.0)) < events.index(("tx", 68))


@pytest.mark.parametrize("delay", [-1, 11, float("inf"), float("nan")])
def test_invalid_delay_does_not_open_port(diagnostics, monkeypatch, delay):
    def forbid_open(*args, **kwargs):
        raise AssertionError("Port must not be opened for invalid arguments")

    monkeypatch.setattr(diagnostics.TracingBus, "connect", forbid_open)
    with pytest.raises(ValueError, match="startup_wait"):
        diagnostics.diagnose("MOCK", startup_wait=delay)


def test_probe_distinguishes_reply_before_off_from_no_reply_after_off(
    diagnostics, serial_mock, monkeypatch, capsys
):
    from lerobot_robot_nexarm.bus import parse_frame

    original_write = serial_mock.write

    def write(frame):
        _, command, argument = parse_frame(frame)
        if command == 98 and argument == b"\x00":
            serial_mock.drop_replies = True
        return original_write(frame)

    monkeypatch.setattr(serial_mock, "write", write)
    assert not diagnostics.diagnose("MOCK", reads=1, probe_before_torque_off=True)
    output = capsys.readouterr().out
    assert "BEFORE torque-OFF: POSITIONS:" in output
    assert "Before torque-OFF: reply received=True" in output
    assert "Result: 0/1 reads returned positions." in output
    assert all(cmd != 97 for cmd, _ in serial_mock.commands())
    assert all(arg == b"\x00" for cmd, arg in serial_mock.commands() if cmd == 98)


def test_inactive_control_lines_are_set_before_port_open(diagnostics, serial_mock, monkeypatch, capsys):
    construction = []
    opened = []

    def create_closed_serial(**kwargs):
        construction.append(kwargs)
        serial_mock.is_open = False
        return serial_mock

    def open_port():
        # The native API must receive inactive states at open, not toggle them afterwards.
        opened.append((serial_mock.port, serial_mock.dtr, serial_mock.rts))
        serial_mock.is_open = True

    monkeypatch.setattr(diagnostics.serial, "Serial", create_closed_serial)
    monkeypatch.setattr(serial_mock, "open", open_port, raising=False)
    assert diagnostics.diagnose("MOCK", reads=1, inactive_control_lines=True)
    assert construction == [{"port": None, "baudrate": 1_000_000, "timeout": 0.05, "write_timeout": 0.05}]
    assert opened == [("MOCK", False, False)]
    assert "DTR=False, RTS=False" in capsys.readouterr().out
    assert serial_mock.commands()[0] == (68, b"\x01")
    assert serial_mock.commands()[-2:] == [(98, b"\x00"), (68, b"\x00")]
    assert all(cmd != 97 for cmd, _ in serial_mock.commands())
    assert all(arg == b"\x00" for cmd, arg in serial_mock.commands() if cmd == 98)
    assert not serial_mock.is_open


@pytest.mark.parametrize("version", [b"\x01\x02\x03", b"\x01\x02\x03\x04\x05\x06"])
def test_controller_probe_reads_version_without_bridge_or_torque_commands(
    diagnostics, serial_mock, monkeypatch, capsys, version
):
    from lerobot_robot_nexarm.bus import SYSTEM_ID, build_frame

    original_write = serial_mock.write

    def write(frame):
        result = original_write(frame)
        # A complete unrelated frame before the reply must not consume the version frame.
        serial_mock.buffer.extend(
            b"[CB] firmware query\r\n"
            + build_frame(SYSTEM_ID, 55, b"\x00")
            + build_frame(SYSTEM_ID, 1, version)
        )
        return result

    monkeypatch.setattr(serial_mock, "write", write)
    assert diagnostics.probe_controller("MOCK", startup_wait=5)
    assert serial_mock.writes == [bytes.fromhex("ff ff ff 02 01 fd")]
    assert not serial_mock.is_open
    output = capsys.readouterr().out
    assert "ESP32 firmware: 1.2.3" in output
    assert ("AT32 firmware: 4.5.6" in output) is (len(version) == 6)


@pytest.mark.parametrize("payload", [None, b"\x01\x02"])
def test_controller_probe_timeout_or_unknown_payload_does_not_send_fallback_commands(
    diagnostics, serial_mock, monkeypatch, capsys, payload
):
    from itertools import count

    from lerobot_robot_nexarm.bus import SYSTEM_ID, build_frame

    original_write = serial_mock.write

    def write(frame):
        result = original_write(frame)
        if payload is not None:
            serial_mock.buffer.extend(build_frame(SYSTEM_ID, 1, payload))
        return result

    monkeypatch.setattr(serial_mock, "write", write)
    monkeypatch.setattr(diagnostics.time, "monotonic", count(step=0.5).__next__)
    assert not diagnostics.probe_controller("MOCK")
    assert serial_mock.commands() == [(1, b"")]
    assert not serial_mock.is_open
    assert "TIMEOUT: no valid firmware-version reply" in capsys.readouterr().out


def test_controller_probe_closes_port_on_failed_write(diagnostics, serial_mock, monkeypatch):
    def failed_write(frame):
        raise OSError("test transport failure")

    monkeypatch.setattr(serial_mock, "write", failed_write)
    with pytest.raises(OSError, match="transport failure"):
        diagnostics.probe_controller("MOCK")
    assert not serial_mock.is_open


@pytest.mark.parametrize("delay", [-1, 11, float("inf"), float("nan")])
def test_invalid_controller_probe_delay_does_not_open_port(diagnostics, monkeypatch, delay):
    def forbid_open(*args, **kwargs):
        raise AssertionError("Port must not be opened for invalid arguments")

    monkeypatch.setattr(diagnostics.TracingBus, "connect", forbid_open)
    with pytest.raises(ValueError, match="startup_wait"):
        diagnostics.probe_controller("MOCK", startup_wait=delay)
