"""DEFA Power button entites."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from .cloudcharge_api.exceptions import CloudChargeForbiddenError

from .coordinator import CloudChargeOperationalDataCoordinator
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DefaPowerConfigEntry
from .cloudcharge_api.client import CloudChargeAPIClient
from .devices import ConnectorDevice

_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True, kw_only=True)
class DefaPowerChargeStartStopButtonDescription(ButtonEntityDescription):
    """Class to describe an DEFA Power button entity."""

    disabled_by_default: bool = False
    on_press: Callable[[str, CloudChargeAPIClient], Awaitable[None]]
    available_on_states: list[str]
    refresh_coordinator_wait: float


async def start_charging(alias: str, client: CloudChargeAPIClient) -> None:
    """Start charging."""
    try:
        await client.async_start_charging(alias)
    except CloudChargeForbiddenError:
        raise ValueError("Starting charging is not allowed")


async def stop_charging(alias: str, client: CloudChargeAPIClient) -> None:
    """Stop charging."""
    try:
        await client.async_stop_charging(alias)
    except CloudChargeForbiddenError:
        raise ValueError("Stopping charging is not allowed")


DEFA_POWER_CONNECTOR_SENSOR_TYPES: tuple[DefaPowerChargeStartStopButtonDescription, ...] = (
    DefaPowerChargeStartStopButtonDescription(
        key="start_charging",
        icon="mdi:flash",
        on_press=start_charging,
        available_on_states=["EVConnected"],
        refresh_coordinator_wait=5, # Start charging takes a while to update, waiting 5 seconds should be enough
    ),
    DefaPowerChargeStartStopButtonDescription(
        key="stop_charging",
        icon="mdi:flash-off",
        on_press=stop_charging,
        available_on_states=["Charging", "SuspendedEV"],
        refresh_coordinator_wait=1, # Stop charging is faster, waiting 1 second should be enough
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: DefaPowerConfigEntry, async_add_entities
):
    """Set up the sensor platform."""

    instance_id = entry.data.get("instance_id") or "default"
    entities: list[ButtonEntity] = []

    for connector_id, val in entry.runtime_data["connectors"].items():
        operational_data_coordinator = val["operational_data_coordinator"]
        entities.extend(
            ChargeStartStopButton(
                connector_id,
                val["alias"],
                sensorType,
                val["device"],
                entry.runtime_data["client"],
                instance_id,
                operational_data_coordinator,
            )
            for sensorType in DEFA_POWER_CONNECTOR_SENSOR_TYPES
        )
        entities.append(ChargerRestartButton(connector_id, val["device"], entry.runtime_data["client"], instance_id))

    async_add_entities(entities, update_before_add=True)


class ChargeStartStopButton(CoordinatorEntity, ButtonEntity):
    """Button entity for starting or stopping charging."""

    _attr_has_entity_name = True
    is_available = False
    is_processing = False

    def __init__(
        self,
        connector_id: str,
        connector_alias: str,
        description: DefaPowerChargeStartStopButtonDescription,
        device: ConnectorDevice,
        client: CloudChargeAPIClient,
        instance_id: str,
        coordinator: CloudChargeOperationalDataCoordinator,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator)
        self.client = client
        self.connector_alias = connector_alias
        self.entity_description = description
        self.coordinator = coordinator

        self._attr_unique_id = f"{instance_id}_{connector_id}_{description.key}"
        self._attr_translation_key = f"defa_power_{description.key}"
        self._attr_icon = description.icon

        if description.disabled_by_default:
            self._attr_entity_registry_enabled_default = False

        self._attr_device_info = device.get_device_info()

    async def async_press(self) -> None:
        """Handle the button press."""

        try:
            self.is_processing = True
            self.async_write_ha_state()
            await self.entity_description.on_press(self.connector_alias, self.client)
        finally:
            _LOGGER.debug("Refreshing data in %s seconds", self.entity_description.refresh_coordinator_wait)
            try:
                await asyncio.sleep(self.entity_description.refresh_coordinator_wait)
                await self.coordinator.async_refresh()
            finally:
                self.is_processing = False
                self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        is_available = self.coordinator.data is not None and self.coordinator.data.get("ocpp", {}).get("chargingState") in self.entity_description.available_on_states
        if is_available != self.is_available:
            self.is_available = is_available
            self.async_write_ha_state()

    @property
    def available(self):
        """Return True if entity is available."""
        return self.is_available and not self.is_processing

class ChargerRestartButton(ButtonEntity):
    """Button entity for restarting charger."""

    _attr_has_entity_name = True

    def __init__(
        self,
        connector_id: str,
        device: ConnectorDevice,
        client: CloudChargeAPIClient,
        instance_id: str,
    ) -> None:
        """Initialize the button entity."""
        self.client = client
        self.connector_id = connector_id

        self._attr_unique_id = f"{instance_id}_{connector_id}_restart"
        self._attr_translation_key = "defa_power_restart"
        self._attr_icon = "mdi:restart"

        self._attr_device_info = device.get_device_info()

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.client.async_restart_charger(self.connector_id)