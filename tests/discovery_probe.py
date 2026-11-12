"""Fresh interpreter probe: never import the plugin before upstream's scanner."""

import importlib.metadata
import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

import draccus
from lerobot.utils.import_utils import register_third_party_plugins

assert "lerobot_robot_nexarm" not in sys.modules
assert importlib.metadata.metadata("lerobot_robot_nexarm")["Name"] == "lerobot_robot_nexarm"
register_third_party_plugins()

from lerobot.robots import RobotConfig, make_robot_from_config  # noqa: E402
from lerobot.teleoperators import TeleoperatorConfig, make_teleoperator_from_config  # noqa: E402

directory = Path(sys.argv[1])


@dataclass
class DevicesConfig:
    robot: RobotConfig
    teleop: TeleoperatorConfig


with patch("serial.Serial", side_effect=AssertionError("Hardware access forbidden")):
    configs = draccus.parse(
        DevicesConfig,
        args=[
            "--robot.type=nexarm_follower",
            "--robot.port=MOCK",
            f"--robot.calibration_dir={directory}",
            "--teleop.type=nexarm_leader",
            "--teleop.port=MOCK",
            f"--teleop.calibration_dir={directory}",
            f"--teleop.follower_calibration_path={directory / 'follower.json'}",
        ],
    )
    robot = make_robot_from_config(configs.robot)
    teleop = make_teleoperator_from_config(configs.teleop)
    assert robot.name == "nexarm_follower" and not robot.is_connected
    assert teleop.name == "nexarm_leader" and not teleop.is_connected
    assert len(robot.action_features) == len(teleop.action_features) == 6
print("Installed metadata discovery, config parsing and both factories passed without connect().")
