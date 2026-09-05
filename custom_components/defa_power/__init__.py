"""DEFA Power integration for Home Assistant."""

import logging
from types import MappingProxyType
from typing import cast

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .cloudcharge_api.client import CloudChargeAPIClient
from .cloudcharge_api.exceptions import CloudChargeAPIError
from .cloudcharge_api.models import ChargePoint
from .const import (
    API_BASE_URL,
    CONF_REQUEST_INTERVAL_MS,
    CONFIG_ENTRY_VERSION,
    DEFAULT_REQUEST_INTERVAL_MS,
    DOMAIN,
    INITIAL_CHARGEPOINT_IDS,
    INITIAL_CONNECTOR_IDS,
)
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

    interval_ms = entry.options.get(
        CONF_REQUEST_INTERVAL_MS, DEFAULT_REQUEST_INTERVAL_MS
    )
    client = CloudChargeAPIClient(API_BASE_URL, request_interval=interval_ms / 1000.0)
    client.import_credentials(entry.data["credentials"])

    instance_id = entry.data.get("instance_id") or "default"
    device_registry = dr.async_get(hass)
    chargepoints: dict = {}
    connectors: dict = {}
    data: RuntimeData = {
        "chargepoints": chargepoints,
        "connectors": connectors,
        "client": client,
    }
    entry.runtime_data = data

    # Subentries for an entry migrated from 0.5.x are created by async_migrate_entry;
    # a freshly added entry carries the selection made in the config flow instead.
    if INITIAL_CONNECTOR_IDS in entry.data or INITIAL_CHARGEPOINT_IDS in entry.data:
        await _async_bootstrap_from_selection(hass, entry, client)

    # Build shared chargepoint coordinators; process chargepoint subentries first
    # so connector subentries can reuse them.
    cp_coordinators: dict[str, CloudChargeChargepointCoordinator] = {}
    # Device registry ids of the registered chargepoint devices, used by their
    # connectors as via_device_id
    cp_device_ids: dict[str, str] = {}

    for subentry in entry.subentries.values():
        if subentry.subentry_type != "chargepoint":
            continue
        cp_id = subentry.data["chargepoint_id"]
        if cp_id in cp_coordinators:
            continue
        coordinator = CloudChargeChargepointCoordinator(cp_id, hass, client)
        await coordinator.async_config_entry_first_refresh()
        cp_coordinators[cp_id] = coordinator
        chargepoint_device = ChargePointDevice(
            coordinator.data["chargepoint"], instance_id
        )
        # Register the chargepoint device up front so its connectors can reference
        # it by device id (via_device_id). Chargepoints without a subentry are
        # deliberately left unregistered: registering them on the main entry makes
        # HA show them under "Devices that don't belong to a sub-entry".
        chargepoint_device_entry = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            config_subentry_id=subentry.subentry_id,
            **chargepoint_device.get_device_info(),
        )
        cp_device_ids[cp_id] = chargepoint_device_entry.id
        cp: RuntimeDataChargePoint = {
            "coordinator": coordinator,
            "device": chargepoint_device,
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
            "device": ConnectorDevice(
                connector_val, instance_id, alias, cp_device_ids.get(cp_id)
            ),
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

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _chargepoint_subentry(cp_id: str, cp_data: ChargePoint) -> ConfigSubentry:
    """Build the subentry representing a chargepoint."""
    return ConfigSubentry(
        data=MappingProxyType({"chargepoint_id": cp_id}),
        subentry_type="chargepoint",
        title=cp_data.get("displayName") or cp_id,
        unique_id=cp_id,
    )


def _connector_subentry(connector_id: str, cp_id: str, title: str) -> ConfigSubentry:
    """Build the subentry representing a connector."""
    return ConfigSubentry(
        data=MappingProxyType(
            {
                "connector_id": connector_id,
                "chargepoint_id": cp_id,
                "connection_type": "cloudcharge",
            }
        ),
        subentry_type="connector",
        title=title,
        unique_id=connector_id,
    )


def _connector_title(cp_data: ChargePoint, cp_title: str, connector_id: str) -> str:
    """Return the display title for a connector of a chargepoint."""
    for alias, val in (cp_data.get("aliasMap") or {}).items():
        if val.get("id") == connector_id:
            return f"{val.get('displayName') or alias} ({cp_title})"
    return connector_id


async def _async_bootstrap_from_selection(
    hass: HomeAssistant,
    entry: DefaPowerConfigEntry,
    client: CloudChargeAPIClient,
) -> None:
    """Create subentries for connectors/chargepoints selected during initial setup."""
    initial_connectors: list[dict] = entry.data.get(INITIAL_CONNECTOR_IDS) or []
    initial_chargepoints: list[str] = entry.data.get(INITIAL_CHARGEPOINT_IDS) or []

    subentries: list[ConfigSubentry] = []
    cp_data_cache: dict[str, ChargePoint] = {}
    cp_ids_seen: set[str] = set()

    async def _ensure_cp_data(cp_id: str) -> ChargePoint:
        if cp_id not in cp_data_cache:
            cp_data_cache[cp_id] = await client.async_get_chargepoint(cp_id)
        return cp_data_cache[cp_id]

    try:
        # Explicitly selected chargepoints first
        for cp_id in initial_chargepoints:
            if cp_id in cp_ids_seen:
                continue
            cp_ids_seen.add(cp_id)
            subentries.append(
                _chargepoint_subentry(cp_id, await _ensure_cp_data(cp_id))
            )

        # Connectors — no automatic chargepoint subentry creation; only the
        # explicit selections above get one
        for item in initial_connectors:
            cp_id = item["chargepoint_id"]
            connector_id = item["connector_id"]
            cp_data = await _ensure_cp_data(cp_id)
            cp_title = cp_data.get("displayName") or cp_id
            subentries.append(
                _connector_subentry(
                    connector_id,
                    cp_id,
                    _connector_title(cp_data, cp_title, connector_id),
                )
            )
    except CloudChargeAPIError as err:
        raise ConfigEntryNotReady(
            f"Could not read the selected chargepoints from CloudCharge: {err}"
        ) from err

    for subentry in subentries:
        hass.config_entries.async_add_subentry(entry, subentry)

    # Drop the selection only once every subentry it describes exists, so a failed
    # attempt is retried with the selection intact rather than leaving the entry
    # set up with no devices at all.
    hass.config_entries.async_update_entry(
        entry,
        data={
            k: v
            for k, v in entry.data.items()
            if k not in (INITIAL_CONNECTOR_IDS, INITIAL_CHARGEPOINT_IDS)
        },
    )

    _LOGGER.info("Bootstrap complete: created %d subentries", len(subentries))


async def _async_migrate_to_subentries(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Give every chargepoint and connector of a 0.5.x entry its own subentry.

    Returns False when the CloudCharge API could not be read, so the migration is
    retried on the next restart instead of leaving the entry without subentries.
    """
    # An entry created by an 0.6.0 beta already has its subentries, and one whose
    # initial setup never finished gets them from the config flow selection; both
    # only need their devices reconciled below.
    if not entry.subentries and not (
        INITIAL_CONNECTOR_IDS in entry.data or INITIAL_CHARGEPOINT_IDS in entry.data
    ):
        _LOGGER.info("Migrating DEFA Power config entry to subentries")

        interval_ms = entry.options.get(
            CONF_REQUEST_INTERVAL_MS, DEFAULT_REQUEST_INTERVAL_MS
        )
        client = CloudChargeAPIClient(
            API_BASE_URL, request_interval=interval_ms / 1000.0
        )
        client.import_credentials(entry.data["credentials"])

        subentries: list[ConfigSubentry] = []
        try:
            for cp_id in await client.async_get_chargepoint_ids():
                cp_data = await client.async_get_chargepoint(cp_id)
                cp_title = cp_data.get("displayName") or cp_id
                subentries.append(_chargepoint_subentry(cp_id, cp_data))
                for val in (cp_data.get("aliasMap") or {}).values():
                    connector_id = val.get("id")
                    if not connector_id:
                        continue
                    subentries.append(
                        _connector_subentry(
                            connector_id,
                            cp_id,
                            _connector_title(cp_data, cp_title, connector_id),
                        )
                    )
        except CloudChargeAPIError as err:
            _LOGGER.error("Migration failed: could not read chargepoints: %s", err)
            return False
        finally:
            await client.async_close()

        # Added only after every call succeeded, so a partial migration is never
        # mistaken for a finished one on the next attempt.
        for subentry in subentries:
            hass.config_entries.async_add_subentry(entry, subentry)

        _LOGGER.info("Migration complete: created %d subentries", len(subentries))

    _async_assign_devices_to_subentries(hass, entry)
    return True


def _async_assign_devices_to_subentries(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Move devices registered before subentries existed into their subentry.

    Devices created by 0.5.x belong to the config entry itself
    (config_subentry_id=None). Letting `async_get_or_create` or `async_add_entities`
    re-register them under a subentry silently moves them, which HA deprecates and
    will reject in 2027.8, so move them explicitly here instead.
    """
    device_registry = dr.async_get(hass)
    instance_id = entry.data.get("instance_id") or "default"

    subentry_ids: dict[str, str] = {}
    for subentry in entry.subentries.values():
        if subentry.subentry_type == "chargepoint":
            subentry_ids[subentry.data["chargepoint_id"]] = subentry.subentry_id
        elif subentry.subentry_type == "connector":
            subentry_ids[subentry.data["connector_id"]] = subentry.subentry_id

    if not subentry_ids:
        return

    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        # This integration uses 3-part identifiers, wider than the 2-tuple HA types
        # them as, the same way ChargePointDevice/ConnectorDevice build them
        for identifier in cast("set[tuple[str, ...]]", device.identifiers):
            if len(identifier) != 3:
                continue
            domain, device_instance_id, device_id = identifier
            if domain != DOMAIN or device_instance_id != instance_id:
                continue
            subentry_id = subentry_ids.get(device_id)
            if subentry_id is None or device.config_subentry_id == subentry_id:
                continue
            _LOGGER.debug("Moving device %s to subentry %s", device_id, subentry_id)
            device_registry.async_update_device(
                device.id, new_config_subentry_id=subentry_id
            )
            break


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading DEFA Power config entry")
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data["client"].async_close()
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate an old entry to the current version."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > CONFIG_ENTRY_VERSION:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        # Credentials moved into their own dict
        new_data = {**config_entry.data}
        new_data["credentials"] = {
            "user_id": new_data.pop("userId"),
            "token": new_data.pop("token"),
        }
        hass.config_entries.async_update_entry(
            config_entry, data=new_data, version=2, minor_version=1
        )

    if config_entry.version == 2:
        # Chargepoints and connectors became subentries
        if not await _async_migrate_to_subentries(hass, config_entry):
            return False
        hass.config_entries.async_update_entry(
            config_entry,
            # "_setup_completed" tracked the subentry migration in the 0.6.0 betas
            # and is superseded by the entry version
            data={
                k: v for k, v in config_entry.data.items() if k != "_setup_completed"
            },
            version=3,
            minor_version=1,
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True


async def update_listener(hass: HomeAssistant, entry: DefaPowerConfigEntry):
    """Reload the entry when config changes (subentry added/removed, credentials or throttling updated)."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_setup(hass: HomeAssistant, config):
    """Set up the integration."""
    await async_setup_services(hass)
    return True
