"""Human-run NexArm transport diagnosis, without position targets or torque-ON commands."""

import argparse
import logging
import math
import time

import serial

from lerobot_robot_nexarm import NexArmFollower, NexArmFollowerConfig
from lerobot_robot_nexarm.bus import SYSTEM_ID, NexArmMotorsBus, build_frame

CMD_FIRMWARE_VERSION = 1


class TracingBus(NexArmMotorsBus):
    """Keep original frames/parser/timeouts; optional diagnostic probes are explicit."""

    startup_wait = 0.0
    probe_before_torque_off = False
    probe_succeeded = None
    inactive_control_lines = False

    def connect(self):
        if self.is_connected:
            return
        if self.inactive_control_lines:
            # Diagnostic-only: set requested line states BEFORE opening the port.
            # The production driver's default Serial(port=...) path is unchanged.
            self._serial = serial.Serial(
                port=None, baudrate=self.baudrate, timeout=self.timeout, write_timeout=self.timeout
            )
            try:
                self._serial.dtr = False
                self._serial.rts = False
                self._serial.port = self.port
                self._serial.open()
                time.sleep(0.1)
                self._serial.reset_input_buffer()
            except BaseException:
                self.disconnect()
                raise
            print("Diagnostic open: DTR/RTS requested inactive before port open", flush=True)
        else:
            super().connect()
        mode = "requested inactive before open" if self.inactive_control_lines else "not modified"
        print(
            f"Serial lines after open: DTR={getattr(self._serial, 'dtr', 'unknown')}, "
            f"RTS={getattr(self._serial, 'rts', 'unknown')} ({mode})",
            flush=True,
        )
        if self.startup_wait:
            print(f"Diagnostic startup wait: {self.startup_wait:g} seconds BEFORE first command", flush=True)
            time.sleep(self.startup_wait)

    def enter_lerobot_mode(self):
        super().enter_lerobot_mode()
        if self.probe_before_torque_off:
            print(
                "BEFORE torque-OFF: initial hardware torque state is UNKNOWN; no torque-ON sent.", flush=True
            )
            try:
                positions = self.read_positions()
            except TimeoutError:
                self.probe_succeeded = False
                print("BEFORE torque-OFF: TIMEOUT", flush=True)
            else:
                self.probe_succeeded = True
                print(f"BEFORE torque-OFF: POSITIONS: {positions}", flush=True)

    def _send(self, frame: bytes, *args, **kwargs):
        print(f"TX CMD {frame[4]}: {frame.hex(' ')}", flush=True)
        return super()._send(frame, *args, **kwargs)

    def _try_parse(self, buf: bytearray):
        print(f"RX buffer ({len(buf)} bytes): {bytes(buf[:128]).hex(' ')}", flush=True)
        result = super()._try_parse(buf)
        if result is not None:
            print(f"Parsed CMD {result[0]}, payload={result[1].hex(' ')}", flush=True)
        return result


def diagnose(
    port: str,
    reads: int = 3,
    startup_wait: float = 0.0,
    probe_before_torque_off: bool = False,
    inactive_control_lines: bool = False,
) -> bool:
    if not math.isfinite(startup_wait) or not 0 <= startup_wait <= 10:
        raise ValueError("startup_wait must be finite and between 0 and 10 seconds.")
    print(f"Follower diagnosis on {port}. Support the arm before running this command.", flush=True)
    print("Sends bridge and torque-OFF commands, then reads. No position targets are sent.", flush=True)
    print("This diagnostic does not verify bridge entry or the hardware torque state.", flush=True)
    robot = NexArmFollower(NexArmFollowerConfig(port=port, id="connection_diagnosis", cameras={}))
    robot.bus = TracingBus(port=port)
    robot.bus.startup_wait = startup_wait
    robot.bus.probe_before_torque_off = probe_before_torque_off
    robot.bus.inactive_control_lines = inactive_control_lines
    successes = 0
    try:
        robot.connect(calibrate=False)
        print("AFTER torque-OFF command (hardware torque state not acknowledged):", flush=True)
        for attempt in range(1, reads + 1):
            print(f"Position read {attempt}/{reads}", flush=True)
            try:
                positions = robot.bus.read_positions()
            except TimeoutError as exc:
                print(f"TIMEOUT: {exc}", flush=True)
            else:
                successes += 1
                print(f"POSITIONS: {positions}", flush=True)
    finally:
        robot.disconnect()
    if probe_before_torque_off:
        print(f"Before torque-OFF: reply received={robot.bus.probe_succeeded}", flush=True)
    print(f"Result: {successes}/{reads} reads returned positions.", flush=True)
    return successes > 0


