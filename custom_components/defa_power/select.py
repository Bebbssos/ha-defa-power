"""Select entities for the DEFA Power integration."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DefaPowerConfigEntry
from .cloudcharge_api.client import CloudChargeAPIClient
from .cloudcharge_api.models import EcoModeConfiguration, EcoModeConfigurationRequest
from .coordinator import CloudChargeEcoModeCoordinator
from .devices import ConnectorDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: DefaPowerConfigEntry, async_add_entities
):
    """Set up the sensor platform."""

    instance_id = entry.data.get("instance_id") or "default"
    entities: list[SelectEntity] = []

    for connector_id, val in entry.runtime_data["connectors"].items():
        eco_mode_coordinator = val["eco_mode_coordinator"]
        # entities.extend(
        #     ChargeStartStopButton(
        #         connector_id,
        #         val["alias"],
        #         sensorType,
        #         val["device"],
        #         entry.runtime_data["client"],
        #         instance_id,
        #         operational_data_coordinator,
        #     )
        #     for sensorType in DEFA_POWER_CONNECTOR_SENSOR_TYPES
        # )
        # entities.append(
        #     ChargerRestartButton(
        #         connector_id, val["device"], entry.runtime_data["client"], instance_id
        #     )
        # )
        entities.extend(
            EcoModeWeekDayScheduleSelect(
                connector_id,
                eco_mode_coordinator,
                val["device"],
                entry.runtime_data["client"],
                instance_id,
                weekday,
            )
            for weekday in [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ]
        )

    async_add_entities(entities, update_before_add=True)


class EcoModeWeekDayScheduleSelect(CoordinatorEntity, SelectEntity):
    """Select entity for selecting the eco mode schedule for a weekday."""

    _attr_has_entity_name = True

    def __init__(
        self,
        connector_id: str,
        coordinator: CloudChargeEcoModeCoordinator,
        device: ConnectorDevice,
        client: CloudChargeAPIClient,
        instance_id: str,
        weekday: str,
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator, weekday)
        self.client = client
        self.connector_id = connector_id

        self._attr_unique_id = (
            f"{instance_id}_{connector_id}eco_mode_schedule_{weekday}"
        )
        self._attr_translation_key = f"defa_power_eco_mode_schedule_{weekday}"
        self._attr_icon = "mdi:calendar-clock"

        self._weekday_upper = weekday.upper()
        self._attr_device_info = device.get_device_info()
        self.state_val = None
        self._set_state()

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    def _set_state(self):
        """Update the state from coordinator. Return True if the state has changed."""
        if self.coordinator.data is None:
            return False

        new_state = self.coordinator.data.get("dayOfWeekMap", {}).get(
            self._weekday_upper
        )

        if new_state is None:
            mapped_state = "disabled"
        else:
            mapped_state = str(new_state)

        if mapped_state != self.state_val:
            self.state_val = mapped_state
            return True

        return False

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._set_state():
            self.async_write_ha_state()

    @property
    def state(self):
        """Return the state of the entity."""
        return self.state_val

    @property
    def options(self) -> list[str] | None:
        """Return the option of the sensor."""
        return [
            "disabled",
            "0",
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "11",
            "12",
            "13",
            "14",
            "15",
            "16",
            "17",
            "18",
            "19",
            "20",
            "21",
            "22",
            "23",
        ]

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option == "disabled":
            new_state = None
        else:
            new_state = int(option)

        current_data: EcoModeConfiguration = self.coordinator.data

        request: EcoModeConfigurationRequest = {
            "active": current_data["active"],
            "hoursToCharge": current_data["hoursToCharge"],
            "pickupTimeEnabled": current_data["pickupTimeEnabled"],
            "dayOfWeekMap": {
                **current_data["dayOfWeekMap"],
                self._weekday_upper: new_state,
            },
        }

        await self.client.async_set_eco_mode_configuration(self.connector_id, request)
        await self.coordinator.async_request_refresh()
