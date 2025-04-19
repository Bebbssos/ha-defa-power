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
from .cloudcharge_api.models import EcoModeConfiguration, EcoModeConfigurationRequest
from .coordinator import CloudChargeEcoModeCoordinator
from .devices import ConnectorDevice

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class DefaPowerEcoModeSwitchDescription(SwitchEntityDescription):
    """Class to describe a DEFA Power eco mode switch entity."""

    disabled_by_default: bool = False
    value_fn: Callable[[EcoModeConfiguration], bool] | None = None
    set_fn: Callable[[str, CloudChargeAPIClient, bool], None] | None = None


async def async_setup_entry(
    hass: HomeAssistant, entry: DefaPowerConfigEntry, async_add_entities
):
    """Set up the switch platform."""
    instance_id = entry.data.get("instance_id") or "default"
    entities = []

    for connector_id, val in entry.runtime_data["connectors"].items():
        eco_mode_coordinator = val["eco_mode_coordinator"]

        # Add eco mode switches
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

    async_add_entities(entities, update_before_add=True)


async def set_eco_mode_active(
    connector_id: str, client: CloudChargeAPIClient, active: bool
) -> None:
    """Set the eco mode active state for a given connector."""
    # First, get the existing eco mode configuration
    eco_mode_config = await client.async_get_eco_mode_configuration(connector_id)

    # Create the update request with the new active value
    request: EcoModeConfigurationRequest = {
        "active": active,
        "hoursToCharge": eco_mode_config["hoursToCharge"],
        "pickupTimeEnabled": eco_mode_config["pickupTimeEnabled"],
        "dayOfWeekMap": eco_mode_config["dayOfWeekMap"],
    }

    # Send the updated configuration
    await client.async_set_eco_mode_configuration(connector_id, request)


async def set_pickup_time_enabled(
    connector_id: str, client: CloudChargeAPIClient, enabled: bool
) -> None:
    """Set the pickup time enabled state for a given connector."""
    # First, get the existing eco mode configuration
    eco_mode_config = await client.async_get_eco_mode_configuration(connector_id)

    # Create the update request with the new pickup time enabled value
    request: EcoModeConfigurationRequest = {
        "active": eco_mode_config["active"],
        "hoursToCharge": eco_mode_config["hoursToCharge"],
        "pickupTimeEnabled": enabled,
        "dayOfWeekMap": eco_mode_config["dayOfWeekMap"],
    }

    # Send the updated configuration
    await client.async_set_eco_mode_configuration(connector_id, request)


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


class EcoModeSwitchEntity(CoordinatorEntity, SwitchEntity):
    """Switch entity for controlling eco mode settings."""

    _attr_has_entity_name = True
    state_val = None

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
        if self.coordinator.data is None:
            return False

        new_state = self.entity_description.value_fn(self.coordinator.data)

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
        await self.entity_description.set_fn(self.connector_id, self.client, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.set_fn(self.connector_id, self.client, False)
        await self.coordinator.async_request_refresh()
