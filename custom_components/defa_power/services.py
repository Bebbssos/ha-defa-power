"""Custom services for the DEFA Power EV charger integration."""

import asyncio

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .models import RuntimeData

SERVICE_SET_CURRENT_LIMIT = "set_current_limit"
SERVICE_SET_ECO_MODE = "set_eco_mode"
SERVICE_START_CHARGING = "start_charging"
SERVICE_STOP_CHARGING = "stop_charging"
SERVICE_RESET_CHARGER = "reset_charger"


SET_CURRENT_LIMIT_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("current_limit"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)

SET_ECO_MODE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("active"): cv.boolean,
        vol.Required("hours_to_charge"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required("pickup_time_enabled"): cv.boolean,
        vol.Optional("pickup_time_mon"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=23)
        ),
        vol.Optional("pickup_time_tue"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=23)
        ),
        vol.Optional("pickup_time_wed"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=23)
        ),
        vol.Optional("pickup_time_thu"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=23)
        ),
        vol.Optional("pickup_time_fri"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=23)
        ),
        vol.Optional("pickup_time_sat"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=23)
        ),
        vol.Optional("pickup_time_sun"): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=23)
        ),
    }
)

START_CHARGING_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
    }
)

STOP_CHARGING_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
    }
)

RESET_CHARGER_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("type"): vol.In(["soft", "hard"]),
    }
)


async def async_setup_services(hass: HomeAssistant):
    """Set up custom services for the EV charger integration."""

    async def handle_set_current_limit(call: ServiceCall):
        """Handle setting current limit."""
        current_limit = call.data.get("current_limit")

        for connector_id, runtime_data in device_data_generator(hass, call):
            await runtime_data["client"].async_set_max_current(
                connector_id, current_limit
            )
            await runtime_data["chargers_coordinator"].async_refresh()

    async def handle_set_eco_mode(call: ServiceCall):
        """Handle setting eco mode."""
        config = {
            "active": call.data.get("active"),
            "hoursToCharge": call.data.get("hours_to_charge"),
            "pickupTimeEnabled": call.data.get("pickup_time_enabled"),
            "dayOfWeekMap": {
                "MONDAY": call.data.get("pickup_time_mon"),
                "TUESDAY": call.data.get("pickup_time_tue"),
                "WEDNESDAY": call.data.get("pickup_time_wed"),
                "THURSDAY": call.data.get("pickup_time_thu"),
                "FRIDAY": call.data.get("pickup_time_fri"),
                "SATURDAY": call.data.get("pickup_time_sat"),
                "SUNDAY": call.data.get("pickup_time_sun"),
            },
        }

        for connector_id, runtime_data in device_data_generator(hass, call):
            await runtime_data["client"].async_set_eco_mode_configuration(
                connector_id, config
            )
            # TODO: Refresh coordinator

    async def handle_start_charging(call: ServiceCall):
        """Handle starting charging."""
        for connector_id, runtime_data in device_data_generator(hass, call):
            await runtime_data["client"].async_start_charging(connector_id)
            await asyncio.sleep(5)
            await runtime_data["connectors"][connector_id][
                "operational_data_coordinator"
            ].async_refresh()

    async def handle_stop_charging(call: ServiceCall):
        """Handle stopping charging."""
        for connector_id, runtime_data in device_data_generator(hass, call):
            await runtime_data["client"].async_stop_charging(connector_id)
            await asyncio.sleep(1)
            await runtime_data["connectors"][connector_id][
                "operational_data_coordinator"
            ].async_refresh()

    async def handle_reset_charger(call: ServiceCall):
        """Handle resetting charger."""
        reset_type = call.data.get("type")

        for connector_id, runtime_data in device_data_generator(hass, call):
            await runtime_data["client"].async_reset_charger(connector_id, reset_type)

    # Register all services
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CURRENT_LIMIT,
        handle_set_current_limit,
        SET_CURRENT_LIMIT_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ECO_MODE,
        handle_set_eco_mode,
        SET_ECO_MODE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_START_CHARGING,
        handle_start_charging,
        START_CHARGING_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_CHARGING,
        handle_stop_charging,
        STOP_CHARGING_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_CHARGER,
        handle_reset_charger,
        RESET_CHARGER_SCHEMA,
    )


def get_charger_id_from_device(device: dr.DeviceEntry) -> str | None:
    """Get the charger ID from a device entry."""
    for identifier in device.identifiers:
        if len(identifier) == 3 and identifier[0] == DOMAIN:
            return identifier[2]  # Return the third part (charger ID)

    return None


def get_runtime_data_from_device(
    hass: HomeAssistant, device: dr.DeviceEntry
) -> RuntimeData | None:
    """Retrieve the API client from the config entry runtime_data."""

    # Find the correct config entry
    for entry_id in device.config_entries:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry and hasattr(entry, "runtime_data"):
            return entry.runtime_data  # Retrieve the API client

    return None  # No API client found


def device_data_generator(hass: HomeAssistant, call: ServiceCall):
    """Generate connector_id and runtime_data for each target device."""
    device_registry = dr.async_get(hass)
    target_devices = call.data.get("device_id", [])

    for device_id in target_devices:
        device = device_registry.async_get(device_id)
        if not device:
            raise ValueError(f"Device with ID {device_id} not found")

        connector_id = get_charger_id_from_device(device)
        runtime_data = get_runtime_data_from_device(hass, device)

        if connector_id is None or runtime_data is None:
            raise ValueError(f"Invalid data for device with ID {device_id}")

        yield connector_id, runtime_data
