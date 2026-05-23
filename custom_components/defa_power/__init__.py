"""DEFA Power integration for Home Assistant."""

import logging
from types import MappingProxyType

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .cloudcharge_api.client import CloudChargeAPIClient
from .cloudcharge_api.exceptions import CloudChargeAPIError
from .const import API_BASE_URL
from .coordinator import (
    CloudChargeActiveScheduleCoordinator,
    CloudChargeChargepointCoordinator,
    CloudChargeEcoModeCoordinator,
    CloudChargeManualSchedulesCoordinator,
    CloudChargeOperationalDataCoordinator,
)
from .devices import ChargePointDevice, ConnectorDevice
from .models import (
    DefaPowerConfigEntry,
    RuntimeData,
    RuntimeDataChargePoint,
    RuntimeDataConnector,
    RuntimeDataConnectorCapabilities,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema("defa_power")

PLATFORMS = ["binary_sensor", "sensor", "button", "number", "select", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: DefaPowerConfigEntry) -> bool:
    """Set up DEFA Power from a config entry."""
    _LOGGER.info("Setting up DEFA Power from config entry")

    client = CloudChargeAPIClient(API_BASE_URL)
    client.import_credentials(entry.data["credentials"])

    instance_id = entry.data.get("instance_id") or "default"
    chargepoints: dict = {}
    connectors: dict = {}
    data: RuntimeData = {
        "chargepoints": chargepoints,
        "connectors": connectors,
        "client": client,
    }
    entry.runtime_data = data

    if not entry.subentries and not entry.data.get("_setup_completed"):
        if "initial_connector_ids" in entry.data:
            await _async_bootstrap_from_selection(hass, entry, client)
        else:
            await _async_migrate_to_subentries(hass, entry, client)
        hass.config_entries.async_update_entry(
            entry,
            data={
                k: v for k, v in entry.data.items()
                if k not in ("initial_connector_ids", "initial_chargepoint_ids")
            } | {"_setup_completed": True},
        )

    # Build shared chargepoint coordinators; process chargepoint subentries first
    # so connector subentries can reuse them.
    cp_coordinators: dict[str, CloudChargeChargepointCoordinator] = {}

    for subentry in entry.subentries.values():
        if subentry.subentry_type != "chargepoint":
            continue
        cp_id = subentry.data["chargepoint_id"]
        if cp_id in cp_coordinators:
            continue
        coordinator = CloudChargeChargepointCoordinator(cp_id, hass, client)
        await coordinator.async_config_entry_first_refresh()
        cp_coordinators[cp_id] = coordinator
        cp: RuntimeDataChargePoint = {
            "coordinator": coordinator,
            "device": ChargePointDevice(coordinator.data["chargepoint"], instance_id),
            "skipped_entities": [],
            "has_subentry": True,
            "subentry_id": subentry.subentry_id,
        }
        chargepoints[cp_id] = cp

    for subentry in entry.subentries.values():
        if subentry.subentry_type != "connector":
            continue
        cp_id = subentry.data["chargepoint_id"]
        connector_id = subentry.data["connector_id"]

        # Ensure a chargepoint coordinator exists (may not have its own subentry)
        if cp_id not in cp_coordinators:
            coordinator = CloudChargeChargepointCoordinator(cp_id, hass, client)
            await coordinator.async_config_entry_first_refresh()
            cp_coordinators[cp_id] = coordinator
            chargepoints[cp_id] = {
                "coordinator": coordinator,
                "device": ChargePointDevice(
                    coordinator.data["chargepoint"], instance_id
                ),
                "skipped_entities": [],
                "has_subentry": False,
                "subentry_id": None,
            }

        coord = cp_coordinators[cp_id]

        # Locate the connector within chargepoint data by connector_id
        alias: str | None = None
        connector_val = None
        for a, v in (coord.data or {}).get("connectors", {}).items():
            if v["id"] == connector_id:
                alias = a
                connector_val = v
                break

        if alias is None or connector_val is None:
            _LOGGER.error(
                "Connector %s not found in chargepoint %s data; skipping",
                connector_id,
                cp_id,
            )
            continue

        capabilities: RuntimeDataConnectorCapabilities = {
            "ecoMode": connector_val.get("capabilities", {}).get("ecoMode", False),
            "manualSchedules": connector_val.get("capabilities", {}).get(
                "manualSchedules", False
            ),
        }

        operational_data_coordinator = CloudChargeOperationalDataCoordinator(
            connector_id, hass, client
        )
        await operational_data_coordinator.async_config_entry_first_refresh()

        eco_mode_coordinator: CloudChargeEcoModeCoordinator | None = None
        if capabilities["ecoMode"]:
            eco_mode_coordinator = CloudChargeEcoModeCoordinator(
                connector_id, hass, client
            )
            await eco_mode_coordinator.async_config_entry_first_refresh()

        manual_schedules_coordinator: CloudChargeManualSchedulesCoordinator | None = None
        active_schedule_coordinator: CloudChargeActiveScheduleCoordinator | None = None
        if capabilities["manualSchedules"]:
            manual_schedules_coordinator = CloudChargeManualSchedulesCoordinator(
                connector_id, hass, client
            )
            await manual_schedules_coordinator.async_config_entry_first_refresh()
            active_schedule_coordinator = CloudChargeActiveScheduleCoordinator(
                connector_id, hass, client
            )
            await active_schedule_coordinator.async_config_entry_first_refresh()
            manual_schedules_coordinator.register_dependent_coordinator(
                active_schedule_coordinator
            )
            if eco_mode_coordinator is not None:
                eco_mode_coordinator.register_dependent_coordinator(
                    active_schedule_coordinator
                )

        conn: RuntimeDataConnector = {
            "device": ConnectorDevice(connector_val, instance_id, alias, chargepoint_registered=chargepoints[cp_id]["has_subentry"]),
            "alias": alias,
            "chargepoint_id": cp_id,
            "operational_data_coordinator": operational_data_coordinator,
            "eco_mode_coordinator": eco_mode_coordinator,
            "manual_schedules_coordinator": manual_schedules_coordinator,
            "active_schedule_coordinator": active_schedule_coordinator,
            "capabilities": capabilities,
            "skipped_entities": [],
            "subentry_id": subentry.subentry_id,
            "connection_type": subentry.data.get("connection_type", "cloudcharge"),
        }
        connectors[connector_id] = conn

    # Pre-register chargepoint devices so connector devices can reference them via via_device.
    # Skip implicit parents (no subentry) — registering them to the main entry without a
    # subentry causes HA to show them under "Devices that don't belong to a sub-entry".
    device_registry = dr.async_get(hass)
    for cp_data in chargepoints.values():
        if not cp_data["has_subentry"]:
            continue
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            config_subentry_id=cp_data["subentry_id"],
            **cp_data["device"].get_device_info()
        )

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_bootstrap_from_selection(
    hass: HomeAssistant,
    entry: DefaPowerConfigEntry,
    client: CloudChargeAPIClient,
) -> None:
    """Create subentries for connectors/chargepoints selected during initial setup."""
    initial_connectors: list[dict] = entry.data.get("initial_connector_ids") or []
    initial_chargepoints: list[str] = entry.data.get("initial_chargepoint_ids") or []

    if not initial_connectors and not initial_chargepoints:
        return

    cp_data_cache: dict = {}
    cp_ids_seen: set[str] = set()

    async def _ensure_cp_data(cp_id: str) -> dict:
        if cp_id not in cp_data_cache:
            try:
                cp_data_cache[cp_id] = await client.async_get_chargepoint(cp_id)
            except CloudChargeAPIError as err:
                _LOGGER.error("Bootstrap failed for chargepoint %s: %s", cp_id, err)
                cp_data_cache[cp_id] = {}
        return cp_data_cache[cp_id]

    def _add_chargepoint_subentry(cp_id: str, cp_data: dict) -> None:
        if cp_id in cp_ids_seen:
            return
        cp_ids_seen.add(cp_id)
        cp_title = cp_data.get("displayName") or cp_id
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType({"chargepoint_id": cp_id}),
                subentry_type="chargepoint",
                title=cp_title,
                unique_id=cp_id,
            ),
        )

    # Explicitly selected chargepoints first
    for cp_id in initial_chargepoints:
        cp_data = await _ensure_cp_data(cp_id)
        _add_chargepoint_subentry(cp_id, cp_data)

    # Connectors — no automatic chargepoint subentry creation; only explicit selections above
    for item in initial_connectors:
        cp_id = item["chargepoint_id"]
        connector_id = item["connector_id"]

        cp_data = await _ensure_cp_data(cp_id)
        cp_name = cp_data.get("displayName") or cp_id

        conn_title = connector_id
        for alias, val in (cp_data.get("aliasMap") or {}).items():
            if val.get("id") == connector_id:
                conn_title = f"{val.get('displayName') or alias} ({cp_name})"
                break

        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType(
                    {
                        "connector_id": connector_id,
                        "chargepoint_id": cp_id,
                        "connection_type": "cloudcharge",
                    }
                ),
                subentry_type="connector",
                title=conn_title,
                unique_id=connector_id,
            ),
        )

    _LOGGER.info("Bootstrap complete: created %d subentries", len(entry.subentries))


