"""DEFA Power number entities."""

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.const import UnitOfElectricCurrent, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DefaPowerConfigEntry
from .cloudcharge_api.client import CloudChargeAPIClient
from .cloudcharge_api.models import (
    Connector,
    EcoModeConfiguration,
    EcoModeConfigurationRequest,
)
from .coordinator import CloudChargeEcoModeCoordinator
from .devices import ConnectorDevice

_LOGGER = logging.getLogger(__name__)


async def set_max_current(
    connector_id: str, client: CloudChargeAPIClient, current: int
) -> None:
    """Set the maximum current for a given connector using the CloudChargeAPIClient."""
    await client.async_set_max_current(connector_id, current)


async def fetch_min_max_values(
    client: CloudChargeAPIClient, connector_id: str
) -> tuple[int, int]:
    """Fetch min/max values from CloudChargeAPIClient asynchronously."""
    try:
        response = await client.async_get_max_current_alternatives(connector_id)

        if response:
            keys = sorted(int(k) for k in response)
            return keys[0], keys[-1]  # Return min and max values

    except (KeyError, ValueError, TypeError, Exception) as e:
        _LOGGER.warning(
            "Failed to fetch currentAlternatives for connector %s: %s. Using defaults",
            connector_id,
            e,
        )

    return 6, 32  # Default fallback values


@dataclass(kw_only=True)  # Remove frozen=True
class DefaPowerConnectorNumberDescription(NumberEntityDescription):
    """Class to describe a DEFA Power number entity."""

    disabled_by_default: bool = False
    options: list[str] | None = None
    value_fn: Callable[[Connector], int] | None = None
    set_fn: Callable[[str, CloudChargeAPIClient, int], None] | None = None
    get_limits_fn: Callable[[CloudChargeAPIClient, str], tuple[int, int]] | None = None


DEFA_POWER_CONNECTOR_NUMBER_TYPES: tuple[DefaPowerConnectorNumberDescription, ...] = (
    DefaPowerConnectorNumberDescription(
        key="ampere",
        icon="mdi:current-ac",
        native_min_value=6,  # Default value
        native_max_value=32,  # Default value
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=NumberDeviceClass.CURRENT,
        value_fn=lambda data: data.get("ampere"),
        set_fn=set_max_current,
        get_limits_fn=fetch_min_max_values,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: DefaPowerConfigEntry, async_add_entities
):
    """Set up the number platform."""

    instance_id = entry.data.get("instance_id") or "default"
    entities: list[NumberEntity] = []

    client = entry.runtime_data["client"]

    # Set up regular DEFA Power connector number entities
    for connector_id, val in entry.runtime_data["connectors"].items():
        # Add standard number entities (current limit)
        for description in DEFA_POWER_CONNECTOR_NUMBER_TYPES:
            description_dict = description.__dict__.copy()

            # Update min/max values if get_limits_fn is provided
            if description.get_limits_fn:
                min_limit, max_limit = await description.get_limits_fn(
                    client, connector_id
                )
                description_dict["native_min_value"] = min_limit
                description_dict["native_max_value"] = max_limit

            # Create a new instance with updated values
            entity_description = DefaPowerConnectorNumberDescription(**description_dict)

            chargepoint_id = val["chargepoint_id"]
            chargepoint_data = entry.runtime_data["chargepoints"][chargepoint_id]
            coordinator = chargepoint_data["coordinator"]

            entities.append(
                DefaConnectorNumberEntity(
                    connector_id,
                    val["alias"],
                    coordinator,
                    entity_description,
                    val["device"],
                    client,
                    instance_id,
                )
            )

        # Add eco mode number entities
        eco_mode_coordinator = val["eco_mode_coordinator"]
        for description in ECO_MODE_NUMBER_TYPES:
            entities.append(
                EcoModeNumberEntity(
                    connector_id,
                    eco_mode_coordinator,
                    description,
                    val["device"],
                    client,
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

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        try:
            await self.entity_description.set_fn(self.id, self.client, int(value))
            await self.coordinator.async_request_refresh()
        except Exception as e:
            _LOGGER.error(
                "Failed to set maximum current to %s for %s: %s", value, self.id, str(e)
            )
            raise HomeAssistantError("Failed to set maximum current") from e

    @property
    def state(self):
        """Return the state of the entity."""
        return self.state_val

    @property
    def options(self) -> list[str] | None:
        """Return the option of the sensor."""
        return self.entity_description.options


@dataclass(kw_only=True)
class DefaPowerEcoModeNumberDescription(NumberEntityDescription):
    """Class to describe a DEFA Power eco mode number entity."""

    disabled_by_default: bool = False
    value_fn: Callable[[EcoModeConfiguration], int] | None = None
    set_fn: Callable[[str, CloudChargeAPIClient, int], None] | None = None


async def set_hours_to_charge(
    connector_id: str, client: CloudChargeAPIClient, hours: int
) -> None:
    """Set the hours to charge for eco mode in the CloudChargeAPIClient."""
    # First, get the existing eco mode configuration
    eco_mode_config = await client.async_get_eco_mode_configuration(connector_id)

    # Create the update request with the new hours to charge value
    request: EcoModeConfigurationRequest = {
        "active": eco_mode_config["active"],
        "hoursToCharge": hours,
        "pickupTimeEnabled": eco_mode_config["pickupTimeEnabled"],
        "dayOfWeekMap": eco_mode_config["dayOfWeekMap"],
    }

    # Send the updated configuration
    await client.async_set_eco_mode_configuration(connector_id, request)


ECO_MODE_NUMBER_TYPES: tuple[DefaPowerEcoModeNumberDescription, ...] = (
    DefaPowerEcoModeNumberDescription(
        key="hours_to_charge",
        icon="mdi:timer-outline",
        native_min_value=1,
        native_max_value=24,
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=lambda data: data.get("hoursToCharge", 1),
        set_fn=set_hours_to_charge,
        native_step=1,
    ),
)


class EcoModeNumberEntity(CoordinatorEntity, NumberEntity):
    """Number entity for controlling eco mode settings."""

    _attr_has_entity_name = True
    state_val = None

    def __init__(
        self,
        connector_id: str,
        coordinator: CloudChargeEcoModeCoordinator,
        description: DefaPowerEcoModeNumberDescription,
        device: ConnectorDevice,
        client: CloudChargeAPIClient,
        instance_id: str,
    ) -> None:
        """Initialize the eco mode number entity."""
        super().__init__(coordinator, description.key)
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{instance_id}_{connector_id}_{description.key}"
        self._attr_translation_key = f"defa_power_{description.key}"
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_unit_of_measurement = description.native_unit_of_measurement
        self._attr_icon = description.icon

        if description.disabled_by_default:
            self._attr_entity_registry_enabled_default = False

        self.connector_id = connector_id
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

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        try:
            await self.entity_description.set_fn(
                self.connector_id, self.client, int(value)
            )
            await self.coordinator.async_request_refresh()
        except Exception as e:
            _LOGGER.error(
                "Failed to set hours to charge to %s for %s: %s",
                value,
                self.connector_id,
                str(e),
            )
            raise HomeAssistantError("Failed to set hours to charge") from e

    @property
    def state(self):
        """Return the state of the entity."""
        return self.state_val
