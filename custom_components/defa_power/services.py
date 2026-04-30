"""Custom services for the DEFA Power EV charger integration."""

import asyncio

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .cloudcharge_api.models import EcoModeConfiguration, ManualSchedule
from .models import RuntimeData

SERVICE_SET_CURRENT_LIMIT = "set_current_limit"
SERVICE_SET_ECO_MODE = "set_eco_mode"
SERVICE_START_CHARGING = "start_charging"
SERVICE_STOP_CHARGING = "stop_charging"
SERVICE_RESET_CHARGER = "reset_charger"
SERVICE_SET_MANUAL_SCHEDULES_ENABLED = "set_manual_schedules_enabled"
SERVICE_OVERRIDE_SCHEDULE = "override_schedule"
SERVICE_GET_MANUAL_SCHEDULES = "get_manual_schedules"
SERVICE_CREATE_MANUAL_SCHEDULE = "create_manual_schedule"
SERVICE_UPDATE_MANUAL_SCHEDULE = "update_manual_schedule"
SERVICE_DELETE_MANUAL_SCHEDULE = "delete_manual_schedule"


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

SET_MANUAL_SCHEDULES_ENABLED_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("enabled"): cv.boolean,
    }
)

OVERRIDE_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
    }
)

GET_MANUAL_SCHEDULES_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
    }
)

DAYS_OF_WEEK = [
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
]

CREATE_MANUAL_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("days"): vol.All(cv.ensure_list, [vol.In(DAYS_OF_WEEK)]),
        vol.Required("start"): cv.string,
        vol.Required("stop"): cv.string,
        vol.Required("enabled"): cv.boolean,
        vol.Optional("priority", default=0): vol.Coerce(float),
    }
)

UPDATE_MANUAL_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("schedule_id"): vol.All(vol.Coerce(int), vol.Range(min=1)),
        vol.Required("days"): vol.All(cv.ensure_list, [vol.In(DAYS_OF_WEEK)]),
        vol.Required("start"): cv.string,
        vol.Required("stop"): cv.string,
        vol.Required("enabled"): cv.boolean,
        vol.Required("priority"): vol.Coerce(float),
    }
)

DELETE_MANUAL_SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.All(cv.ensure_list, [cv.string]),
        vol.Required("schedule_id"): vol.All(vol.Coerce(int), vol.Range(min=1)),
    }
)


