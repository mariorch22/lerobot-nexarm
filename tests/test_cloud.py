"""Cloud bridge logic without GPU, vast.ai, SSH or model weights."""

import base64
import importlib.util
import io
import sys
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


def test_train_script_follows_the_recipe_and_rejects_shell_characters():
    script = deploy.train_script("nexarm_f3a_stack_boxes_v1", "nexarm_lora", steps=40, resume=False)
    assert "--config_path=examples/flux3/lora.json" in script
    assert "--policy.path=models/flux-3-action-so101" in script
    assert "--dataset.root=/workspace/data/nexarm_f3a_stack_boxes_v1" in script
    assert "--output_dir=outputs/nexarm_lora" in script and script.rstrip().endswith("--steps=40")
    assert "--steps" not in deploy.train_script("data", "run", steps=None, resume=False)

    small = deploy.train_script("data", "run", steps=None, resume=False, batch_size=1)
    assert "--batch_size=1" in small and "--accelerator.gradient_accumulation.steps=8" in small
    assert "--steps=20000" in small and "--save_freq=1000" in small  # same samples, divisible by 8

    resumed = deploy.train_script("data", "run", steps=40, resume=True)
    assert "--resume=true" in resumed and "train_config.json" in resumed and "--steps" not in resumed

    with pytest.raises(SystemExit):
        deploy.train_script("data; rm -rf /", "run", steps=None, resume=False)


def test_training_table_condenses_the_log_and_names_checkpoints():
    line = "INFO 11:13:19 ot_train.py:894 step:{} smpl:20 loss:{} grdn:3.6 lr:1.0e-04 video_mse:0.1 action_mse:{}"
    log = "\n".join(line.format(step, 1 / step, 2 / step) for step in range(20, 2020, 20))
    log += "\nINFO ot_train.py:900 Eval loss on held-out episodes: 0.31\nTraining: 100%|###| 2000/2000"
    table = deploy.training_table(log, rows=10).splitlines()
    assert table[0].split() == ["step", "loss", "action_mse", "video_mse"]
    assert 10 <= len([row for row in table if row.strip()[:1].isdigit()]) <= 12
    assert table[1].split()[0] == "20" and "2000" in table[-4]  # first and last training line are kept
    assert table[-1].endswith("Eval loss on held-out episodes: 0.31")
    assert "no evaluation line" in deploy.training_table(line.format(20, 0.5, 0.4))

    assert deploy.checkpoint(None) == "last" and deploy.checkpoint(3000) == "003000"


def test_directories_survive_the_tar_stream_used_for_uploads(tmp_path):
    import subprocess
    import tarfile

    source = tmp_path / "dataset"
    (source / "meta").mkdir(parents=True)
    (source / "meta" / "info.json").write_text("{}")
    (source / "data.bin").write_bytes(bytes(range(256)) * 100)
    # The same writer deploy.upload_dir uses, into a local process instead of ssh.
    unpack = "import sys, tarfile; tarfile.open(fileobj=sys.stdin.buffer, mode='r|')"
    unpack += ".extractall(sys.argv[1], filter='data')"
    reader = subprocess.Popen([sys.executable, "-c", unpack, str(tmp_path / "copy")], stdin=subprocess.PIPE)
    with tarfile.open(fileobj=reader.stdin, mode="w|") as tar:
        tar.add(source, arcname=source.name)
    reader.stdin.close()
    assert reader.wait() == 0
    assert (tmp_path / "copy" / "dataset" / "data.bin").read_bytes() == (source / "data.bin").read_bytes()
    assert (tmp_path / "copy" / "dataset" / "meta" / "info.json").read_text() == "{}"


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
