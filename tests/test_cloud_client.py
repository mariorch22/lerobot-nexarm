"""Cloud client loop against a fake follower and the mock server. No hardware, no network."""

import base64
import importlib.util
import json
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"cloud_{name}", ROOT / "cloud" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


client = load("client")


class Robot(client.FakeRobot):
    def __init__(self):
        super().__init__()
        self.sent = []

    def send_action(self, action):
        self.sent.append([action[key] for key in client.KEYS])
        return super().send_action(action)


def plan_towards(offset: float, calls: list | None = None):
    """Fake server: 32 commands that move every arm joint by `offset` degrees per plan."""

    def predict(task, frames):
        if calls is not None:
            calls.append(frames)
        state = frames[-1]["state"]
        return {
            "commands": [[v + offset * (i + 1) / 32 for v in state[:5]] + [state[5]] for i in range(32)],
            "seconds": 0.0,
        }

    return predict


def fast(robot, predict, **options):
    return client.Client(robot, predict, "pick up the block", fps=2000, **options)


def test_image_is_squashed_to_256_and_keeps_rgb_order():
    red = np.zeros((480, 640, 3), dtype=np.uint8)
    red[..., 0] = 255
    jpeg = np.frombuffer(base64.b64decode(client.encode_image(red)), dtype=np.uint8)
    decoded = cv2.imdecode(jpeg, cv2.IMREAD_COLOR)[..., ::-1]  # back to RGB
    assert decoded.shape == (256, 256, 3)
    assert decoded[..., 0].mean() > 240 and decoded[..., 2].mean() < 15


def test_jump_guard_uses_separate_limits_for_arm_and_gripper():
    state = [0, 0, 0, 0, 0, 50]
    assert client.jump(state, [15, -15, 0, 0, 0, 80], 15, 30) is None
    assert client.jump(state, [0, 0, 15.1, 0, 0, 50], 15, 30).startswith("elbow_flex")
    assert client.jump(state, [0, 0, 0, 0, 0, 81], 15, 30).startswith("gripper")


def test_dry_run_never_sends_and_never_claims_a_command():
    robot, calls = Robot(), []
    assert fast(robot, plan_towards(3, calls)).run(duration=1.0) == "duration reached"  # room for two plans
    assert robot.sent == []
    assert len(calls) >= 2
    assert all(frame["last_command"] is None for frames in calls for frame in frames)


def test_execute_sends_32_commands_and_reports_them_as_history():
    robot, calls = Robot(), []
    predict = plan_towards(3, calls)

    def two_plans(task, frames):
        if len(calls) == 2:
            raise OSError("stop after two plans")
        return predict(task, frames)

    assert fast(robot, two_plans, execute=True).run() == "server: stop after two plans"
    assert len(robot.sent) == 64
    first, second = calls
    assert len(first) == 1 and first[0]["last_command"] is None  # episode start
    assert len(second) == 8  # the newest eight ticks, oldest first
    assert [frame["last_command"] for frame in second] == robot.sent[24:32]
    assert [frame["state"] for frame in second] == robot.sent[24:32]  # the fake arm reached each command


def test_jump_guard_stops_before_anything_is_sent():
    robot = Robot()
    reason = fast(robot, plan_towards(32 * 20), execute=True).run()  # first command is 20 degrees away
    assert reason.startswith("jump guard rejected plan 1: shoulder_pan")
    assert robot.sent == []


def test_server_timeout_stops_the_loop():
    def predict(task, frames):
        raise TimeoutError("timed out")

    assert fast(Robot(), predict, execute=True).run() == "server: timed out"


def test_ctrl_c_propagates_so_main_can_disconnect():
    def predict(task, frames):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        fast(Robot(), predict).run()


def test_chunk_runs_at_30_hz_and_is_logged(tmp_path):
    robot, log = Robot(), tmp_path / "client.jsonl"
    predict = plan_towards(3)
    calls = []

    def one_plan(task, frames):
        if calls:
            raise OSError("done")
        calls.append(frames)
        return predict(task, frames)

    start = time.perf_counter()
    client.Client(robot, one_plan, "pick up the block", execute=True, log_path=log).run()
    elapsed = time.perf_counter() - start
    assert 32 / 30 <= elapsed < 32 / 30 + 0.4
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["plan"] == 1 and entry["executed"] is True and len(entry["first"]) == 6


def test_example_config_builds_the_follower_without_hardware(tmp_path, calibration, monkeypatch):
    from lerobot_robot_nexarm.calibration import CalibrationError, save_calibration

    monkeypatch.chdir(tmp_path)  # calibration_dir in the example is relative
    config = ROOT / "examples" / "nexarm" / "inference.yaml"
    with pytest.raises(CalibrationError):
        client.load_follower(config)  # no calibration yet: refuse before connecting
    save_calibration(tmp_path / "calibration" / "follower" / "follower.json", calibration)
    robot = client.load_follower(config)
    assert set(robot.cameras) == {"scene", "wrist"} and not robot.is_connected


def test_client_against_the_mock_server():
    pytest.importorskip("fastapi", reason="run with: uv run --with fastapi --with httpx pytest")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    server = load("server")
    api = TestClient(server.create_app(server.MockModel))
    while api.get("/health").json()["status"] == "loading":
        pass
    statuses = []

    def predict(task, frames):
        response = api.post("/predict", json={"task": task, "frames": frames})
        statuses.append(response.status_code)
        if len(statuses) == 3:
            raise OSError("stop after two plans")
        return response.json()

    robot = Robot()
    fast(robot, predict, execute=True).run()
    assert statuses == [200, 200, 200]  # also the eight-frame request with real commands is accepted
    assert robot.sent == [[0.0, 0.0, 0.0, 0.0, 0.0, 50.0]] * 64  # the mock repeats the state
