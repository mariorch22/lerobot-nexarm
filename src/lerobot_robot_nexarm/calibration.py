"""Host-only calibration in LeRobot's per-joint MotorCalibration JSON format."""

import json
import logging
import math
import os
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from lerobot.motors import MotorCalibration
from lerobot.utils.utils import enter_pressed

from .bus import JOINT_NAMES, NexArmMotorsBus

logger = logging.getLogger(__name__)
GRIPPER_MIN = 1195
GRIPPER_MAX = 2833
DEGREES_PER_TICK = 360 / 4095


class CalibrationError(ValueError):
    """Calibration is missing, incomplete or unsafe to use."""


def validate_calibration(calibration: dict[str, MotorCalibration], *, follower: bool = True) -> None:
    if set(calibration) != set(JOINT_NAMES):
        raise CalibrationError("Calibration must contain exactly the six NexArm joint names; recalibrate.")
    if all(
        (c.range_min, c.range_max, c.homing_offset, c.drive_mode) == (0, 4095, 2048, 0)
        for c in calibration.values()
    ):
        raise CalibrationError("Old placeholder calibration detected; run lerobot-calibrate again.")
    for joint_id, name in enumerate(JOINT_NAMES, start=1):
        c = calibration[name]
        if any(type(value) is not int for value in asdict(c).values()):
            raise CalibrationError(f"{name}: all calibration fields must be integers.")
        if c.id != joint_id or c.drive_mode not in (0, 1):
            raise CalibrationError(f"{name}: expected id={joint_id} and drive_mode 0 (+) or 1 (-).")
        if c.range_min == c.range_max:
            raise CalibrationError(
                f"{name}: no raw position change recorded (min=max={c.range_min}). "
                "Check the arm/port assignment and torque release; do not force a blocked joint."
            )
        if not 0 <= c.range_min < c.range_max <= 4095:
            raise CalibrationError(f"{name}: require 0 <= range_min < range_max <= 4095.")
        if not c.range_min <= c.homing_offset <= c.range_max:
            raise CalibrationError(f"{name}: measured zero (homing_offset) must be inside its raw range.")
        if follower and name == "gripper" and not GRIPPER_MIN <= c.range_min < c.range_max <= GRIPPER_MAX:
            raise CalibrationError("Follower gripper calibration must lie inside raw [1195, 2833].")


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise CalibrationError(f"Duplicate calibration key: {key}")
        result[key] = value
    return result


def load_calibration(path: Path, *, follower: bool = True) -> dict[str, MotorCalibration]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_keys)
        calibration = {name: MotorCalibration(**fields) for name, fields in raw.items()}
        validate_calibration(calibration, follower=follower)
        return calibration
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        raise CalibrationError(f"Cannot use calibration {path}: {exc}") from exc


def save_calibration(path: Path, calibration: dict[str, MotorCalibration], *, follower: bool = True) -> None:
    validate_calibration(calibration, follower=follower)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({name: asdict(calibration[name]) for name in JOINT_NAMES}, stream, indent=4)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


class JointNormalizer:
    """Convert follower raw coordinates; homing_offset is the measured raw zero.

    The degree scale matches upstream. Explicit signs, clipping, measured zero and
    round() on the inverse are approved NexArm-specific extensions.
    """

    def __init__(self, calibration: dict[str, MotorCalibration], *, use_degrees: bool = True):
        validate_calibration(calibration)
        self.calibration = calibration
        self.use_degrees = use_degrees

    def normalize(self, name: str, raw: int | float) -> float:
        if not math.isfinite(raw):
            raise ValueError(f"{name}: position must be finite.")
        c = self.calibration[name]
        raw = min(c.range_max, max(c.range_min, raw))
        sign = -1 if c.drive_mode else 1
        if name == "gripper":
            value = (raw - c.range_min) * 100 / (c.range_max - c.range_min)
            return 100 - value if c.drive_mode else value
        if self.use_degrees:
            return sign * (raw - c.homing_offset) * DEGREES_PER_TICK
        return sign * (200 * (raw - c.range_min) / (c.range_max - c.range_min) - 100)

    def unnormalize(self, name: str, value: float) -> int:
        if not math.isfinite(value):
            raise ValueError(f"{name}: action must be finite.")
        c = self.calibration[name]
        sign = -1 if c.drive_mode else 1
        if name == "gripper":
            value = 100 - value if c.drive_mode else value
            value = min(100, max(0, value))
            raw = value * (c.range_max - c.range_min) / 100 + c.range_min
        elif self.use_degrees:
            # Clamp before multiplication so even finite, very large model outputs cannot overflow.
            unsigned = sign * value
            unsigned = min(
                (c.range_max - c.homing_offset) * DEGREES_PER_TICK,
                max((c.range_min - c.homing_offset) * DEGREES_PER_TICK, unsigned),
            )
            raw = unsigned / DEGREES_PER_TICK + c.homing_offset
        else:
            value = min(100, max(-100, sign * value))
            raw = (value + 100) * (c.range_max - c.range_min) / 200 + c.range_min
        return min(c.range_max, max(c.range_min, round(raw)))


