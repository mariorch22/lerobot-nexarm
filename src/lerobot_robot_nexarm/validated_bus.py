"""Validate position replies before the unchanged manufacturer driver clips them."""

import logging
import struct

from .bus import (
    CMD_READ_POS,
    DEFAULT_BAUDRATE,
    DEFAULT_TIMEOUT,
    JOINT_COUNT,
    POSITION_MAX,
    POSITION_MIN,
    REPLY_TIMEOUT,
    NexArmMotorsBus,
)

logger = logging.getLogger(__name__)


class ValidatedNexArmMotorsBus(NexArmMotorsBus):
    """Reject impossible positions within the original read retry budget.

    Framing, checksum tolerance and retry timing remain in the manufacturer
    driver. Valid 12-bit samples, including 0 and 4095, pass through unchanged.
    """

    def __init__(self, port: str, baudrate: int = DEFAULT_BAUDRATE, timeout: float = DEFAULT_TIMEOUT):
        super().__init__(port=port, baudrate=baudrate, timeout=timeout)
        self.rejected_position_replies = 0

    def _send(
        self, frame: bytes, expect_reply: bool = True, reply_timeout: float = REPLY_TIMEOUT
    ) -> tuple[int, bytes] | None:
        reply = super()._send(frame, expect_reply=expect_reply, reply_timeout=reply_timeout)
        if reply is None or not expect_reply or len(frame) < 5 or frame[4] != CMD_READ_POS:
            return reply
        command, payload = reply
        reason = None
        if command != CMD_READ_POS or len(payload) != JOINT_COUNT * 2:
            reason = f"expected CMD 96 with 12 bytes, got CMD {command} with {len(payload)} bytes"
        else:
            values = struct.unpack("<6h", payload)
            if any(value < POSITION_MIN or value > POSITION_MAX for value in values):
                reason = f"values outside 0..4095 before clipping: {list(values)}"
        if reason is not None:
            self.rejected_position_replies += 1
            logger.warning(
                "Discarding invalid NexArm position reply on %s: %s; payload=%s",
                self.port,
                reason,
                payload.hex(" "),
            )
            return None
        return reply
