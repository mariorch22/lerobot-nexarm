"""Human-run NexArm raw teleoperation, optionally with cameras and a live Rerun view."""

import argparse
import contextlib
import logging
import math
import time
from pathlib import Path

from lerobot.cameras import Camera, CameraConfig, ColorMode, make_cameras_from_configs

from lerobot_robot_nexarm.bus import JOINT_NAMES, map_leader_to_follower
from lerobot_robot_nexarm.validated_bus import ValidatedNexArmMotorsBus
from lerobot_robot_nexarm.visualization import RawTeleopViewer

logger = logging.getLogger(__name__)


def load_camera_configs(path: Path) -> dict[str, CameraConfig]:
    """Read only robot.cameras; never load calibration or open hardware from this YAML."""
    import draccus
    from draccus.cfgparsing import load_config
    from lerobot.cameras.opencv import OpenCVCameraConfig  # noqa: F401 (register the camera type)

    try:
        with path.open(encoding="utf-8") as stream:
            config = load_config(stream, file=path)
        robot = config.get("robot") if isinstance(config, dict) else None
        cameras = robot.get("cameras") if isinstance(robot, dict) else None
        if not isinstance(cameras, dict) or not cameras:
            raise ValueError(f"{path}: expected a non-empty robot.cameras mapping.")
        configs = draccus.decode(dict[str, CameraConfig], cameras)
    except draccus.ParsingError as exc:
        raise ValueError(f"{path}: invalid camera configuration: {exc}") from exc
    motor_keys = {f"{name}.pos" for name in JOINT_NAMES}
    if any(not name.strip() or name in motor_keys for name in configs):
        raise ValueError("Camera names must be non-empty and must not overlap joint position names.")
    return configs


def _read_camera(camera: Camera, name: str):
    # Keep the manufacturer's Windows fallback for stale background frames.
    try:
        frame = camera.read_latest()
    except TimeoutError:
        logger.warning("%s: stale frame, falling back to async_read", name)
        try:
            frame = camera.async_read(timeout_ms=2000)
        except TimeoutError as exc:
            raise TimeoutError(f"Camera {name}: {exc}") from exc
    # Rerun expects RGB; OpenCV configs may also request BGR output.
    if getattr(camera, "color_mode", ColorMode.RGB) == ColorMode.BGR:
        frame = frame[..., ::-1].copy()
    return frame


def _disconnect_camera(camera: Camera) -> None:
    with contextlib.suppress(Exception):
        camera.disconnect()


def _read_positions(bus: ValidatedNexArmMotorsBus, role: str) -> list[int]:
    try:
        return bus.read_positions()
    except TimeoutError as exc:
        raise TimeoutError(f"{role} on {bus.port}: {exc}") from exc


