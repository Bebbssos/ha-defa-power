"""DEFA Power device classes."""

from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


class ChargePointDevice:
    """Representation of a DEFA Power charger device."""

    def __init__(self, data, instance_id) -> None:
        """Initialize the device."""
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, instance_id, data["id"])},  # type: ignore[arg-type]
            name=data.get("displayName") or data["id"],
        )

    def get_device_info(self):
        """Return the device info."""
        return self._device_info


class ConnectorDevice:
    """Representation of a DEFA Power connector device."""

    def __init__(
        self, data, instance_id, alias, via_device_id: str | None = None
    ) -> None:
        """Initialize the device."""
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, instance_id, data["id"])},  # type: ignore[arg-type]
            manufacturer=data["vendor"],
            model=data["model"],
            name=data.get("displayName") or alias or data["id"],
            sw_version=data["firmwareVersion"],
            serial_number=data["serialNumber"],
        )
        # Only linked when the chargepoint device is registered, which is not
        # the case for chargepoints without their own subentry
        if via_device_id:
            self._device_info["via_device_id"] = via_device_id

    def get_device_info(self):
        """Return the device info."""
        return self._device_info


class BalancerDevice:
    """Representation of a DEFA Balancer device."""

    def __init__(self, serial: str, firmware_version: str | None = None) -> None:
        """Initialize the device."""
        # The serial is printed on the balancer and is stable across re-adding
        # the entry, so no instance id is mixed into the identifier
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, "balancer", serial)},  # type: ignore[arg-type]
            manufacturer="DEFA",
            model="Balancer",
            name=f"Balancer {serial}",
            serial_number=serial,
            sw_version=firmware_version,
        )

    def get_device_info(self):
        """Return the device info."""
        return self._device_info
