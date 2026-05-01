"""Switch entities for the DEFA Power integration."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DefaPowerConfigEntry
from .cloudcharge_api.client import CloudChargeAPIClient
from .cloudcharge_api.models import EcoModeConfiguration
from .coordinator import (
    CloudChargeEcoModeCoordinator,
    CloudChargeManualSchedulesCoordinator,
)
from .devices import ConnectorDevice

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DefaPowerEcoModeSwitchDescription(SwitchEntityDescription):
    """Class to describe a DEFA Power eco mode switch entity."""

    disabled_by_default: bool = False
    value_fn: Callable[[EcoModeConfiguration], bool] | None = None
    set_fn: Callable[[EcoModeConfiguration, bool], None] | None = None


async def async_setup_entry(
    hass: HomeAssistant, entry: DefaPowerConfigEntry, async_add_entities
):
    """Set up the switch platform."""
    instance_id = entry.data.get("instance_id") or "default"
    entities = []

    for connector_id, val in entry.runtime_data["connectors"].items():
        if val["capabilities"]["ecoMode"]:
            # Add eco mode switches if eco mode is supported by the connector
            eco_mode_coordinator = val["eco_mode_coordinator"]
            assert eco_mode_coordinator is not None

            entities.extend(
                EcoModeSwitchEntity(
                    connector_id,
                    eco_mode_coordinator,
                    description,
                    val["device"],
                    entry.runtime_data["client"],
                    instance_id,
                )
                for description in ECO_MODE_SWITCH_TYPES
            )

        if val["capabilities"]["manualSchedules"]:
            manual_schedules_coordinator = val["manual_schedules_coordinator"]
            assert manual_schedules_coordinator is not None

            entities.append(
                ManualSchedulesSwitchEntity(
                    connector_id,
                    manual_schedules_coordinator,
                    val["device"],
                    entry.runtime_data["client"],
                    instance_id,
                )
            )

    async_add_entities(entities, update_before_add=True)


def set_eco_mode_active(config: EcoModeConfiguration, active: bool) -> None:
    """Set the eco mode active state for a given connector."""
    config["active"] = active


def set_pickup_time_enabled(config: EcoModeConfiguration, enabled: bool) -> None:
    """Set the pickup time enabled state for a given connector."""
    config["pickupTimeEnabled"] = enabled


ECO_MODE_SWITCH_TYPES = (
    DefaPowerEcoModeSwitchDescription(
        key="eco_mode_active",
        icon="mdi:leaf",
        value_fn=lambda data: data.get("active", False),
        set_fn=set_eco_mode_active,
    ),
    DefaPowerEcoModeSwitchDescription(
        key="eco_mode_pickup_time_enabled",
        icon="mdi:clock-time-four-outline",
        value_fn=lambda data: data.get("pickupTimeEnabled", False),
        set_fn=set_pickup_time_enabled,
    ),
)


class EcoModeSwitchEntity(
    CoordinatorEntity[CloudChargeEcoModeCoordinator], SwitchEntity
):
    """Switch entity for controlling eco mode settings."""

    _attr_has_entity_name = True
    state_val = None
    entity_description: DefaPowerEcoModeSwitchDescription

    def __init__(
        self,
        connector_id: str,
        coordinator: CloudChargeEcoModeCoordinator,
        description: DefaPowerEcoModeSwitchDescription,
        device: ConnectorDevice,
        client: CloudChargeAPIClient,
        instance_id: str,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, description.key)
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{instance_id}_{connector_id}_{description.key}"
        self._attr_translation_key = f"defa_power_{description.key}"
        self._attr_icon = description.icon

        if description.disabled_by_default:
            self._attr_entity_registry_enabled_default = False

        self.connector_id = connector_id
        self.client = client
        self._attr_device_info = device.get_device_info()
        self._set_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    def _set_state(self) -> bool:
        """Update the state from coordinator. Return True if the state has changed."""
        data = self.coordinator.get_data()
        if data is None:
            return False

        if self.entity_description.value_fn is None:
            return False
        new_state = self.entity_description.value_fn(data)

        if new_state != self.state_val:
            self.state_val = new_state
            return True

        return False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._set_state():
            self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        return self.state_val

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if self.entity_description.set_fn is None:
            return
        set_fn = self.entity_description.set_fn
        await self.coordinator.set_data(lambda config: set_fn(config, True))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        if self.entity_description.set_fn is None:
            return
        set_fn = self.entity_description.set_fn
        await self.coordinator.set_data(lambda config: set_fn(config, False))


class ManualSchedulesSwitchEntity(
    CoordinatorEntity[CloudChargeManualSchedulesCoordinator], SwitchEntity
):
    """Switch entity for enabling/disabling manual charging schedules."""

    _attr_has_entity_name = True

    def __init__(
        self,
        connector_id: str,
        coordinator: CloudChargeManualSchedulesCoordinator,
        device: ConnectorDevice,
        client: CloudChargeAPIClient,
        instance_id: str,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._attr_unique_id = f"{instance_id}_{connector_id}_manual_schedules_enabled"
        self._attr_translation_key = "defa_power_manual_schedules_enabled"
        self._attr_icon = "mdi:calendar-clock"
        self._attr_device_info = device.get_device_info()
        self.connector_id = connector_id
        self.client = client

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def is_on(self) -> bool | None:
        """Return true if manual schedules are enabled."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("schedulingEnabled", False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable manual schedules."""
        await self.client.async_set_manual_schedules_enabled(self.connector_id, True)
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable manual schedules."""
        await self.client.async_set_manual_schedules_enabled(self.connector_id, False)
        await self.coordinator.async_refresh()
