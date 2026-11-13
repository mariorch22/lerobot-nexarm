import importlib.util
import math
import struct
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from lerobot_robot_nexarm.bus import parse_frame


@pytest.fixture(autouse=True)
def forbid_real_cameras_and_viewer(monkeypatch):
    monkeypatch.setattr("cv2.VideoCapture", MagicMock(side_effect=AssertionError("Real cameras forbidden")))
    monkeypatch.setattr(
        "lerobot.utils.visualization_utils.init_rerun",
        MagicMock(side_effect=AssertionError("Real viewer forbidden")),
    )


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
    monkeypatch.setattr(raw_teleop.time, "perf_counter", lambda: clock[0])
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


def test_load_existing_camera_example_without_loading_calibration(raw_teleop):
    from lerobot.cameras.opencv import OpenCVCameraConfig

    path = Path(__file__).resolve().parents[1] / "examples" / "nexarm" / "teleoperate.yaml"
    configs = raw_teleop.load_camera_configs(path)
    assert list(configs) == ["front", "wrist"]
    for name, index in [("front", 1), ("wrist", 2)]:
        assert isinstance(configs[name], OpenCVCameraConfig)
        assert configs[name].index_or_path == index
        assert (configs[name].width, configs[name].height, configs[name].fps) == (640, 480, 30)
        assert configs[name].fourcc == "MJPG"


def test_custom_camera_name_index_and_settings(raw_teleop, tmp_path):
    path = tmp_path / "cameras.yaml"
    path.write_text(
        "robot:\n"
        "  port: DO_NOT_OPEN\n"
        "  calibration_dir: nonexistent\n"
        "  cameras:\n"
        "    scene:\n"
        "      type: opencv\n"
        "      index_or_path: 4\n"
        "      width: 1280\n"
        "      height: 720\n"
        "      fps: 20\n"
        "      fourcc: MJPG\n",
        encoding="utf-8",
    )
    configs = raw_teleop.load_camera_configs(path)
    assert list(configs) == ["scene"]
    assert configs["scene"].index_or_path == 4
    assert (configs["scene"].width, configs["scene"].height, configs["scene"].fps) == (1280, 720, 20)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "[]",
        "robot: {}",
        "robot: {cameras: {}}",
        "robot: {cameras: []}",
        "robot: {cameras: {front: {type: unknown_camera}}}",
        "robot: {cameras: {front: {type: opencv, index_or_path: 1, typo: 123}}}",
        "robot: {cameras: {'': {type: opencv, index_or_path: 1}}}",
        "robot: {cameras: {shoulder_pan.pos: {type: opencv, index_or_path: 1}}}",
        "robot: [invalid yaml",
    ],
)
def test_invalid_camera_config_fails_without_hardware(raw_teleop, tmp_path, content):
    path = tmp_path / "invalid.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        raw_teleop.load_camera_configs(path)


@pytest.fixture
def camera_setup(raw_teleop, arms, monkeypatch):
    from lerobot.cameras import ColorMode
    from lerobot.cameras.opencv import OpenCVCameraConfig

    _, _, events = arms
    frame = np.arange(12, dtype=np.uint8).reshape(2, 2, 3)
    cameras = {}
    configs = {}
    for name, index in [("front", 1), ("wrist", 2)]:
        camera = MagicMock(color_mode=ColorMode.RGB)
        camera.read_latest.return_value = frame
        camera.async_read.return_value = frame
        camera.connect.side_effect = lambda name=name: events.append(("camera", name))
        cameras[name] = camera
        configs[name] = OpenCVCameraConfig(index_or_path=index, width=640, height=480, fps=30, fourcc="MJPG")
    factory = MagicMock(return_value=cameras)
    monkeypatch.setattr(raw_teleop, "make_cameras_from_configs", factory)
    viewer = MagicMock()
    monkeypatch.setattr(raw_teleop, "RawTeleopViewer", MagicMock(return_value=viewer))
    return configs, cameras, frame, viewer, factory


