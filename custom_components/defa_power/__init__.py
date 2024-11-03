"""DEFA Power integration for Home Assistant."""

import logging
from typing import TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .cloudcharge_api.client import CloudChargeAPIClient
from .const import API_BASE_URL
from .coordinator import (
    CloudChargeChargersCoordinator,
    CloudChargeOperationalDataCoordinator,
)
from .devices import ChargePointDevice, ConnectorDevice

_LOGGER = logging.getLogger(__name__)


class RuntimeDataChargePoint(TypedDict):
    """Runtime data for a charger."""

    device: ChargePointDevice


class RuntimeDataConnector(TypedDict):
    """Runtime data for a connector."""

    device: ConnectorDevice
    alias: str
    operational_data_coordinator: CloudChargeOperationalDataCoordinator


class RuntimeData(TypedDict):
    """Runtime data for DEFA Power."""

    chargers_coordinator: CloudChargeChargersCoordinator
    chargerPoints: dict[str, RuntimeDataChargePoint]
    connectors: dict[str, RuntimeDataConnector]

    client: CloudChargeAPIClient


type DefaPowerConfigEntry = ConfigEntry[RuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: DefaPowerConfigEntry) -> bool:
    """Set up DEFA Power from a config entry."""
    _LOGGER.info("Setting up DEFA Power from config entry")

    client = CloudChargeAPIClient(API_BASE_URL)
    client.import_credentials(entry.data["credentials"])

    chargers_coordinator = CloudChargeChargersCoordinator(hass, client)
    await chargers_coordinator.async_config_entry_first_refresh()

    instance_id = entry.data.get("instance_id") or "default"
    chargePoints = {}
    connectors = {}
    data: RuntimeData = {
        "chargers_coordinator": chargers_coordinator,
        "chargePoints": chargePoints,
        "connectors": connectors,
        "client": client,
    }

    for connector_id, val in chargers_coordinator.data["chargePoints"].items():
        c: RuntimeDataChargePoint = {}
        chargePoints[connector_id] = c

        c["device"] = ChargePointDevice(val, instance_id)

    for alias, val in chargers_coordinator.data["connectors"].items():
        connector_id = val["id"]

        c: RuntimeDataConnector = {}
        connectors[connector_id] = c

        operational_data_coordinator = CloudChargeOperationalDataCoordinator(
            connector_id, hass, client
        )
        await (
            operational_data_coordinator.async_config_entry_first_refresh()
        )  # TODO: Fix first entiry not getting value on first fetch without prefetching

        c["device"] = ConnectorDevice(val, instance_id, alias)
        c["alias"] = alias
        c["operational_data_coordinator"] = operational_data_coordinator

    entry.runtime_data = data

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "button"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading DEFA Power config entry")
    await hass.config_entries.async_forward_entry_unload(entry, "sensor", "button")
    return True


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 2:
        # This means the user has downgraded from a future version
        return False

    new_data = {**config_entry.data}

    if config_entry.version == 1:
        new_data["credentials"] = {
            "user_id": config_entry.data["userId"],
            "token": config_entry.data["token"],
        }
        del new_data["userId"]
        del new_data["token"]

    hass.config_entries.async_update_entry(
        config_entry, data=new_data, minor_version=1, version=2
    )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True


async def update_listener(hass: HomeAssistant, entry: DefaPowerConfigEntry):
    """Handle options update."""
    _LOGGER.info("Handling options update")

    entry.runtime_data["client"].import_credentials(entry.data["credentials"])
