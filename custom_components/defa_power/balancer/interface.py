"""Look up the network interface a balancer entry listens on.

The entry stores the interface by name rather than by address: the address a
DHCP lease gives Home Assistant can change, the interface does not. The name is
resolved to its current IPv4 address every time the entry is set up.

Interfaces are read fresh with ifaddr (a Home Assistant core dependency) rather
than through the network integration, which only reads them once at startup.
"""

import ifaddr

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from ..const import CONF_INTERFACE


class InterfaceUnavailableError(HomeAssistantError):
    """The entry's interface is missing or has no IPv4 address right now."""


def _get_interfaces() -> dict[str, list[str]]:
    interfaces: dict[str, list[str]] = {}
    for adapter in ifaddr.get_adapters():
        addresses = [
            ip.ip
            for ip in adapter.ips
            if ip.is_IPv4 and isinstance(ip.ip, str) and not ip.ip.startswith("127.")
        ]
        if addresses:
            interfaces[adapter.nice_name] = addresses
    return interfaces


async def async_get_interfaces(hass: HomeAssistant) -> dict[str, list[str]]:
    """Return the IPv4 addresses of every interface that has one, by name.

    Loopback addresses are left out; the balancer multicast never arrives there.
    """
    return await hass.async_add_executor_job(_get_interfaces)


def interface_for_ip(interfaces: dict[str, list[str]], ip_address: str) -> str | None:
    """Return the name of the interface that has the given address."""
    return next(
        (name for name, addresses in interfaces.items() if ip_address in addresses),
        None,
    )


async def async_resolve_entry_interface(
    hass: HomeAssistant, entry: ConfigEntry
) -> tuple[str, str]:
    """Return the name and current IPv4 address of the entry's interface.

    Raises InterfaceUnavailableError when the interface cannot be listened on
    right now, with a message fit for the user.
    """
    name: str = entry.data[CONF_INTERFACE]
    addresses = (await async_get_interfaces(hass)).get(name)
    if not addresses:
        raise InterfaceUnavailableError(
            f"Network interface {name} is missing or has no IPv4 address"
        )
    return name, addresses[0]
