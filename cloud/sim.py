"""A simulated NexArm follower in MuJoCo, as a stand-in robot for cloud/client.py.

It tests the control loop with moving images and real physics. It does not show whether
the model solves the task on the real arm: the images are rendered, and the joint zero
is an assumption (see ASSUMPTIONS below).

The arm model is not part of this repo. Clone https://github.com/khanhthanhdev/lerobot-nexarm
(with `git lfs pull --include "sim/assets/**"`) and pass its sim/description/mjcf/scene.xml.

ASSUMPTIONS. They are guesses that place the arm inside the value range the SO-101
checkpoint was trained on (its dataset_statistics.json); nothing here is measured:
- shoulder_lift is 90 with the upper arm vertical and grows when it leans forward.
- elbow_flex is 90 with the forearm at a right angle and reaches 180 fully stretched.
- shoulder_pan, wrist_flex and wrist_roll are 0 in the CAD home pose, directions as in the model.
- Gripper 0 is closed and 54 is fully open.
"""

import math
from pathlib import Path

import cv2
import mujoco
import numpy as np

from lerobot_robot_nexarm.bus import JOINT_NAMES

KEYS = [f"{name}.pos" for name in JOINT_NAMES]
JOINTS = [
    "joint_1_base_to_link_1",
    "joint_2_link_1_to_link_2",
    "joint_3_link_2_to_link_3",
    "joint_4_link_3_to_link_4",
    "joint_5_link_4_to_link_5",
    "right_jaw_slide_joint",
]
JAW_OPEN = 0.0255  # metres of jaw travel when fully open
GRIPPER_OPEN = 54.0  # gripper value when fully open
SIGN = [1, -1, -1, 1, 1]  # model units -> direction of the MuJoCo joint
OFFSET = [0.0, 90.0, 90.0, 0.0, 0.0]  # model units in the CAD home pose
START = [0.0, 120.0, 110.0, 60.0, 0.0, 40.0]  # leaning over the table, gripper mostly open
HEIGHT, WIDTH = 480, 640


def look_at(position, target) -> list[float]:
    """Camera x and y axes for a camera at `position` looking at `target`, z up."""
    forward = np.subtract(target, position)
    forward = forward / np.linalg.norm(forward)
    right = np.cross(forward, [0.0, 0.0, 1.0])
    right = right / np.linalg.norm(right)
    return [*right, *np.cross(right, forward)]


def build_model(scene: Path) -> mujoco.MjModel:
    """Load the arm scene and swap its demo objects for our task: a small and a big box."""
    spec = mujoco.MjSpec.from_file(str(scene))
    for key in list(spec.keys):  # they list the old objects' positions
        spec.delete(key)
    for name in ("cube", "target_zone"):
        spec.delete(spec.body(name))
    boxes = {
        "big_box": ([-0.07, -0.25, 0.02], [0.03, 0.03, 0.02], [0.92, 0.9, 0.85, 1]),
        "small_box": ([0.06, -0.25, 0.0125], [0.0125, 0.0125, 0.0125], [0.95, 0.75, 0.1, 1]),
    }
    for name, (position, half_size, colour) in boxes.items():
        body = spec.worldbody.add_body(name=name, pos=position)
        body.add_freejoint()
        body.add_geom(
            type=mujoco.mjtGeom.mjGEOM_BOX, size=half_size, rgba=colour, mass=0.02,
            friction=[1.2, 0.01, 0.001], contype=2, conaffinity=3,
        )  # fmt: skip
    position = [0.45, -0.7, 0.55]  # fixed camera, roughly where the lab's scene camera stands
    spec.worldbody.add_camera(
        name="scene", pos=position, xyaxes=look_at(position, [0.0, -0.15, 0.1]), fovy=50
    )
    return spec.compile()


class MujocoRobot:
    """Same interface as the follower: degrees and gripper value in, images and state out."""

    def __init__(self, scene: Path, video: Path | None = None, fps: float = 30.0):
        self.model = build_model(scene)
        self.data = mujoco.MjData(self.model)
        self.video, self.fps = video, fps
        self.steps = round(1 / fps / self.model.opt.timestep)  # physics steps per control tick
        self.qpos = [self.model.joint(name).qposadr[0] for name in JOINTS]
        self.limits = self.model.actuator_ctrlrange.copy()  # actuators are in joint order
        self.renderer = None
        self.frames = []

    def to_sim(self, values: list[float]) -> np.ndarray:
        """Model units -> radians and jaw travel, clipped to the joint limits."""
        targets = [math.radians(s * (v - o)) for v, s, o in zip(values[:5], SIGN, OFFSET, strict=True)]
        targets.append(values[5] / GRIPPER_OPEN * JAW_OPEN)
        return np.clip(targets, self.limits[:, 0], self.limits[:, 1])

    def from_sim(self, positions) -> list[float]:
        """Radians and jaw travel -> model units."""
        values = [s * math.degrees(p) + o for p, s, o in zip(positions[:5], SIGN, OFFSET, strict=True)]
        return [*values, float(positions[5]) / JAW_OPEN * GRIPPER_OPEN]

    def connect(self):
        self.renderer = mujoco.Renderer(self.model, HEIGHT, WIDTH)
        start = self.to_sim(START)
        self.data.qpos[self.qpos] = start
        self.data.qpos[self.model.joint("left_jaw_slide_joint").qposadr[0]] = start[5]
        self.data.ctrl[:] = start
        mujoco.mj_step(self.model, self.data, 500)  # let arm and boxes settle

    def disconnect(self):
        if self.renderer is not None:
            self.renderer.close()
        if self.video is not None and self.frames:
            self.video.parent.mkdir(parents=True, exist_ok=True)
            height, width = self.frames[0].shape[:2]
            writer = cv2.VideoWriter(
                str(self.video), cv2.VideoWriter_fourcc(*"mp4v"), self.fps, (width, height)
            )
            for frame in self.frames:
                writer.write(frame[..., ::-1])  # OpenCV wants BGR
            writer.release()
            print(f"Video: {self.video} ({len(self.frames)} frames)")

    def render(self, camera: str) -> np.ndarray:
        self.renderer.update_scene(self.data, camera=camera)
        return self.renderer.render().copy()

    def get_observation(self) -> dict:
        state = self.from_sim(self.data.qpos[self.qpos])
        scene, wrist = self.render("scene"), self.render("wrist")
        if self.video is not None:
            self.frames.append(np.hstack([scene, wrist]))
        return {**dict(zip(KEYS, state, strict=True)), "scene": scene, "wrist": wrist}

    def send_action(self, action: dict) -> dict:
        targets = self.to_sim([float(action[key]) for key in KEYS])
        self.data.ctrl[:] = targets
        mujoco.mj_step(self.model, self.data, self.steps)
        return dict(zip(KEYS, self.from_sim(targets), strict=True))  # really commanded, after clipping
