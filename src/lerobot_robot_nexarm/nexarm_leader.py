import contextlib
from typing import Any

from lerobot.teleoperators import Teleoperator

from .bus import JOINT_NAMES, NexArmMotorsBus, map_leader_to_follower
from .calibration import CalibrationError, CalibrationMixin, JointNormalizer, load_calibration
from .config_nexarm import NexArmLeaderConfig


class NexArmLeader(CalibrationMixin, Teleoperator):
    config_class = NexArmLeaderConfig
    name = "nexarm_leader"
    _follower_calibration = False

    def __init__(self, config: NexArmLeaderConfig):
        self._action_ready = False
        super().__init__(config)
        self.config = config
        self.bus = NexArmMotorsBus(port=config.port, baudrate=config.baudrate)
        self._follower_normalizer = None

    @property
    def action_features(self) -> dict[str, type]:
        return {f"{name}.pos": float for name in JOINT_NAMES}

    @property
    def feedback_features(self) -> dict[str, type]:
        return {}

    @property
    def is_connected(self) -> bool:
        return self.bus.is_connected

    def connect(self, calibrate: bool = True) -> None:
        if self.bus.is_connected:
            return
        self._action_ready = False
        self._follower_normalizer = None
        self.calibration = {}
        if self.calibration_fpath.is_file():
            self._load_calibration()
        # Validate the referenced follower BEFORE opening the leader port for normal operation.
        if calibrate:
            follower_calibration = load_calibration(self.config.follower_calibration_path)
            self._follower_normalizer = JointNormalizer(
                follower_calibration, use_degrees=self.config.use_degrees
            )
        try:
            self.bus.connect()
            self.configure()
            if calibrate and self.is_calibrated:
                self._action_ready = True
            elif calibrate:
                self.calibrate()
        except BaseException:
            self._close(force_torque_off=True)
            raise

    def configure(self) -> None:
        if not self.bus.is_connected:
            raise ConnectionError("NexArm leader is not connected.")
        self.bus.set_torque(False)

    def get_action(self) -> dict[str, float]:
        if not self.is_connected:
            raise ConnectionError("NexArm leader is not connected.")
        if not self._action_ready or not self.is_calibrated or self._follower_normalizer is None:
            raise CalibrationError(
                "Leader actions disabled: calibrate and reconnect with follower calibration."
            )
        # Preserve both fixed mappings; apply signs once, in the FOLLOWER coordinate system.
        targets = map_leader_to_follower(self.bus.read_positions())
        return {
            f"{name}.pos": self._follower_normalizer.normalize(name, raw)
            for name, raw in zip(JOINT_NAMES, targets, strict=True)
        }

    def send_feedback(self, feedback: dict[str, Any]) -> None:
        """No active leader feedback capability is advertised or implemented."""

    def _close(self, *, force_torque_off: bool = False) -> None:
        if self.bus.is_connected:
            if force_torque_off:
                with contextlib.suppress(Exception):
                    self.bus.set_torque(False)
            self.bus.disconnect()
        self._action_ready = False
        self._follower_normalizer = None

    def disconnect(self) -> None:
        self._close()
