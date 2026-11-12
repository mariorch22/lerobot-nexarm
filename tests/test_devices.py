import json
import struct
from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from lerobot_robot_nexarm import NexArmFollower, NexArmFollowerConfig, NexArmLeader, NexArmLeaderConfig
from lerobot_robot_nexarm.bus import JOINT_NAMES, map_leader_to_follower
from lerobot_robot_nexarm.calibration import CalibrationError, JointNormalizer, save_calibration


@pytest.fixture
def follower(tmp_path, calibration):
    cfg = NexArmFollowerConfig(port="MOCK", id="follower", calibration_dir=tmp_path)
    save_calibration(tmp_path / "follower.json", calibration)
    return NexArmFollower(cfg)


@pytest.fixture
def leader(tmp_path, calibration):
    path = tmp_path / "follower.json"
    save_calibration(path, calibration)
    save_calibration(tmp_path / "leader.json", calibration, follower=False)
    cfg = NexArmLeaderConfig(
        port="MOCK", id="leader", calibration_dir=tmp_path, follower_calibration_path=path
    )
    return NexArmLeader(cfg)


def test_follower_connect_observe_write_disconnect(follower, calibration, serial_mock):
    follower.connect()
    assert serial_mock.commands()[:2] == [(68, b"\x01"), (98, b"\x01")]
    assert follower.is_connected
    obs = follower.get_observation()
    assert obs["shoulder_pan.pos"] == 0
    assert obs["gripper.pos"] == pytest.approx((2048 - 1195) * 100 / 1638)
    result = follower.send_action({f"{name}.pos": 1e10 for name in JOINT_NAMES})
    writes = [args for cmd, args in serial_mock.commands() if cmd == 97]
    assert struct.unpack("<6h", writes[0]) == (3500, 3500, 3500, 3500, 3500, 2833)
    assert result["gripper.pos"] == 100
    # Serial readback reports 2000, while dataset action must describe the sent 3500 target.
    assert result["shoulder_pan.pos"] == pytest.approx(1500 * 360 / 4095)
    assert serial_mock.commands()[-1][0] == 96
    follower.disconnect()
    assert serial_mock.commands()[-1] == (68, b"\x00")
    assert (98, b"\x00") not in serial_mock.commands()  # manufacturer default retained
    assert not serial_mock.is_open
    assert follower.supports_position_hold is False
    assert follower.supports_command_hold is False


def test_optional_torque_off_disconnect(follower, serial_mock):
    follower.config.disable_torque_on_disconnect = True
    follower.connect()
    follower.disconnect()
    assert serial_mock.commands()[-2:] == [(98, b"\x00"), (68, b"\x00")]


def test_optional_readback_and_return_of_sent_values(follower, serial_mock):
    follower.config.readback_after_write = False
    follower.connect()
    result = follower.send_action({f"{name}.pos": 0 for name in JOINT_NAMES})
    assert [cmd for cmd, _ in serial_mock.commands()] == [68, 98, 97]
    assert result["shoulder_pan.pos"] == 0


def test_readback_timeout_does_not_replace_targets(follower, serial_mock):
    follower.connect()
    serial_mock.drop_replies = True
    result = follower.send_action({f"{name}.pos": 10 for name in JOINT_NAMES})
    assert result["shoulder_pan.pos"] == pytest.approx(10, abs=360 / 4095)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_invalid_actions_send_no_partial_command(follower, serial_mock, bad):
    follower.connect()
    action = {f"{name}.pos": 0 for name in JOINT_NAMES}
    action["gripper.pos"] = bad
    with pytest.raises(ValueError):
        follower.send_action(action)
    assert not any(cmd == 97 for cmd, _ in serial_mock.commands())


def test_missing_calibration_allows_calibration_connection_but_no_actions(tmp_path, serial_mock):
    robot = NexArmFollower(NexArmFollowerConfig(port="MOCK", calibration_dir=tmp_path))
    robot.connect(calibrate=False)
    with pytest.raises(CalibrationError):
        robot.send_action({f"{name}.pos": 0 for name in JOINT_NAMES})
    robot.disconnect()
    assert all(args == b"\x00" for cmd, args in serial_mock.commands() if cmd == 98)


def test_placeholder_file_is_not_valid_calibration(follower, calibration, serial_mock):
    raw = {
        name: {"id": i + 1, "drive_mode": 0, "homing_offset": 2048, "range_min": 0, "range_max": 4095}
        for i, name in enumerate(JOINT_NAMES)
    }
    follower.calibration_fpath.write_text(json.dumps(raw))
    follower.connect(calibrate=False)
    assert not follower.is_calibrated
    with pytest.raises(CalibrationError):
        follower.send_action({f"{name}.pos": 0 for name in JOINT_NAMES})


