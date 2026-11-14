"""Cloud bridge logic without GPU, vast.ai, SSH or model weights."""

import base64
import importlib.util
import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

CLOUD = Path(__file__).resolve().parents[1] / "cloud"


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"cloud_{name}", CLOUD / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


deploy = load("deploy")


def test_cheapest_offer_is_chosen_and_price_limit_applies():
    offers = [{"id": 1, "dph_total": 0.7}, {"id": 2, "dph_total": 0.5}]
    assert deploy.cheapest_offer(offers, max_price=1.0)["id"] == 2
    with pytest.raises(SystemExit):
        deploy.cheapest_offer(offers, max_price=0.4)
    with pytest.raises(SystemExit):
        deploy.cheapest_offer([], max_price=1.0)


def test_ssh_endpoint_prefers_direct_port_and_falls_back_to_proxy():
    proxy = {"ssh_host": "ssh5.vast.ai", "ssh_port": 12345}
    direct = {**proxy, "public_ipaddr": "1.2.3.4 ", "ports": {"22/tcp": [{"HostPort": "40022"}]}}
    assert deploy.ssh_endpoint(direct) == ("1.2.3.4", 40022)
    assert deploy.ssh_endpoint(proxy) == ("ssh5.vast.ai", 12345)
    assert deploy.ssh_endpoint({"actual_status": "loading"}) is None


def jpeg(color) -> str:
    stream = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(stream, format="JPEG")
    return base64.b64encode(stream.getvalue()).decode()


@pytest.fixture(scope="module")
def server():
    pytest.importorskip("fastapi", reason="run with: uv run --with fastapi --with httpx pytest")
    return load("server")


def test_image_decoding_and_history_padding(server):
    image = server.decode_image(jpeg((255, 0, 0)))
    assert image.shape == (3, 48, 64) and image.dtype == np.float32
    assert image[0].mean() > 0.9 and image[1].mean() < 0.1  # RGB order, range 0..1

    frames = [server.Frame(image_scene="a", image_wrist="b", state=[float(i)] * 6) for i in range(3)]
    padded = server.pad_frames(frames, 8)
    assert [f.state[0] for f in padded] == [0, 0, 0, 0, 0, 0, 1, 2]  # oldest repeated in front
    assert [f.state[0] for f in server.pad_frames(frames * 4, 8)] == [1, 2, 0, 1, 2, 0, 1, 2]


def test_sweep_mock_moves_in_small_steps_from_the_measured_state(server):
    state = [0.0, 0.0, 0.0, 0.0, 0.0, 50.0]
    frame = server.Frame(image_scene="a", image_wrist="b", state=state)
    commands = server.SweepModel().predict(server.PredictRequest(task="x", frames=[frame]))
    assert len(commands) == 32
    steps = np.abs(np.diff([state, *commands], axis=0))
    assert steps[:, :5].max() <= 0.5 and steps[:, 5].max() <= 3.0  # no jump, also not on the first command
    assert steps.sum() > 10  # it really moves


def test_mock_server_returns_32_commands(server):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    client = TestClient(server.create_app(server.MockModel))
    while client.get("/health").json()["status"] == "loading":
        pass
    state = [1.0, 2.0, 3.0, 4.0, 5.0, 50.0]
    frame = {"image_scene": jpeg((0, 0, 0)), "image_wrist": jpeg((0, 0, 0)), "state": state}
    response = client.post("/predict", json={"task": "pick up the blue block", "frames": [frame]})
    assert response.status_code == 200
    assert response.json()["commands"] == [state] * 32
    assert client.post("/predict", json={"task": "x", "frames": []}).status_code == 422
