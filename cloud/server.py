# /// script
# requires-python = ">=3.12"
# dependencies = ["fastapi", "uvicorn", "pillow", "numpy"]
# ///
"""FLUX 3 Action inference server for the NexArm. Runs on the GPU instance.

    python server.py            real model, needs the LeRobot environment from setup_remote.sh
    uv run server.py --mock     no model: returns the measured state 32 times (local client tests)

The server only listens on 127.0.0.1:8000 and is reached through an SSH tunnel.
It keeps no state between requests: every plan resets the policy and both processors.
"""

import argparse
import base64
import io
import threading
import time
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel, Field

MODELS = Path(__file__).resolve().parent / "lerobot" / "models"
POLICY_DIR = MODELS / "flux-3-action-so101"
ENCODERS_DIR = MODELS / "flux-3-action-base"


class Frame(BaseModel):
    """One control tick. Arm joints in degrees, gripper 0..100, same order as the plugin."""

    image_scene: str  # base64 JPEG, fixed scene camera
    image_wrist: str  # base64 JPEG, wrist camera
    state: list[float] = Field(min_length=6, max_length=6)
    # Command that was sent to the arm right before this tick; None at episode start.
    last_command: list[float] | None = Field(default=None, min_length=6, max_length=6)


class PredictRequest(BaseModel):
    task: str
    # Oldest first, newest last. The checkpoint wants n_obs_steps (8) frames; if fewer
    # are sent (episode start), the oldest frame is repeated, like LeRobot's own runner does.
    frames: list[Frame] = Field(min_length=1)


class PredictResponse(BaseModel):
    commands: list[list[float]]  # n_action_steps (32) absolute commands, same units as state
    seconds: float


def decode_image(encoded: str) -> np.ndarray:
    """base64 JPEG -> float32 array (3, H, W) in [0, 1]. No resize; the model does that."""
    image = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")
    return np.asarray(image, dtype=np.float32).transpose(2, 0, 1) / 255


def pad_frames(frames: list[Frame], n: int) -> list[Frame]:
    """Keep the newest n frames; repeat the oldest one at the front if there are fewer."""
    frames = frames[-n:]
    return [frames[0]] * (n - len(frames)) + frames


class MockModel:
    name = "mock"
    n_action_steps = 32

    def predict(self, request: PredictRequest) -> list[list[float]]:
        return [list(request.frames[-1].state)] * self.n_action_steps


class Flux3Model:
    """The SO-101 checkpoint with its saved processors, loaded as in the LeRobot F3A docs."""

    def __init__(self, adapter: Path | None = None, text_encoder_on_cpu: bool = False):
        import torch
        from lerobot.policies.factory import make_pre_post_processors
        from lerobot.policies.flux3 import Flux3Config, Flux3Policy

        self.torch = torch
        config = Flux3Config.from_pretrained(str(POLICY_DIR))
        config.device = "cuda"
        config.video_vae_id = str(ENCODERS_DIR / "video_vae.safetensors")
        config.text_encoder_id = str(ENCODERS_DIR / "text_encoder")
        self.policy = Flux3Policy.from_pretrained(str(POLICY_DIR), config=config).eval()
        if adapter is not None:  # optional LoRA adapter trained on our own data
            from peft import PeftModel

            self.policy = PeftModel.from_pretrained(self.policy, str(adapter)).eval()
        # An adapter directory carries its own saved processors; otherwise use the base ones.
        self.preprocessor, self.postprocessor = make_pre_post_processors(
            config,
            pretrained_path=str(adapter or POLICY_DIR),
            preprocessor_overrides={"device_processor": {"device": "cuda"}},
            postprocessor_overrides={"device_processor": {"device": "cpu"}},
        )
        if text_encoder_on_cpu:  # saves about 8 GiB of VRAM
            self.policy.frozen.text_encoder.cpu()
        self.name = torch.cuda.get_device_name(0)
        self.n_obs_steps = config.n_obs_steps
        self.n_action_steps = config.n_action_steps

    def predict(self, request: PredictRequest) -> list[list[float]]:
        torch = self.torch
        frames = pad_frames(request.frames, self.n_obs_steps)
        # History inputs need an explicit batch dimension: (1, T, ...).
        batch = {
            "observation.state": torch.tensor([f.state for f in frames])[None],
            # Anchor for integrating the predicted deltas into absolute commands.
            "observation.command_history": torch.tensor([f.last_command or f.state for f in frames])[None],
            "observation.images.scene": torch.from_numpy(
                np.stack([decode_image(f.image_scene) for f in frames])
            )[None],
            "observation.images.wrist": torch.from_numpy(
                np.stack([decode_image(f.image_wrist) for f in frames])
            )[None],
            "task": [request.task],
        }
        self.policy.reset()
        self.preprocessor.reset()
        self.postprocessor.reset()
        with torch.inference_mode():
            chunk = self.policy.predict_action_chunk(self.preprocessor(batch))  # normalized, (1, 42, 6)
            commands = self.postprocessor(chunk)  # absolute degrees / gripper percent
        return commands[0, : self.n_action_steps].float().cpu().tolist()


def create_app(load_model) -> FastAPI:
    app = FastAPI(title="NexArm F3A inference")
    state = {"status": "loading", "model": None, "error": None}
    lock = threading.Lock()  # one GPU, one robot: one prediction at a time

    def load():
        try:
            state["model"] = load_model()
            state["status"] = "ready"
        except Exception as exc:
            state["status"], state["error"] = "error", f"{type(exc).__name__}: {exc}"
            raise

    # Load in the background so /health answers while the weights are loading (about 80 s).
    threading.Thread(target=load, daemon=True).start()

    @app.get("/health")
    def health():
        model = state["model"]
        return {"status": state["status"], "model": model.name if model else None, "error": state["error"]}

    @app.post("/predict")
    def predict(request: PredictRequest) -> PredictResponse:
        if state["status"] != "ready":
            raise HTTPException(503, f"model is {state['status']}")
        start = time.perf_counter()
        with lock:
            commands = state["model"].predict(request)
        return PredictResponse(commands=commands, seconds=time.perf_counter() - start)

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--mock", action="store_true", help="no model, repeat the state 32 times")
    parser.add_argument("--adapter", type=Path, help="LoRA adapter directory (optional)")
    parser.add_argument("--text-encoder-on-cpu", action="store_true")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    import uvicorn

    if args.mock:
        load_model = MockModel
    else:

        def load_model():
            return Flux3Model(args.adapter, args.text_encoder_on_cpu)

    uvicorn.run(create_app(load_model), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
