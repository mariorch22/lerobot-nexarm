from dataclasses import dataclass, field
from pathlib import Path

from lerobot.cameras import CameraConfig
from lerobot.robots import RobotConfig
from lerobot.teleoperators import TeleoperatorConfig


@RobotConfig.register_subclass("nexarm_follower")
@dataclass
class NexArmFollowerConfig(RobotConfig):
    port: str
    baudrate: int = 1_000_000
    cameras: dict[str, CameraConfig] = field(default_factory=dict)
    use_degrees: bool = True
    disable_torque_on_disconnect: bool = False
    readback_after_write: bool = True


@TeleoperatorConfig.register_subclass("nexarm_leader")
@dataclass
class NexArmLeaderConfig(TeleoperatorConfig):
    port: str
    # Required explicitly: the leader emits targets in this follower's coordinate system.
    follower_calibration_path: Path
    baudrate: int = 1_000_000
    use_degrees: bool = True