async def _async_migrate_to_subentries(
    hass: HomeAssistant,
    entry: DefaPowerConfigEntry,
    client: CloudChargeAPIClient,
) -> None:
    """Create subentries for all existing connectors/chargepoints (one-time migration)."""
    _LOGGER.info("Migrating DEFA Power config entry to subentries")
    try:
        chargepoint_ids = await client.async_get_chargepoint_ids()
    except CloudChargeAPIError as err:
        _LOGGER.error("Migration failed: could not fetch chargepoints: %s", err)
        return

    for cp_id in chargepoint_ids:
        try:
            cp_data = await client.async_get_chargepoint(cp_id)
        except CloudChargeAPIError as err:
            _LOGGER.error("Migration failed for chargepoint %s: %s", cp_id, err)
            continue

        cp_title = cp_data.get("displayName") or cp_id
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType({"chargepoint_id": cp_id}),
                subentry_type="chargepoint",
                title=cp_title,
                unique_id=cp_id,
            ),
        )

        for alias, val in (cp_data.get("aliasMap") or {}).items():
            connector_id = val.get("id")
            if not connector_id:
                continue
            conn_title = f"{val.get('displayName') or alias} ({cp_title})"
            hass.config_entries.async_add_subentry(
                entry,
                ConfigSubentry(
                    data=MappingProxyType(
                        {"connector_id": connector_id, "chargepoint_id": cp_id, "connection_type": "cloudcharge"}
                    ),
                    subentry_type="connector",
                    title=conn_title,
                    unique_id=connector_id,
                ),
            )

    _LOGGER.info(
        "Migration complete: created %d subentries", len(entry.subentries)
    )


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading DEFA Power config entry")
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
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
    """Reload the entry when config changes (subentry added/removed, credentials updated)."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_setup(hass: HomeAssistant, config):
    """Set up the integration."""
    await async_setup_services(hass)
    return True
