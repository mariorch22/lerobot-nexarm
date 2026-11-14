"""Compare the model's plans with what the human did, on recorded episodes. No robot needed.

    uv run python cloud/replay_eval.py --dataset outputs/datasets/NAME --episodes 14 15 16 17

At several moments of an episode it sends the eight recorded ticks up to that moment to the
running server (cloud/server.py behind the tunnel), exactly as cloud/client.py would, and
compares the 32 planned commands with the 32 commands the human gave next.

Use held-out episodes: LeRobot's LoRA recipe trains on the first 80 % and keeps the last 20 %.
"hold" is the error of not moving at all (repeating the last command); a useful model is
clearly below it. A low error here does not prove that the arm solves the task.
"""

import argparse
from pathlib import Path

import av
import numpy as np
import pandas as pd
from client import HISTORY, encode_image, http_predict

from lerobot_robot_nexarm.bus import JOINT_NAMES


def video_frames(root: Path, episode: pd.Series, camera: str, indices: set[int]) -> dict[int, np.ndarray]:
    """Decode the wanted frames of one episode; indices count from the episode start."""
    key = f"videos/observation.images.{camera}"
    path = (
        root
        / f"videos/observation.images.{camera}"
        / f"chunk-{int(episode[f'{key}/chunk_index']):03d}"
        / f"file-{int(episode[f'{key}/file_index']):03d}.mp4"
    )
    start = round(float(episode[f"{key}/from_timestamp"]) * 30)
    found = {}
    with av.open(str(path)) as container:
        for number, frame in enumerate(container.decode(container.streams.video[0])):
            if number - start in indices:
                found[number - start] = frame.to_ndarray(format="rgb24")
            if number - start >= max(indices):
                break
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--dataset", type=Path, required=True, help="local LeRobot dataset directory")
    parser.add_argument("--episodes", type=int, nargs="+", required=True)
    parser.add_argument("--moments", type=int, default=6, help="plans per episode (default 6)")
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    root = args.dataset
    data = pd.concat(pd.read_parquet(f) for f in sorted((root / "data").rglob("*.parquet")))
    episodes = pd.concat(pd.read_parquet(f) for f in sorted((root / "meta/episodes").rglob("*.parquet")))
    episodes = episodes.set_index("episode_index")
    task = pd.read_parquet(root / "meta/tasks.parquet").index[0]
    predict = http_predict(args.url, args.timeout)

    model_errors, hold_errors = [], []
    for number in args.episodes:
        rows = data[data["episode_index"] == number]
        states = np.stack(rows["observation.state"].to_numpy()).astype(float)
        actions = np.stack(rows["action"].to_numpy()).astype(float)
        moments = [int(m) for m in np.linspace(HISTORY, len(rows) - 33, args.moments)]
        wanted = {i for m in moments for i in range(m - HISTORY + 1, m + 1)}
        images = {
            camera: video_frames(root, episodes.loc[number], camera, wanted) for camera in ("scene", "wrist")
        }
        for moment in moments:
            frames = [
                {
                    "image_scene": encode_image(images["scene"][i]),
                    "image_wrist": encode_image(images["wrist"][i]),
                    "state": states[i].tolist(),
                    "last_command": actions[i - 1].tolist(),  # the command sent right before this tick
                }
                for i in range(moment - HISTORY + 1, moment + 1)
            ]
            planned = np.array(predict(task, frames)["commands"])
            human = actions[moment : moment + 32]
            model_error = np.abs(planned - human).mean(axis=0)
            hold_error = np.abs(actions[moment - 1] - human).mean(axis=0)
            model_errors.append(model_error)
            hold_errors.append(hold_error)
            print(
                f"episode {number:2d} tick {moment:4d}: model {model_error[:5].mean():5.1f} deg, "
                f"hold {hold_error[:5].mean():5.1f} deg, gripper {model_error[5]:5.1f} / {hold_error[5]:5.1f}"
            )

    model, hold = np.mean(model_errors, axis=0), np.mean(hold_errors, axis=0)
    print(f"\nTask: {task}\nMean absolute error over {len(model_errors)} plans of 32 commands:")
    for name, m, h in zip(JOINT_NAMES, model, hold, strict=True):
        print(f"  {name:14s} model {m:6.2f}   hold {h:6.2f}")
    print(f"  arm joints     model {model[:5].mean():6.2f}   hold {hold[:5].mean():6.2f}   (degrees)")


if __name__ == "__main__":
    main()