def test_leader_fixed_mapping_then_follower_signs(leader, calibration, serial_mock):
    # Own leader calibration has different signs and ranges: these must NOT normalize actions.
    leader_own = {name: replace(c, drive_mode=1) for name, c in calibration.items()}
    save_calibration(leader.calibration_fpath, leader_own, follower=False)
    calibration["shoulder_lift"] = replace(calibration["shoulder_lift"], drive_mode=1)
    save_calibration(leader.config.follower_calibration_path, calibration)
    serial_mock.positions = [2000, 1000, 2000, 2000, 2000, 1800]
    leader.connect()
    result = leader.get_action()
    converter = JointNormalizer(calibration)
    mapped = map_leader_to_follower(serial_mock.positions)
    assert result == {
        f"{name}.pos": converter.normalize(name, mapped[i]) for i, name in enumerate(JOINT_NAMES)
    }
    assert result["shoulder_lift.pos"] < 0
    assert result["gripper.pos"] == pytest.approx((1841 - 1195) * 100 / 1638)
    leader.send_feedback(result)
    leader.disconnect()
    assert all(cmd not in (68, 97) for cmd, _ in serial_mock.commands())
    assert serial_mock.commands()[0] == (98, b"\x00")
    assert leader.feedback_features == {}


def test_missing_follower_reference_fails_before_port_open(leader, serial_mock):
    leader.config.follower_calibration_path.unlink()
    with pytest.raises(CalibrationError):
        leader.connect()
    assert serial_mock.writes == []


@pytest.mark.parametrize("role", ["follower", "leader"])
def test_successful_calibration_stays_off_until_reconnect(
    request, role, serial_mock, calibration, monkeypatch
):
    device = request.getfixturevalue(role)
    device.connect(calibrate=False)
    monkeypatch.setattr("builtins.input", lambda _: "c")
    monkeypatch.setattr("lerobot_robot_nexarm.calibration.record_calibration", lambda *_: calibration)
    device.calibrate()
    assert all(args == b"\x00" for cmd, args in serial_mock.commands() if cmd == 98)
    with pytest.raises(CalibrationError):
        if role == "follower":
            device.send_action({f"{name}.pos": 0 for name in JOINT_NAMES})
        else:
            device.get_action()
    device.disconnect()
    device.connect()
    if role == "follower":
        device.send_action({f"{name}.pos": 0 for name in JOINT_NAMES})
    else:
        assert device.get_action()
    device.disconnect()


def test_aborted_calibration_disables_torque_exits_bridge_and_keeps_file(follower, serial_mock, monkeypatch):
    before = follower.calibration_fpath.read_bytes()
    follower.connect(calibrate=False)
    monkeypatch.setattr("builtins.input", lambda _: "c")

    def abort(*_):
        raise KeyboardInterrupt

    monkeypatch.setattr("lerobot_robot_nexarm.calibration.record_calibration", abort)
    with pytest.raises(KeyboardInterrupt):
        follower.calibrate()
    assert serial_mock.commands()[-2:] == [(98, b"\x00"), (68, b"\x00")]
    assert not follower.bus.is_connected
    assert follower.calibration_fpath.read_bytes() == before


def test_camera_failure_cleans_up_torque_and_bridge(follower, serial_mock):
    camera = MagicMock()
    camera.connect.side_effect = RuntimeError("camera unavailable")
    follower.cameras = {"front": camera}
    with pytest.raises(RuntimeError, match="camera unavailable"):
        follower.connect()
    assert serial_mock.commands()[-2:] == [(98, b"\x00"), (68, b"\x00")]
    assert (98, b"\x01") not in serial_mock.commands()
    assert not serial_mock.is_open
    camera.disconnect.assert_called()


def test_stale_camera_fallback_and_configurable_feature_name(follower, serial_mock):
    camera = MagicMock(height=480, width=640, is_connected=True)
    camera.read_latest.side_effect = TimeoutError
    camera.async_read.return_value = "mock RGB frame"
    follower.cameras = {"custom_scene": camera}
    assert follower.observation_features["custom_scene"] == (480, 640, 3)
    follower.connect()
    assert follower.get_observation()["custom_scene"] == "mock RGB frame"
    camera.async_read.assert_called_once_with(timeout_ms=2000)
