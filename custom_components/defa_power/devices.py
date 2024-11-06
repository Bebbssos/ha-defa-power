"""DEFA Power device classes."""

from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


class ChargePointDevice:
    """Representation of a DEFA Power charger device."""

    def __init__(self, data, instance_id) -> None:
        """Initialize the device."""
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, instance_id, data["id"])},
            name=data.get("displayName") or data["id"],
        )

    def get_device_info(self):
        """Return the device info."""
        return self._device_info


class ConnectorDevice:
    """Representation of a DEFA Power connector device."""

    def __init__(self, data, instance_id, alias) -> None:
        """Initialize the device."""
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, instance_id, data["id"])},
            manufacturer=data["vendor"],
            model=data["model"],
            name=data.get("displayName") or alias or data["id"],
            sw_version=data["firmwareVersion"],
            serial_number=data["serialNumber"],
            via_device=(DOMAIN, instance_id, data["chargerId"]),
        )

    def get_device_info(self):
        """Return the device info."""
        return self._device_info
