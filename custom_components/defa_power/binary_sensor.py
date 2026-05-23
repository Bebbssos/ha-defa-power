"""Binary sensor entities for the DEFA Power integration."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DefaPowerConfigEntry
from .cloudcharge_api.models import ActiveScheduleSettings
from .coordinator import CloudChargeActiveScheduleCoordinator
from .devices import ConnectorDevice

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DefaPowerActiveScheduleBinarySensorDescription(BinarySensorEntityDescription):
    """Class to describe a DEFA Power active schedule binary sensor entity."""

    disabled_by_default: bool = False
    value_fn: Callable[[ActiveScheduleSettings], bool | None] | None = None
    create_if_none: bool = False


DEFA_POWER_ACTIVE_SCHEDULE_BINARY_SENSOR_TYPES: tuple[
    DefaPowerActiveScheduleBinarySensorDescription, ...
] = (
    DefaPowerActiveScheduleBinarySensorDescription(
        key="override_smart_charging",
        icon="mdi:lightning-bolt-circle",
        create_if_none=True,
        value_fn=lambda data: data.get("overrideSmartCharging"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: DefaPowerConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
):
    """Set up the binary sensor platform."""
    instance_id = entry.data.get("instance_id") or "default"

    for connector_id, val in entry.runtime_data["connectors"].items():
        if not val["capabilities"]["manualSchedules"]:
            continue
        subentry_id = val["subentry_id"]
        active_schedule_coordinator = val["active_schedule_coordinator"]
        assert active_schedule_coordinator is not None

        entities: list[BinarySensorEntity] = []
        for description in DEFA_POWER_ACTIVE_SCHEDULE_BINARY_SENSOR_TYPES:
            if description.value_fn is None:
                continue
            current_value = description.value_fn(
                active_schedule_coordinator.data or {}  # type: ignore[arg-type]
            )

            if description.create_if_none is False and current_value is None:
                _LOGGER.debug(
                    "Skipping entity %s for connector %s, value is None or missing",
                    description.key,
                    connector_id,
                )
                val["skipped_entities"].append(description.key)
                continue

            entities.append(
                ActiveScheduleBinarySensorEntity(
                    connector_id,
                    active_schedule_coordinator,
                    description,
                    val["device"],
                    instance_id,
                )
            )

        if entities:
            async_add_entities(entities, update_before_add=True, config_subentry_id=subentry_id)


class ActiveScheduleBinarySensorEntity(
    CoordinatorEntity[CloudChargeActiveScheduleCoordinator], BinarySensorEntity
):
    """Binary sensor entity for active schedule data."""

    _attr_has_entity_name = True
    entity_description: DefaPowerActiveScheduleBinarySensorDescription

    def __init__(
        self,
        connector_id: str,
        coordinator: CloudChargeActiveScheduleCoordinator,
        description: DefaPowerActiveScheduleBinarySensorDescription,
        device: ConnectorDevice,
        instance_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, description.key)
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{instance_id}_{connector_id}_{description.key}"
        self._attr_translation_key = f"defa_power_{description.key}"
        self._attr_icon = description.icon

        if description.disabled_by_default:
            self._attr_entity_registry_enabled_default = False

        self._attr_device_info = device.get_device_info()
        self._state: bool | None = None
        self._set_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self._state

    def _set_state(self) -> bool:
        """Update state from coordinator. Return True if changed."""
        if self.coordinator.data is None or self.entity_description.value_fn is None:
            return False
        new_state = self.entity_description.value_fn(self.coordinator.data)
        if new_state != self._state:
            self._state = new_state
            return True
        return False

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._set_state():
            self.async_write_ha_state()