async def async_setup_services(hass: HomeAssistant):
    """Set up custom services for the EV charger integration."""

    async def handle_set_current_limit(call: ServiceCall):
        """Handle setting current limit."""
        current_limit = int(call.data["current_limit"])

        for connector_id, runtime_data in device_data_generator(hass, call):
            await runtime_data["client"].async_set_max_current(
                connector_id, current_limit
            )
            chargepoint_id = runtime_data["connectors"][connector_id]["chargepoint_id"]
            await runtime_data["chargepoints"][chargepoint_id][
                "coordinator"
            ].async_refresh()

    async def handle_set_eco_mode(call: ServiceCall):
        """Handle setting eco mode."""
        # Build a partial update dict with only the fields the user explicitly controls.
        # Days omitted from the call are left unchanged in the existing config.
        day_of_week_updates: dict[str, int | None] = {
            day: (int(val) if val is not None else None)
            for day, key in (
                ("MONDAY", "pickup_time_mon"),
                ("TUESDAY", "pickup_time_tue"),
                ("WEDNESDAY", "pickup_time_wed"),
                ("THURSDAY", "pickup_time_thu"),
                ("FRIDAY", "pickup_time_fri"),
                ("SATURDAY", "pickup_time_sat"),
                ("SUNDAY", "pickup_time_sun"),
            )
            if (val := call.data.get(key)) is not None
        }
        active: bool = call.data["active"]
        hours_to_charge: int = int(call.data["hours_to_charge"])
        pickup_time_enabled: bool = call.data["pickup_time_enabled"]

        def _apply(
            data: EcoModeConfiguration,
            _active: bool = active,
            _hours: int = hours_to_charge,
            _pickup: bool = pickup_time_enabled,
            _days: dict[str, int | None] = day_of_week_updates,
        ) -> None:
            data["active"] = _active
            data["hoursToCharge"] = _hours
            data["pickupTimeEnabled"] = _pickup
            # Merge only the days that were provided; leave others intact.
            data["dayOfWeekMap"].update(_days)  # type: ignore[typeddict-item]

        for connector_id, runtime_data in device_data_generator(hass, call):
            coordinator = runtime_data["connectors"][connector_id][
                "eco_mode_coordinator"
            ]
            assert coordinator is not None
            await coordinator.set_data(_apply)

    async def handle_start_charging(call: ServiceCall):
        """Handle starting charging."""
        for connector_id, runtime_data in device_data_generator(hass, call):
            alias = runtime_data["connectors"][connector_id]["alias"]
            await runtime_data["client"].async_start_charging(alias)
            await asyncio.sleep(5)
            await runtime_data["connectors"][connector_id][
                "operational_data_coordinator"
            ].async_refresh()

    async def handle_stop_charging(call: ServiceCall):
        """Handle stopping charging."""
        for connector_id, runtime_data in device_data_generator(hass, call):
            alias = runtime_data["connectors"][connector_id]["alias"]
            await runtime_data["client"].async_stop_charging(alias)
            await asyncio.sleep(1)
            await runtime_data["connectors"][connector_id][
                "operational_data_coordinator"
            ].async_refresh()

    async def handle_reset_charger(call: ServiceCall):
        """Handle resetting charger."""
        reset_type = call.data["type"]

        for connector_id, runtime_data in device_data_generator(hass, call):
            await runtime_data["client"].async_reset_charger(connector_id, reset_type)

    async def handle_set_manual_schedules_enabled(call: ServiceCall):
        """Handle enabling or disabling manual schedules."""
        enabled: bool = call.data["enabled"]

        for connector_id, runtime_data in device_data_generator(hass, call):
            await runtime_data["client"].async_set_manual_schedules_enabled(
                connector_id, enabled
            )
            coordinator = runtime_data["connectors"][connector_id][
                "manual_schedules_coordinator"
            ]
            assert coordinator is not None
            await coordinator.async_refresh()

    async def handle_override_schedule(call: ServiceCall):
        """Handle overriding the schedule to charge now."""
        for connector_id, runtime_data in device_data_generator(hass, call):
            await runtime_data["client"].async_override_schedule(connector_id)
            await asyncio.sleep(1)
            coordinator = runtime_data["connectors"][connector_id][
                "active_schedule_coordinator"
            ]
            assert coordinator is not None
            await coordinator.async_refresh()

    async def handle_get_manual_schedules(call: ServiceCall):
        """Return manual schedules for the target connector."""
        result: dict = {}
        for connector_id, runtime_data in device_data_generator(hass, call):
            data = await runtime_data["client"].async_get_manual_schedules(connector_id)
            result = dict(data)
            break
        return result

    async def handle_create_manual_schedule(call: ServiceCall):
        """Create a manual schedule on the connector."""
        schedule: ManualSchedule = {
            "days": call.data["days"],
            "start": call.data["start"][:5],
            "stop": call.data["stop"][:5],
            "enabled": call.data["enabled"],
            "priority": call.data["priority"],
        }
        result = {}
        for connector_id, runtime_data in device_data_generator(hass, call):
            created = await runtime_data["client"].async_create_manual_schedule(
                connector_id, schedule
            )
            result[connector_id] = created
            coordinator = runtime_data["connectors"][connector_id][
                "manual_schedules_coordinator"
            ]
            assert coordinator is not None
            await coordinator.async_refresh()
        return result

    async def handle_update_manual_schedule(call: ServiceCall):
        """Update a manual schedule on the connector."""
        schedule_id = int(call.data["schedule_id"])
        schedule: ManualSchedule = {
            "id": schedule_id,
            "days": call.data["days"],
            "start": call.data["start"][:5],
            "stop": call.data["stop"][:5],
            "enabled": call.data["enabled"],
            "priority": call.data["priority"],
        }
        result = {}
        for connector_id, runtime_data in device_data_generator(hass, call):
            updated = await runtime_data["client"].async_update_manual_schedule(
                connector_id, schedule_id, schedule
            )
            result[connector_id] = updated
            coordinator = runtime_data["connectors"][connector_id][
                "manual_schedules_coordinator"
            ]
            assert coordinator is not None
            await coordinator.async_refresh()
        return result

    async def handle_delete_manual_schedule(call: ServiceCall):
        """Delete a manual schedule from the connector."""
        schedule_id = int(call.data["schedule_id"])
        for connector_id, runtime_data in device_data_generator(hass, call):
            await runtime_data["client"].async_delete_manual_schedule(
                connector_id, schedule_id
            )
            coordinator = runtime_data["connectors"][connector_id][
                "manual_schedules_coordinator"
            ]
            assert coordinator is not None
            await coordinator.async_refresh()

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

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_MANUAL_SCHEDULES_ENABLED,
        handle_set_manual_schedules_enabled,
        SET_MANUAL_SCHEDULES_ENABLED_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_OVERRIDE_SCHEDULE,
        handle_override_schedule,
        OVERRIDE_SCHEDULE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_MANUAL_SCHEDULES,
        handle_get_manual_schedules,
        GET_MANUAL_SCHEDULES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_MANUAL_SCHEDULE,
        handle_create_manual_schedule,
        CREATE_MANUAL_SCHEDULE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_MANUAL_SCHEDULE,
        handle_update_manual_schedule,
        UPDATE_MANUAL_SCHEDULE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_MANUAL_SCHEDULE,
        handle_delete_manual_schedule,
        DELETE_MANUAL_SCHEDULE_SCHEMA,
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
