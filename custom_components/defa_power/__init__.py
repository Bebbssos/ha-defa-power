"""DEFA Power integration for Home Assistant."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .cloudcharge_api.client import CloudChargeAPIClient
from .const import API_BASE_URL
from .coordinator import (
    CloudChargeChargepointCoordinator,
    CloudChargeEcoModeCoordinator,
    CloudChargeOperationalDataCoordinator,
)
from .devices import ChargePointDevice, ConnectorDevice
from .models import (
    DefaPowerConfigEntry,
    RuntimeData,
    RuntimeDataChargePoint,
    RuntimeDataConnector,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: DefaPowerConfigEntry) -> bool:
    """Set up DEFA Power from a config entry."""
    _LOGGER.info("Setting up DEFA Power from config entry")

    client = CloudChargeAPIClient(API_BASE_URL)
    client.import_credentials(entry.data["credentials"])

    chargepoint_ids = await client.async_get_chargepoint_ids()

    instance_id = entry.data.get("instance_id") or "default"
    chargepoints = {}
    connectors = {}
    data: RuntimeData = {
        "chargepoints": chargepoints,
        "connectors": connectors,
        "client": client,
    }

    for chargepoint_id in chargepoint_ids:
        c: RuntimeDataChargePoint = {}
        chargepoints[chargepoint_id] = c
        coordinator = CloudChargeChargepointCoordinator(chargepoint_id, hass, client)
        await coordinator.async_config_entry_first_refresh()
        chargepoint_data = coordinator.data

        c["coordinator"] = coordinator
        c["device"] = ChargePointDevice(chargepoint_data["chargepoint"], instance_id)

        for alias, val in chargepoint_data["connectors"].items():
            connector_id = val["id"]

            c: RuntimeDataConnector = {}
            connectors[connector_id] = c

            operational_data_coordinator = CloudChargeOperationalDataCoordinator(
                connector_id, hass, client
            )
            await operational_data_coordinator.async_config_entry_first_refresh()

            eco_mode_coordinator = CloudChargeEcoModeCoordinator(
                connector_id, hass, client
            )
            await eco_mode_coordinator.async_config_entry_first_refresh()

            c["device"] = ConnectorDevice(val, instance_id, alias)
            c["alias"] = alias
            c["operational_data_coordinator"] = operational_data_coordinator
            c["eco_mode_coordinator"] = eco_mode_coordinator
            c["chargepoint_id"] = chargepoint_id

    entry.runtime_data = data

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor", "button", "number", "select", "switch"]
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading DEFA Power config entry")
    await hass.config_entries.async_unload_platforms(
        entry, ["sensor", "button", "number", "select", "switch"]
    )
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry):
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


async def async_setup(hass: HomeAssistant, config):
    """Set up the integration."""
    await async_setup_services(hass)
    return True