def probe_controller(port: str, startup_wait: float = 0.0, inactive_control_lines: bool = False) -> bool:
    """Query the vendor's normal-mode firmware handler, independently of the servo bridge."""
    if not math.isfinite(startup_wait) or not 0 <= startup_wait <= 10:
        raise ValueError("startup_wait must be finite and between 0 and 10 seconds.")
    print(f"Controller firmware probe on {port} at 1000000 baud.", flush=True)
    print("Sends only CMD 1 (read firmware version); no bridge, torque or position commands.", flush=True)
    print(
        "Requires normal firmware mode after a full power cycle, not an existing bridge session.", flush=True
    )
    bus = TracingBus(port=port)
    bus.startup_wait = startup_wait
    bus.inactive_control_lines = inactive_control_lines
    try:
        bus.connect()
        bus._send(build_frame(SYSTEM_ID, CMD_FIRMWARE_VERSION), expect_reply=False)
        deadline = time.monotonic() + 3.0
        buffer = bytearray()
        while time.monotonic() < deadline:
            available = bus._serial.in_waiting
            if not available:
                time.sleep(0.001)
                continue
            buffer.extend(bus._serial.read(available))
            # Keep trailing frames: unsolicited status may precede the version reply.
            while (reply := bus._try_parse(buffer)) is not None:
                command, payload = reply
                if command != CMD_FIRMWARE_VERSION:
                    print(f"Ignoring unsolicited CMD {command}; waiting for CMD 1.", flush=True)
                    continue
                if len(payload) not in (3, 6):
                    print(f"Unexpected CMD 1 payload length: {len(payload)}; not a known version reply.")
                    continue
                print(f"ESP32 firmware: {'.'.join(map(str, payload[:3]))}", flush=True)
                if len(payload) == 6:
                    if payload[3:] == b"\x00\x00\x00":
                        print("AT32 firmware: 0.0.0 (no AT32 version confirmed)", flush=True)
                    else:
                        print(f"AT32 firmware: {'.'.join(map(str, payload[3:]))}", flush=True)
                print("Result: controller replied to the firmware query.", flush=True)
                return True
    finally:
        bus.disconnect()
    print("TIMEOUT: no valid firmware-version reply. Firmware on this device is not yet identified.")
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="Confirmed FOLLOWER port, e.g. COM12")
    parser.add_argument(
        "--controller-probe",
        action="store_true",
        help="Query firmware with CMD 1 only, in normal mode after a full power cycle",
    )
    parser.add_argument("--reads", type=int, default=3, choices=range(1, 11))
    parser.add_argument(
        "--startup-wait",
        type=float,
        default=0.0,
        help="Diagnostic-only extra wait AFTER port open and BEFORE the first command (0..10 seconds)",
    )
    parser.add_argument(
        "--probe-before-torque-off",
        action="store_true",
        help="Explicit diagnostic read after bridge entry BEFORE torque-OFF; initial torque is unknown",
    )
    parser.add_argument(
        "--inactive-control-lines",
        action="store_true",
        help="Diagnostic-only: request DTR=False and RTS=False BEFORE opening the port",
    )
    args = parser.parse_args()
    if not math.isfinite(args.startup_wait) or not 0 <= args.startup_wait <= 10:
        parser.error("--startup-wait must be finite and between 0 and 10 seconds")
    if args.controller_probe and args.probe_before_torque_off:
        parser.error("--controller-probe cannot be combined with --probe-before-torque-off")
    logging.basicConfig(level=logging.INFO)
    if args.controller_probe:
        successful = probe_controller(args.port, args.startup_wait, args.inactive_control_lines)
    else:
        successful = diagnose(
            args.port,
            args.reads,
            args.startup_wait,
            args.probe_before_torque_off,
            args.inactive_control_lines,
        )
    raise SystemExit(0 if successful else 2)


if __name__ == "__main__":
    main()