def test_camera_view_logs_images_and_raw_values_with_original_motor_mapping(raw_teleop, arms, camera_setup):
    configs, cameras, frame, viewer, factory = camera_setup
    follower, leader, events = arms
    assert (
        raw_teleop.teleoperate("MOCK_F", "MOCK_L", duration=1 / 30, camera_configs=configs, display_data=True)
        == 1
    )
    factory.assert_called_once_with(configs)
    assert [event[:2] for event in events[:4]] == [
        ("camera", "front"),
        ("camera", "wrist"),
        ("open", "MOCK_L"),
        ("tx", "MOCK_L"),
    ]
    viewer.connect.assert_called_once_with(cameras)
    data = viewer.log.call_args.kwargs
    assert data["observation"]["front"] is frame
    assert data["observation"]["wrist"] is frame
    assert data["observation"]["shoulder_lift.pos"] == 2100
    assert data["action"]["shoulder_lift.pos"] == 3096
    assert data["action"]["gripper.pos"] == 1841
    assert follower.commands() == [
        (68, b"\x01"),
        (98, b"\x01"),
        (96, b""),
        (97, struct.pack("<6h", 2000, 3096, 2200, 2300, 1800, 1841)),
        (96, b""),
        (68, b"\x00"),
    ]
    for camera in cameras.values():
        camera.read_latest.assert_called_once_with()
        camera.disconnect.assert_called_once_with()
    viewer.disconnect.assert_called_once_with()
    assert not follower.is_open and not leader.is_open


def test_camera_stale_frame_uses_manufacturer_async_fallback(raw_teleop, camera_setup):
    configs, cameras, frame, viewer, _ = camera_setup
    cameras["front"].read_latest.side_effect = TimeoutError("stale frame")
    raw_teleop.teleoperate("MOCK_F", "MOCK_L", duration=1 / 30, camera_configs=configs, display_data=True)
    cameras["front"].async_read.assert_called_once_with(timeout_ms=2000)
    assert viewer.log.call_args.kwargs["observation"]["front"] is frame


def test_bgr_camera_is_converted_to_rgb_without_modifying_original(raw_teleop, camera_setup):
    from lerobot.cameras import ColorMode

    _, cameras, frame, _, _ = camera_setup
    cameras["front"].color_mode = ColorMode.BGR
    original = frame.copy()
    result = raw_teleop._read_camera(cameras["front"], "front")
    np.testing.assert_array_equal(result, original[..., ::-1])
    np.testing.assert_array_equal(frame, original)


def test_headless_cameras_still_read_frames_without_starting_viewer(raw_teleop, camera_setup):
    configs, cameras, _, viewer, _ = camera_setup
    raw_teleop.teleoperate("MOCK_F", "MOCK_L", duration=1 / 30, camera_configs=configs)
    for camera in cameras.values():
        camera.read_latest.assert_called_once_with()
        camera.disconnect.assert_called_once_with()
    assert viewer.mock_calls == []


def test_camera_connect_failure_cleans_up_before_any_serial_open(raw_teleop, arms, camera_setup):
    configs, cameras, _, viewer, _ = camera_setup
    _, _, events = arms
    cameras["wrist"].connect.side_effect = OSError("camera unavailable")
    with pytest.raises(OSError, match="camera unavailable"):
        raw_teleop.teleoperate("MOCK_F", "MOCK_L", camera_configs=configs, display_data=True)
    assert not any(event[0] == "open" for event in events)
    for camera in cameras.values():
        camera.disconnect.assert_called_once_with()
    viewer.disconnect.assert_called_once_with()


@pytest.mark.parametrize("failure", [TimeoutError("no frames"), KeyboardInterrupt()])
def test_camera_read_failure_sends_no_target_and_closes_all_devices(raw_teleop, arms, camera_setup, failure):
    configs, cameras, _, viewer, _ = camera_setup
    follower, leader, _ = arms
    cameras["front"].read_latest.side_effect = failure
    cameras["front"].async_read.side_effect = failure
    with pytest.raises(type(failure)):
        raw_teleop.teleoperate("MOCK_F", "MOCK_L", camera_configs=configs, display_data=True)
    assert not any(command == 97 for command, _ in follower.commands())
    assert follower.commands()[-1] == (68, b"\x00")
    assert not follower.is_open and not leader.is_open
    for camera in cameras.values():
        camera.disconnect.assert_called_once_with()
    viewer.disconnect.assert_called_once_with()


def test_serial_failure_also_closes_cameras_and_viewer(raw_teleop, arms, camera_setup):
    configs, cameras, _, viewer, _ = camera_setup
    follower, leader, _ = arms
    leader.drop_replies = True
    with pytest.raises(TimeoutError, match="Leader on MOCK_L"):
        raw_teleop.teleoperate("MOCK_F", "MOCK_L", camera_configs=configs, display_data=True)
    assert not any(command == 97 for command, _ in follower.commands())
    assert not follower.is_open and not leader.is_open
    for camera in cameras.values():
        camera.disconnect.assert_called_once_with()
    viewer.disconnect.assert_called_once_with()


