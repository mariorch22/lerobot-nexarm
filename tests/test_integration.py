import importlib.metadata
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import draccus
import pytest

ROOT = Path(__file__).resolve().parents[1]
PIN = "2f05d8f64d62a865c368a9fdf0ba3d8423e28035"


def test_installed_git_dependency_is_exact_pin():
    dist = importlib.metadata.distribution("lerobot")
    source = json.loads(dist.read_text("direct_url.json"))
    assert source["vcs_info"]["commit_id"] == PIN


def test_discovery_in_fresh_interpreter(tmp_path):
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "tests" / "discovery_probe.py"), str(tmp_path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "both factories passed" in result.stdout


@pytest.mark.parametrize("name", ["teleoperate", "record", "inference"])
def test_example_uses_actual_pinned_cli_schema_without_hardware(name):
    from lerobot.utils.import_utils import register_third_party_plugins

    register_third_party_plugins()
    if name == "teleoperate":
        from lerobot.scripts.lerobot_teleoperate import TeleoperateConfig as Config
    elif name == "record":
        from lerobot.scripts.lerobot_record import RecordConfig as Config
    else:
        from lerobot.configs.policies import PreTrainedConfig
        from lerobot.policies.act.configuration_act import ACTConfig
        from lerobot.rollout.configs import RolloutConfig as Config

    # Exercise the real rollout schema with an actual lightweight policy CONFIG;
    # no model implementation, network, tensors or GPU initialization is needed.
    path = ROOT / "examples" / "nexarm" / f"{name}.yaml"
    with patch("serial.Serial", side_effect=AssertionError("Hardware access forbidden")):
        if name == "inference":
            with (
                patch("lerobot.rollout.configs.parser.get_path_arg", return_value="MOCK_POLICY"),
                patch.object(PreTrainedConfig, "from_pretrained", return_value=ACTConfig(device="cpu")),
            ):
                config = draccus.parse(Config, config_path=path, args=[])
        else:
            config = draccus.parse(Config, config_path=path, args=[])
    assert config.robot.type == "nexarm_follower"
    assert config.robot.cameras["scene"].fourcc == "MJPG"
    assert config.robot.cameras["wrist"].fps == 30
    if name != "inference":
        assert config.teleop.type == "nexarm_leader"
        assert config.teleop.follower_calibration_path == Path("calibration/follower/follower.json")
    else:
        assert config.return_to_initial_position is False


def test_camera_free_example_and_actual_port_overrides():
    from lerobot.scripts.lerobot_teleoperate import TeleoperateConfig
    from lerobot.utils.import_utils import register_third_party_plugins

    register_third_party_plugins()
    with patch("serial.Serial", side_effect=AssertionError("Hardware access forbidden")):
        config = draccus.parse(
            TeleoperateConfig,
            config_path=ROOT / "examples" / "nexarm" / "teleoperate_no_cameras.yaml",
            args=["--robot.port=COM13", "--teleop.port=COM14"],
        )
    assert config.robot.cameras == {}
    assert config.robot.port == "COM13"
    assert config.teleop.port == "COM14"
