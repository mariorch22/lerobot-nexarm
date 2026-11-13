import json
from dataclasses import replace
from unittest.mock import Mock

import pytest

from lerobot_robot_nexarm.bus import JOINT_NAMES
from lerobot_robot_nexarm.calibration import (
    CalibrationError,
    JointNormalizer,
    RangeRecorder,
    load_calibration,
    record_calibration,
    save_calibration,
    validate_calibration,
)


@pytest.mark.parametrize("use_degrees", [True, False])
@pytest.mark.parametrize("sign", [0, 1])
@pytest.mark.parametrize("name", JOINT_NAMES)
def test_all_joint_roundtrips(calibration, use_degrees, sign, name):
    calibration[name] = replace(calibration[name], drive_mode=sign)
    converter = JointNormalizer(calibration, use_degrees=use_degrees)
    c = calibration[name]
    for raw in (c.range_min, c.range_min + 1, c.homing_offset, 2111, c.range_max - 1, c.range_max):
        assert converter.unnormalize(name, converter.normalize(name, raw)) == raw


def test_degree_scale_zero_sign_and_rounding(calibration):
    calibration["shoulder_pan"] = replace(calibration["shoulder_pan"], drive_mode=1, homing_offset=2100)
    converter = JointNormalizer(calibration)
    assert converter.normalize("shoulder_pan", 2100) == 0
    assert converter.normalize("shoulder_pan", 2200) == pytest.approx(-100 * 360 / 4095)
    assert converter.unnormalize("shoulder_pan", -0.6 * 360 / 4095) == 2101


@pytest.mark.parametrize("name", JOINT_NAMES)
@pytest.mark.parametrize("use_degrees", [True, False])
def test_sign_flip_changes_forward_values_not_just_roundtrip(calibration, name, use_degrees):
    plain = JointNormalizer(calibration, use_degrees=use_degrees)
    raw = calibration[name].range_min
    before = plain.normalize(name, raw)
    flipped = dict(calibration)
    flipped[name] = replace(calibration[name], drive_mode=1)
    inverted = JointNormalizer(flipped, use_degrees=use_degrees)
    assert inverted.normalize(name, raw) == pytest.approx(100 - before if name == "gripper" else -before)
    if name == "gripper":
        assert before == 0
    elif not use_degrees:
        assert before == -100


@pytest.mark.parametrize("sign", [0, 1])
@pytest.mark.parametrize("name", JOINT_NAMES)
def test_clipping_is_in_calibrated_raw_space(calibration, sign, name):
    calibration[name] = replace(calibration[name], drive_mode=sign)
    converter = JointNormalizer(calibration)
    c = calibration[name]
    high = converter.unnormalize(name, 1e308)
    low = converter.unnormalize(name, -1e308)
    assert {high, low} == {c.range_min, c.range_max}
    assert converter.normalize(name, -100) == converter.normalize(name, c.range_min)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_reject_nonfinite(calibration, value):
    converter = JointNormalizer(calibration)
    with pytest.raises(ValueError, match="finite"):
        converter.unnormalize("gripper", value)


def test_json_roundtrip_and_manual_direction_edit(tmp_path, calibration):
    path = tmp_path / "follower.json"
    save_calibration(path, calibration)
    raw = json.loads(path.read_text())
    raw["elbow_flex"]["drive_mode"] = 1
    path.write_text(json.dumps(raw))
    restored = load_calibration(path)
    assert restored["elbow_flex"].drive_mode == 1
    assert restored["gripper"] == calibration["gripper"]


@pytest.mark.parametrize(
    "defect", ["missing", "id", "sign", "zero", "range", "gripper", "type", "placeholder"]
)
def test_reject_invalid_or_placeholder_calibration(calibration, defect):
    if defect == "missing":
        del calibration["gripper"]
    elif defect == "placeholder":
        calibration = {
            name: replace(c, range_min=0, range_max=4095, homing_offset=2048, drive_mode=0)
            for name, c in calibration.items()
        }
    else:
        field, value = {
            "id": ("id", 6),
            "sign": ("drive_mode", -1),
            "zero": ("homing_offset", 0),
            "range": ("range_max", 500),
            "gripper": ("range_min", 1194),
            "type": ("drive_mode", True),
        }[defect]
        name = "gripper" if defect == "gripper" else "shoulder_pan"
        calibration[name] = replace(calibration[name], **{field: value})
    with pytest.raises(CalibrationError):
        validate_calibration(calibration)