@pytest.mark.parametrize("display_args, expected", [([], True), (["--no-display-data"], False)])
@pytest.mark.parametrize("fps_args", [[], ["--show-fps"]])
def test_cli_camera_config_enables_viewer_unless_disabled(
    raw_teleop, monkeypatch, display_args, expected, fps_args
):
    path = Path(__file__).resolve().parents[1] / "examples" / "nexarm" / "teleoperate.yaml"
    run = MagicMock()
    monkeypatch.setattr(raw_teleop, "teleoperate", run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "teleoperate_raw.py",
            "--follower-port=MOCK_F",
            "--leader-port=MOCK_L",
            f"--camera-config={path}",
            *display_args,
            *fps_args,
        ],
    )
    raw_teleop.main()
    assert run.call_args.args == ("MOCK_F", "MOCK_L", 30.0, None)
    assert list(run.call_args.kwargs["camera_configs"]) == ["front", "wrist"]
    assert run.call_args.kwargs["display_data"] is expected
    assert run.call_args.kwargs["show_fps"] is bool(fps_args)


@pytest.mark.parametrize(
    "target, io_delay, measured, loop_ms, work_ms",
    [(5, 0, "5.0", "200.0", "0.0"), (30, 0.1, "10.0", "100.0", "100.0")],
)
def test_real_loop_fps_includes_pacing_and_slow_serial_io(
    raw_teleop, arms, monkeypatch, capsys, target, io_delay, measured, loop_ms, work_ms
):
    follower, leader, _ = arms
    original_write = follower.write

    def delayed_write(frame):
        if frame[4] == 97:
            raw_teleop.time.sleep(io_delay)  # Advance the fake clock; no real sleep or device.
        return original_write(frame)

    monkeypatch.setattr(follower, "write", delayed_write)
    steps = raw_teleop.teleoperate("MOCK_F", "MOCK_L", fps=target, duration=1.1, show_fps=True)
    output = capsys.readouterr().out
    assert f"Measured FPS: {measured} | loop: {loop_ms} ms | work: {work_ms} ms | target: {target}" in output
    assert f"Overall FPS: {measured} ({steps} completed loops" in output
    assert not follower.is_open and not leader.is_open


def test_short_run_reports_fps_without_waiting_for_one_second(raw_teleop, arms, capsys):
    raw_teleop.teleoperate("MOCK_F", "MOCK_L", duration=1 / 30, show_fps=True)
    output = capsys.readouterr().out
    assert "Measured FPS:" not in output
    assert "Overall FPS: 30.0 (1 completed loops" in output


def test_pacing_and_measurement_use_high_resolution_clock_on_windows(raw_teleop, arms, monkeypatch, capsys):
    follower, _, _ = arms
    original_write = follower.write

    # Reproduce Python 3.12's distinct Windows clocks: coarse monotonic, precise perf_counter.
    monkeypatch.setattr(
        raw_teleop.time,
        "monotonic",
        lambda: math.floor(raw_teleop.time.perf_counter() / 0.015625) * 0.015625,
    )

    def delayed_write(frame):
        if frame[4] == 97:
            raw_teleop.time.sleep(0.025)
        return original_write(frame)

    monkeypatch.setattr(follower, "write", delayed_write)
    raw_teleop.teleoperate("MOCK_F", "MOCK_L", fps=30, duration=1.1, show_fps=True)
    output = capsys.readouterr().out
    assert "Measured FPS: 30.0 | loop: 33.3 ms | work: 25.0 ms | target: 30" in output
    assert "Overall FPS: 30.0" in output


def test_viewer_setup_failure_still_cleans_up_without_opening_ports(raw_teleop, arms, camera_setup):
    configs, cameras, _, viewer, _ = camera_setup
    _, _, events = arms
    viewer.connect.side_effect = RuntimeError("blueprint setup failed")
    with pytest.raises(RuntimeError, match="blueprint setup failed"):
        raw_teleop.teleoperate("MOCK_F", "MOCK_L", camera_configs=configs, display_data=True)
    viewer.disconnect.assert_called_once_with()
    assert not any(event[0] == "open" for event in events)
    for camera in cameras.values():
        camera.connect.assert_not_called()