class RangeRecorder:
    """Track all joints, aborting on apparent encoder-wrap-sized discontinuities."""

    def __init__(self, zero: list[int]):
        self.zero = list(zero)
        self.previous = list(zero)
        self.minimum = list(zero)
        self.maximum = list(zero)

    def update(self, positions: list[int]) -> None:
        if len(positions) != len(JOINT_NAMES):
            raise CalibrationError("Expected six raw encoder positions.")
        for i, name in enumerate(JOINT_NAMES):
            if abs(positions[i] - self.previous[i]) > 2048:
                raise CalibrationError(
                    f"{name}: apparent encoder transition 4095 <-> 0 (or sampling discontinuity). "
                    "Calibration aborted; use a non-wrapping range and move slowly."
                )
            self.minimum[i] = min(self.minimum[i], positions[i])
            self.maximum[i] = max(self.maximum[i], positions[i])
        self.previous = list(positions)

    def result(self, previous: dict[str, MotorCalibration]) -> dict[str, MotorCalibration]:
        return {
            name: MotorCalibration(
                id=i + 1,
                drive_mode=previous[name].drive_mode if name in previous else 0,
                homing_offset=self.zero[i],
                range_min=self.minimum[i],
                range_max=self.maximum[i],
            )
            for i, name in enumerate(JOINT_NAMES)
        }


def record_calibration(
    bus: NexArmMotorsBus, previous: dict[str, MotorCalibration]
) -> dict[str, MotorCalibration]:
    _confirm_enter_only(
        "With torque OFF, support the arm in the SO-101 middle/reference pose. Press ENTER to save zero. "
    )
    recorder = RangeRecorder(bus.read_positions())
    print(
        "Reference raw positions: "
        + ", ".join(f"{name}={raw}" for name, raw in zip(JOINT_NAMES, recorder.zero, strict=True))
    )
    for i, name in enumerate(JOINT_NAMES):
        _confirm_enter_only(f"Prepare to move {name} slowly through its usable range; press ENTER to start. ")
        print(f"Recording {name} (all joints monitored). Move by hand; press ENTER to finish this joint.")
        next_display = 0.0
        while True:
            recorder.update(bus.read_positions())
            now = time.monotonic()
            if now >= next_display:
                print(
                    f"\r{name}: raw={recorder.previous[i]:4d} "
                    f"min={recorder.minimum[i]:4d} max={recorder.maximum[i]:4d}",
                    end="",
                    flush=True,
                )
                next_display = now + 0.2
            if enter_pressed():
                break
            time.sleep(0.02)
        print(f"\n{name}: measured min={recorder.minimum[i]}, max={recorder.maximum[i]}")
        if recorder.minimum[i] == recorder.maximum[i]:
            raise CalibrationError(
                f"{name}: no raw position change recorded (min=max={recorder.minimum[i]}). "
                "Calibration aborted before saving. Check the arm/port assignment and torque release; "
                "do not force a blocked joint."
            )
    print("Measured raw ranges:")
    for i, name in enumerate(JOINT_NAMES):
        print(f"  {name}: zero={recorder.zero[i]}, min={recorder.minimum[i]}, max={recorder.maximum[i]}")
    return recorder.result(previous)


def _confirm_enter_only(prompt: str) -> None:
    if input(prompt).strip():
        raise CalibrationError(
            "Expected ENTER only. This is the calibration dialog, not PowerShell. "
            "Calibration aborted; run shell commands only after the PS prompt returns."
        )


class CalibrationMixin:
    """Shared host calibration lifecycle. Subclasses supply bus and _close()."""

    _follower_calibration = True

    def _load_calibration(self, fpath: Path | None = None) -> None:
        path = self.calibration_fpath if fpath is None else Path(fpath)
        try:
            self.calibration = load_calibration(path, follower=self._follower_calibration)
        except CalibrationError as exc:
            self.calibration = {}
            logger.warning("%s", exc)

    def _save_calibration(self, fpath: Path | None = None) -> None:
        path = self.calibration_fpath if fpath is None else Path(fpath)
        save_calibration(path, self.calibration, follower=self._follower_calibration)

    @property
    def is_calibrated(self) -> bool:
        try:
            validate_calibration(self.calibration, follower=self._follower_calibration)
        except CalibrationError:
            return False
        return True

    def calibrate(self) -> None:
        if not self.bus.is_connected:
            raise ConnectionError("Connect with calibrate=False before running calibration.")
        self._action_ready = False
        try:
            self.bus.set_torque(False)
            keep = (
                self.is_calibrated
                and input("Press ENTER to keep this calibration, or 'c' then ENTER to measure again: ")
                .strip()
                .lower()
                != "c"
            )
            if not keep:
                candidate = record_calibration(self.bus, self.calibration)
                save_calibration(self.calibration_fpath, candidate, follower=self._follower_calibration)
                self.calibration = candidate
            print(f"Calibration: {self.calibration_fpath}. Torque remains OFF; reconnect before control.")
        except BaseException:
            self._close(force_torque_off=True)
            raise
