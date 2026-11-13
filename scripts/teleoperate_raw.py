"""Human-run, camera-free NexArm teleoperation with the manufacturer's raw-value workflow."""

import argparse
import contextlib
import logging
import math
import time

from lerobot_robot_nexarm.bus import NexArmMotorsBus, map_leader_to_follower

logger = logging.getLogger(__name__)


def _read_positions(bus: NexArmMotorsBus, role: str) -> list[int]:
    try:
        return bus.read_positions()
    except TimeoutError as exc:
        raise TimeoutError(f"{role} on {bus.port}: {exc}") from exc


def teleoperate(
    follower_port: str,
    leader_port: str,
    fps: float = 30.0,
    duration: float | None = None,
) -> int:
    """Use raw bus positions only; no calibration files, recording or policy execution."""
    follower_port, leader_port = follower_port.strip(), leader_port.strip()
    if not follower_port or not leader_port or follower_port.casefold() == leader_port.casefold():
        raise ValueError("Specify two different ports for follower and leader.")
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("fps must be finite and positive.")
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        raise ValueError("duration must be finite and positive.")

    leader = NexArmMotorsBus(port=leader_port)
    follower = NexArmMotorsBus(port=follower_port)
    bridge_requested = False
    steps = 0
    print(f"Raw teleoperation: follower={follower_port}, leader={leader_port}, fps={fps:g}", flush=True)
    print("Same raw mapping as old; no calibration required. This command can move the arm.", flush=True)
    try:
        # Match old's CLI startup: leader torque off, then follower bridge and torque on.
        leader.connect()
        leader.set_torque(False)
        follower.connect()
        bridge_requested = True
        follower.enter_lerobot_mode()
        follower.set_torque(True)
        print("Follower torque-ON command sent. Reading positions before the first target.", flush=True)
        deadline = None if duration is None else time.monotonic() + duration
        while deadline is None or time.monotonic() < deadline:
            loop_start = time.monotonic()
            observation = _read_positions(follower, "Follower")
            leader_positions = _read_positions(leader, "Leader")
            goals = map_leader_to_follower(leader_positions)
            follower.write_positions(goals)
            try:
                follower.read_positions()  # Preserve old's additional readback after every write.
            except TimeoutError:
                logger.debug("Position readback timed out after write", exc_info=True)
            steps += 1
            if steps == 1:
                print(f"Follower raw positions: {observation}", flush=True)
                print("Raw teleoperation running. Press Ctrl+C to stop.", flush=True)
            remaining = 1.0 / fps - (time.monotonic() - loop_start)
            if remaining > 0:
                time.sleep(remaining)
    finally:
        # Match old's disable_torque_on_disconnect=False. Always release both serial ports.
        if bridge_requested and follower.is_connected:
            with contextlib.suppress(Exception):
                follower.exit_lerobot_mode()
        follower.disconnect()
        leader.disconnect()
    return steps


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--follower-port", required=True, help="Working arm, e.g. COM13")
    parser.add_argument("--leader-port", required=True, help="Hand-guided arm, e.g. COM14")
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--duration", type=float, help="Optional maximum loop duration in seconds")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        teleoperate(args.follower_port, args.leader_port, args.fps, args.duration)
    except KeyboardInterrupt:
        print("Raw teleoperation stopped.")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"ERROR: {exc}\n")


if __name__ == "__main__":
    main()
