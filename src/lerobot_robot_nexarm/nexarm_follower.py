import contextlib
import logging

from lerobot.cameras import make_cameras_from_configs
from lerobot.lerobot_types import RobotAction, RobotObservation
from lerobot.robots import Robot

from .bus import JOINT_NAMES, NexArmMotorsBus
from .calibration import CalibrationError, CalibrationMixin, JointNormalizer
from .config_nexarm import NexArmFollowerConfig

logger = logging.getLogger(__name__)


class NexArmFollower(CalibrationMixin, Robot):
    config_class = NexArmFollowerConfig
    name = "nexarm_follower"
    # Deliberately inherit both hold capability flags as False.

    def __init__(self, config: NexArmFollowerConfig):
        self._action_ready = False
        self._bridge_entered = False
        super().__init__(config)
        self.config = config
        self.bus = NexArmMotorsBus(port=config.port, baudrate=config.baudrate)
        self.cameras = make_cameras_from_configs(config.cameras)

    @property
    def action_features(self) -> dict[str, type]:
        return {f"{name}.pos": float for name in JOINT_NAMES}

    @property
    def observation_features(self) -> dict[str, type | tuple]:
        return {
            **self.action_features,
            **{name: (cam.height, cam.width, 3) for name, cam in self.cameras.items()},
        }

    @property
    def is_connected(self) -> bool:
        return self.bus.is_connected and all(cam.is_connected for cam in self.cameras.values())

    def connect(self, calibrate: bool = True) -> None:
        if self.bus.is_connected:
            return
        self._action_ready = False
        self.calibration = {}
        if self.calibration_fpath.is_file():
            self._load_calibration()
        try:
            self.bus.connect()
            # Set before sending so a partially failed bridge-enter is also cleaned up.
            self._bridge_entered = True
            self.bus.enter_lerobot_mode()
            if calibrate and self.is_calibrated:
                self._action_ready = True
            elif calibrate:
                self.calibrate()  # Stays torque off; reconnect required after measuring.
            if not self._action_ready:
                self.configure()  # Calibration path is off before any camera setup.
            for camera in self.cameras.values():
                camera.connect()
            if self._action_ready:
                self.configure()  # Preserve manufacturer ordering: cameras first, normal torque-on last.
        except BaseException:
            self._close(force_torque_off=True)
            raise

    def configure(self) -> None:
        # A calibration-only connection must never enable torque.
        if not self.bus.is_connected:
            raise ConnectionError("NexArm follower is not connected.")
        self.bus.set_torque(self._action_ready and self.is_calibrated)

    def get_observation(self) -> RobotObservation:
        if not self.is_connected:
            raise ConnectionError("NexArm follower is not connected.")
        normalizer = JointNormalizer(self.calibration, use_degrees=self.config.use_degrees)
        positions = self.bus.read_positions()
        observation = {
            f"{name}.pos": normalizer.normalize(name, raw)
            for name, raw in zip(JOINT_NAMES, positions, strict=True)
        }
        for name, camera in self.cameras.items():
            try:
                observation[name] = camera.read_latest()
            except TimeoutError:
                logger.warning("%s: stale frame, falling back to async_read", name)
                observation[name] = camera.async_read(timeout_ms=2000)
        return observation

    def send_action(self, action: RobotAction) -> RobotAction:
        if not self.is_connected:
            raise ConnectionError("NexArm follower is not connected.")
        if not self._action_ready or not self.is_calibrated:
            raise CalibrationError(
                "Actions disabled: calibrate, set directions, then disconnect and reconnect."
            )
        if not self.action_features.keys() <= action.keys():
            raise ValueError("A complete six-joint position action is required.")
        normalizer = JointNormalizer(self.calibration, use_degrees=self.config.use_degrees)
        # Validate and convert the entire action before writing any bytes.
        goals = [normalizer.unnormalize(name, float(action[f"{name}.pos"])) for name in JOINT_NAMES]
        self.bus.write_positions(goals)
        if self.config.readback_after_write:
            try:
                self.bus.read_positions()  # Keep manufacturer's I/O timing; never use as dataset action.
            except TimeoutError:
                logger.debug("Position readback timed out after write", exc_info=True)
        return {
            f"{name}.pos": normalizer.normalize(name, raw)
            for name, raw in zip(JOINT_NAMES, goals, strict=True)
        }

    def _close(self, *, force_torque_off: bool = False) -> None:
        for camera in self.cameras.values():
            with contextlib.suppress(Exception):
                camera.disconnect()
        if self.bus.is_connected:
            try:
                if force_torque_off or not self._action_ready or self.config.disable_torque_on_disconnect:
                    try:
                        self.bus.set_torque(False)
                    except Exception:
                        logger.exception("Could not disable NexArm torque during cleanup")
            finally:
                try:
                    if self._bridge_entered:
                        try:
                            self.bus.exit_lerobot_mode()
                        except Exception:
                            logger.exception("Could not exit NexArm bridge mode during cleanup")
                finally:
                    self.bus.disconnect()
        self._bridge_entered = False
        self._action_ready = False

    def disconnect(self) -> None:
        self._close()