def teleoperate(
    follower_port: str,
    leader_port: str,
    fps: float = 30.0,
    duration: float | None = None,
    *,
    camera_configs: dict[str, CameraConfig] | None = None,
    display_data: bool = False,
    show_fps: bool = False,
) -> int:
    """Use raw bus positions only; no calibration files, recording or policy execution."""
    follower_port, leader_port = follower_port.strip(), leader_port.strip()
    if not follower_port or not leader_port or follower_port.casefold() == leader_port.casefold():
        raise ValueError("Specify two different ports for follower and leader.")
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("fps must be finite and positive.")
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        raise ValueError("duration must be finite and positive.")

    leader = ValidatedNexArmMotorsBus(port=leader_port)
    follower = ValidatedNexArmMotorsBus(port=follower_port)
    bridge_requested = False
    steps = 0
    rate_start = None
    print(f"Raw teleoperation: follower={follower_port}, leader={leader_port}, fps={fps:g}", flush=True)
    print("Same raw mapping as old; no calibration required. This command can move the arm.", flush=True)
    cameras = make_cameras_from_configs(camera_configs or {})
    viewer = None
    with contextlib.ExitStack() as resources:
        if display_data:
            viewer = RawTeleopViewer()
            resources.callback(viewer.disconnect)
            viewer.connect(cameras)
            print("Rerun shows camera images and raw joint positions (encoder ticks).", flush=True)
        # Finish camera warmup before enabling the arm; failure here opens no serial port.
        for name, camera in cameras.items():
            resources.callback(_disconnect_camera, camera)
            print(f"Connecting camera {name}: {camera_configs[name]}", flush=True)
            camera.connect()
        try:
            # Match old's CLI startup: leader torque off, then follower bridge and torque on.
            leader.connect()
            leader.set_torque(False)
            follower.connect()
            bridge_requested = True
            follower.enter_lerobot_mode()
            follower.set_torque(True)
            print("Follower torque-ON command sent. Reading positions before the first target.", flush=True)
            # Python 3.12's Windows monotonic clock ticks every 15.6 ms; use the high-resolution clock.
            rate_start = time.perf_counter()
            report_start = rate_start
            report_steps = 0
            work_total = 0.0
            deadline = None if duration is None else rate_start + duration
            while deadline is None or time.perf_counter() < deadline:
                loop_start = time.perf_counter()
                observation = _read_positions(follower, "Follower")
                images = {name: _read_camera(camera, name) for name, camera in cameras.items()}
                leader_positions = _read_positions(leader, "Leader")
                goals = map_leader_to_follower(leader_positions)
                follower.write_positions(goals)
                try:
                    follower.read_positions()  # Preserve old's additional readback after every write.
                except TimeoutError:
                    logger.debug("Position readback timed out after write", exc_info=True)
                if viewer is not None:
                    viewer.log(
                        observation={
                            **{
                                f"{name}.pos": float(pos)
                                for name, pos in zip(JOINT_NAMES, observation, strict=True)
                            },
                            **images,
                        },
                        action={
                            f"{name}.pos": float(pos) for name, pos in zip(JOINT_NAMES, goals, strict=True)
                        },
                        elapsed=time.perf_counter() - rate_start,
                    )
                steps += 1
                if steps == 1:
                    print(f"Follower raw positions: {observation}", flush=True)
                    print("Raw teleoperation running. Press Ctrl+C to stop.", flush=True)
                work_s = time.perf_counter() - loop_start
                remaining = 1.0 / fps - work_s
                if remaining > 0:
                    time.sleep(remaining)
                if show_fps:
                    report_steps += 1
                    work_total += work_s
                    now = time.perf_counter()
                    elapsed = now - report_start
                    if elapsed >= 1.0:
                        print(
                            f"Measured FPS: {report_steps / elapsed:.1f} | "
                            f"loop: {1000 * elapsed / report_steps:.1f} ms | "
                            f"work: {1000 * work_total / report_steps:.1f} ms | target: {fps:g}",
                            flush=True,
                        )
                        report_start = now
                        report_steps = 0
                        work_total = 0.0
        finally:
            elapsed = time.perf_counter() - rate_start if show_fps and rate_start is not None else 0.0
            # Match old's disable_torque_on_disconnect=False. Always release both serial ports.
            if bridge_requested and follower.is_connected:
                with contextlib.suppress(Exception):
                    follower.exit_lerobot_mode()
            try:
                follower.disconnect()
            finally:
                leader.disconnect()
            if elapsed > 0:
                print(
                    f"Overall FPS: {steps / elapsed:.1f} ({steps} completed loops in {elapsed:.2f} s)",
                    flush=True,
                )
    return steps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--follower-port", required=True, help="Working arm, e.g. COM13")
    parser.add_argument("--leader-port", required=True, help="Hand-guided arm, e.g. COM14")
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--duration", type=float, help="Optional maximum loop duration in seconds")
    parser.add_argument(
        "--show-fps",
        action="store_true",
        help="Print measured teleoperation loop FPS every second and an overall rate on exit",
    )
    parser.add_argument(
        "--camera-config",
        type=Path,
        help="Load only robot.cameras from a LeRobot YAML file, e.g. examples/nexarm/teleoperate.yaml",
    )
    parser.add_argument(
        "--display-data",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Show images and raw positions in Rerun (default: enabled with --camera-config)",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        cameras = load_camera_configs(args.camera_config) if args.camera_config else {}
        teleoperate(
            args.follower_port,
            args.leader_port,
            args.fps,
            args.duration,
            camera_configs=cameras,
            display_data=args.display_data if args.display_data is not None else bool(cameras),
            show_fps=args.show_fps,
        )
    except KeyboardInterrupt:
        print("Raw teleoperation stopped.")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
