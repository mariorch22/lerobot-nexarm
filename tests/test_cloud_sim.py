"""Simulated follower for the cloud client. Needs mujoco and the external arm model, else skipped."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCENE = ROOT / "third_party" / "khanhthanhdev-lerobot-nexarm" / "sim" / "description" / "mjcf" / "scene.xml"

pytest.importorskip("mujoco", reason="run with: uv run --with mujoco pytest")
if not SCENE.is_file():
    pytest.skip("arm model not cloned into third_party/ (see cloud/README.md)", allow_module_level=True)

spec = importlib.util.spec_from_file_location("cloud_sim", ROOT / "cloud" / "sim.py")
sim = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sim)


def test_simulated_arm_follows_commands_and_clips_them():
    robot = sim.MujocoRobot(SCENE)
    robot.connect()
    try:
        observation = robot.get_observation()
        assert observation["scene"].shape == observation["wrist"].shape == (480, 640, 3)
        assert [observation[key] for key in sim.KEYS] == pytest.approx(sim.START, abs=1.0)

        target = [20.0, -10.0, -30.0, 40.0, 10.0, 50.0]
        for step in range(60):  # two seconds, like two thirds of a plan and its successor
            command = [s + (t - s) * (step + 1) / 60 for s, t in zip(sim.START, target, strict=True)]
            robot.send_action(dict(zip(sim.KEYS, command, strict=True)))
        for _ in range(15):
            robot.send_action(dict(zip(sim.KEYS, target, strict=True)))
        reached = robot.get_observation()
        assert [reached[key] for key in sim.KEYS] == pytest.approx(target, abs=3.0)

        sent = robot.send_action(dict(zip(sim.KEYS, [999.0, 0, 0, 0, 0, 150.0], strict=True)))
        assert sent["shoulder_pan.pos"] == pytest.approx(135.0) and sent["gripper.pos"] == pytest.approx(
            100.0
        )
    finally:
        robot.disconnect()
