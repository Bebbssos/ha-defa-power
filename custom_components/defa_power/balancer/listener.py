"""Receive DEFA Balancer multicast broadcasts."""

import asyncio
from collections.abc import Callable
import logging
import socket
import time

from homeassistant.core import HomeAssistant, callback

from ..const import BALANCER_MULTICAST_ADDR, BALANCER_MULTICAST_PORT
from .protocol import BalancerData, parse_balancer_packet

_LOGGER = logging.getLogger(__name__)

type BalancerCallback = Callable[[BalancerData], None]


class BalancerListener(asyncio.DatagramProtocol):
    """Joins the balancer multicast group on one interface and decodes broadcasts.

    Every balancer on the network sends to the same group, so one listener
    serves all of them; packets are handed to callbacks registered per serial.
    Balancers that nobody registered for are still tracked in `last_seen` so a
    config flow can discover them.
    """

    def __init__(self, hass: HomeAssistant, interface_ip: str) -> None:
        """Initialize the listener for the interface with the given local IP."""
        self.hass = hass
        self.interface_ip = interface_ip
        self._transport: asyncio.DatagramTransport | None = None
        self._callbacks: dict[str, list[BalancerCallback]] = {}
        # Latest decoded broadcast per serial and the monotonic time it arrived
        self.last_seen: dict[str, tuple[BalancerData, float]] = {}

    async def async_start(self) -> None:
        """Open the socket and join the multicast group.

        Raises OSError when the socket cannot be bound or the interface does not
        exist.
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        try:
            # Several listeners (a running entry plus a config flow scan) must be
            # able to receive the same multicast at once
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            sock.bind(("", BALANCER_MULTICAST_PORT))
            membership = socket.inet_aton(BALANCER_MULTICAST_ADDR) + socket.inet_aton(
                self.interface_ip
            )
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
            sock.setblocking(False)
        except OSError:
            sock.close()
            raise

        loop = asyncio.get_running_loop()
        self._transport, _ = await loop.create_datagram_endpoint(
            lambda: self, sock=sock
        )
        _LOGGER.debug(
            "Listening for balancers on %s:%s via %s",
            BALANCER_MULTICAST_ADDR,
            BALANCER_MULTICAST_PORT,
            self.interface_ip,
        )

    @callback
    def async_stop(self) -> None:
        """Close the socket."""
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    @callback
    def async_register(self, serial: str, cb: BalancerCallback) -> Callable[[], None]:
        """Call `cb` with every broadcast from the balancer with the given serial.

        Returns a function that removes the callback again.
        """
        self._callbacks.setdefault(serial, []).append(cb)

        @callback
        def _unregister() -> None:
            self._callbacks[serial].remove(cb)

        return _unregister

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Decode a received packet and dispatch it."""
        parsed = parse_balancer_packet(data)
        if parsed is None:
            _LOGGER.debug("Ignoring unknown packet from %s: %s", addr, data.hex(" "))
            return
        serial = parsed["serial"]
        self.last_seen[serial] = (parsed, time.monotonic())
        for cb in self._callbacks.get(serial, ()):
            cb(parsed)

    def error_received(self, exc: Exception) -> None:
        """Log socket errors; the transport stays open."""
        _LOGGER.warning("Balancer listener error on %s: %s", self.interface_ip, exc)

    def connection_lost(self, exc: Exception | None) -> None:
        """Log an unexpected close of the socket."""
        if exc is not None:
            _LOGGER.error("Balancer listener on %s closed: %s", self.interface_ip, exc)


async def async_scan_balancers(
    hass: HomeAssistant, interface_ip: str, timeout: float
) -> dict[str, BalancerData]:
    """Listen for `timeout` seconds and return every balancer heard, by serial.

    Raises OSError when the interface cannot be listened on.
    """
    listener = BalancerListener(hass, interface_ip)
    await listener.async_start()
    try:
        await asyncio.sleep(timeout)
    finally:
        listener.async_stop()
    return {serial: data for serial, (data, _) in listener.last_seen.items()}
