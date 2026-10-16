"""Wire format of the DEFA Balancer multicast broadcast.

Reverse engineered from captured traffic; there is no public documentation.
Layout of a broadcast (all integers little endian):

    0..11   device id, ASCII, "L4" followed by the serial (starts with "33")
    11..15  wall clock: Unix time in milliseconds, low 32 bits, u32
    15..20  unknown
    20..23  phase 1 current in mA, u24
    23..26  phase 2 current in mA, u24
    26..29  phase 3 current in mA, u24
    29..33  unknown
    33..    firmware version, NUL terminated ASCII, at most 20 bytes

The address the packet was sent from is recorded alongside the decoded fields.
"""

from typing import TypedDict

DEVICE_ID_PREFIX = "L433"
DEVICE_ID_LENGTH = 11
MIN_PACKET_LENGTH = 33
FIRMWARE_OFFSET = 33
FIRMWARE_MAX_LENGTH = 20


class BalancerData(TypedDict):
    """One decoded balancer broadcast."""

    serial: str
    firmware_version: str | None
    # Amperes per phase
    current_l1: float
    current_l2: float
    current_l3: float
    # Source address of the broadcast
    ip_address: str
    # The complete packet as hex, kept so unknown fields can be studied from a
    # diagnostics dump
    raw: str


def _u24(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 3], "little")


def parse_balancer_packet(data: bytes, ip_address: str) -> BalancerData | None:
    """Decode a broadcast from `ip_address`, or return None for any other packet."""
    if len(data) < MIN_PACKET_LENGTH:
        return None
    try:
        device_id = data[:DEVICE_ID_LENGTH].decode("ascii")
    except UnicodeDecodeError:
        return None
    if not device_id.startswith(DEVICE_ID_PREFIX):
        return None

    firmware_version: str | None = None
    if len(data) > FIRMWARE_OFFSET:
        firmware_bytes = data[FIRMWARE_OFFSET : FIRMWARE_OFFSET + FIRMWARE_MAX_LENGTH]
        firmware_bytes = firmware_bytes.split(b"\0", 1)[0]
        firmware_version = firmware_bytes.decode("ascii", errors="replace") or None

    return {
        "serial": device_id[2:],
        "firmware_version": firmware_version,
        "current_l1": _u24(data, 20) / 1000,
        "current_l2": _u24(data, 23) / 1000,
        "current_l3": _u24(data, 26) / 1000,
        "ip_address": ip_address,
        "raw": data.hex(" "),
    }
