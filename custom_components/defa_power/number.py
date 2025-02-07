"""DEFA Power number entities."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DefaPowerConfigEntry
from .cloudcharge_api.models import Connector
from .cloudcharge_api.client import CloudChargeAPIClient
from .devices import ConnectorDevice

_LOGGER = logging.getLogger(__name__)


# TODO: Can this be done in the class instead, like Roborock?
async def set_max_current(connector_id: str, client: CloudChargeAPIClient, current: int) -> None: 
    await client.async_set_max_current(connector_id, current)


@dataclass(frozen=True, kw_only=True)
class DefaPowerConnectorNumberDescription(NumberEntityDescription):
    """Class to describe a DEFA Power number entity."""

    disabled_by_default: bool = False
    options: list[str] | None = None
    value_fn: Callable[[Connector], int] | None = None
    set_fn: Callable[[str, CloudChargeAPIClient, int], None] | None = None


DEFA_POWER_CONNECTOR_NUMBER_TYPES: tuple[DefaPowerConnectorNumberDescription, ...] = (
    DefaPowerConnectorNumberDescription(
        key="ampere",
        icon="mdi:current-ac",
        native_min_value=6,     # TODO: Fetch these values from the API instead of hard coding them
        native_max_value=15,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=NumberDeviceClass.CURRENT,
        value_fn=lambda data: data.get("ampere"),
        set_fn=set_max_current,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: DefaPowerConfigEntry, async_add_entities
):
    """Set up the number platform."""

    instance_id = entry.data.get("instance_id") or "default"
    entities: list[NumberEntity] = []

    for connector_id, val in entry.runtime_data["connectors"].items():
        for sensor_type in DEFA_POWER_CONNECTOR_NUMBER_TYPES:
            coordinator = entry.runtime_data["chargers_coordinator"]

            entities.append(
                DefaConnectorNumberEntity(
                    connector_id,
                    val["alias"],
                    coordinator,
                    sensor_type,
                    val["device"],
                    entry.runtime_data["client"],
                    instance_id,
                )
            )

    async_add_entities(entities, update_before_add=True)


class DefaConnectorNumberEntity(CoordinatorEntity, NumberEntity):
    """Base class for DEFA Power number entities."""

    state_val = None
    _attr_has_entity_name = True

    def __init__(
        self,
        id: str,
        alias: str,
        coordinator,
        description: DefaPowerConnectorNumberDescription,
        device: ConnectorDevice,
        client: CloudChargeAPIClient,
        instance_id: str,
    ) -> None:
        """Initialize the entity."""
        self.id_lookup_required = True
        context = alias

        super().__init__(coordinator, context)
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{instance_id}_{id}_{description.key}"
        self._attr_translation_key = f"defa_power_{description.key}"
        if description.device_class is not None:
            self._attr_device_class = description.device_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_unit_of_measurement = description.native_unit_of_measurement
        self._attr_icon = description.icon

        if description.disabled_by_default:
            self._attr_entity_registry_enabled_default = False

        self.id = id
        self.alias = alias
        self.client = client
        self._attr_device_info = device.get_device_info()
        self._set_state()

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    def _set_state(self):
        """Update the state from coordinator. Return True if the state has changed."""
        if self.coordinator.data is None:
            return False

        new_state = self.entity_description.value_fn(
            self.coordinator.data["connectors"][self.alias]
        )

        if new_state != self.state_val:
            self.state_val = new_state
            return True

        return False

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._set_state():
            self.async_write_ha_state()

    # TODO: Exception handling
    async def async_set_native_value(self, value: float) -> None:
        await self.entity_description.set_fn(self.id, self.client, int(value))
        await self.coordinator.async_request_refresh()

    @property
    def state(self):
        """Return the state of the entity."""
        return self.state_val

    @property
    def options(self) -> list[str] | None:
        """Return the option of the sensor."""
        return self.entity_description.options