def test_bad_json_and_duplicate_keys(tmp_path):
    path = tmp_path / "invalid.json"
    for value in ('{"a":1,"a":2}', "[]", "{broken"):
        path.write_text(value)
        with pytest.raises(CalibrationError):
            load_calibration(path)


def test_range_recorder_detects_wrap_and_preserves_zero_and_sign(calibration):
    recorder = RangeRecorder([2000] * 6)
    recorder.update([1000] * 6)
    recorder.update([3000] * 6)
    previous = {"shoulder_pan": replace(calibration["shoulder_pan"], drive_mode=1)}
    result = recorder.result(previous)
    assert result["shoulder_pan"].homing_offset == 2000
    assert result["shoulder_pan"].drive_mode == 1
    assert result["gripper"].range_min == 1000
    recorder.update([4090] * 6)
    with pytest.raises(CalibrationError, match="encoder transition"):
        recorder.update([5] * 6)


def test_interactive_two_stage_measurement_records_raw_reference_and_ranges(monkeypatch, calibration):
    zero = [2000] * 5 + [2048]
    low = [1000] * 5 + [1195]
    high = [3000] * 5 + [2833]
    bus = Mock()
    bus.read_positions.side_effect = [zero] + [row for _ in JOINT_NAMES for row in (low, high)]
    endings = iter([False, True] * 6)
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr("lerobot_robot_nexarm.calibration.enter_pressed", lambda: next(endings))
    monkeypatch.setattr("lerobot_robot_nexarm.calibration.time.sleep", lambda _: None)
    calibration["shoulder_pan"] = replace(calibration["shoulder_pan"], drive_mode=1)
    result = record_calibration(bus, calibration)
    assert result["shoulder_pan"].homing_offset == 2000
    assert result["shoulder_pan"].range_min == 1000
    assert result["shoulder_pan"].range_max == 3000
    assert result["shoulder_pan"].drive_mode == 1
    assert result["gripper"].homing_offset == 2048
    assert result["gripper"].range_min == 1195
    assert result["gripper"].range_max == 2833


def test_shell_command_at_reference_prompt_cannot_save_accidental_zero(monkeypatch):
    bus = Mock()
    monkeypatch.setattr("builtins.input", lambda _: "uv run lerobot-teleoperate --robot.port=COM11")
    with pytest.raises(CalibrationError, match="not PowerShell"):
        record_calibration(bus, {})
    bus.read_positions.assert_not_called()


def test_stalled_joint_shows_raw_values_and_aborts_before_remaining_joints(monkeypatch, capsys):
    bus = Mock()
    bus.read_positions.return_value = [2000] * 6
    prompt = Mock(return_value="")
    monkeypatch.setattr("builtins.input", prompt)
    monkeypatch.setattr("lerobot_robot_nexarm.calibration.enter_pressed", lambda: True)
    with pytest.raises(CalibrationError, match=r"shoulder_pan: no raw position change.*min=max=2000"):
        record_calibration(bus, {})
    output = capsys.readouterr().out
    assert "shoulder_pan: raw=2000 min=2000 max=2000" in output
    assert "shoulder_pan: measured min=2000, max=2000" in output
    assert prompt.call_count == 2  # Only reference and first-joint prompts; no five wasted measurements.


def test_validation_reports_actual_unchanged_encoder_value(calibration):
    calibration["shoulder_pan"] = replace(calibration["shoulder_pan"], range_min=2000, range_max=2000)
    with pytest.raises(CalibrationError, match=r"shoulder_pan: no raw position change.*min=max=2000"):
        validate_calibration(calibration)
