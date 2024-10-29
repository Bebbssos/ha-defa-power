"""DEFA Power sensor entities."""

from dataclasses import dataclass
from enum import Enum
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfElectricCurrent, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DefaPowerConfigEntry
from .devices import ChargerDevice, ConnectorDevice

_LOGGER = logging.getLogger(__name__)

CURRENCY_CODE_VALUES = [
    "CAD",
    "CHF",
    "CZK",
    "DKK",
    "EUR",
    "GBP",
    "HUF",
    "HRK",
    "ILS",
    "ISK",
    "MTL",
    "SKK",
    "NOK",
    "SIT",
    "PLN",
    "RON",
    "ROL",
    "SEK",
    "USD",
    "XOF",
]
CHARGING_STATE_VALUES = [
    "EVConnected",
    "Charging",
    "SuspendedEV",
    "SuspendedEVSE",
    "Idle",
    "UNRECOGNIZED",
]
STATUS_VALUES = [
    "AVAILABLE",
    "OCCUPIED",
    "PREPARING",
    "CHARGING",
    "SUSPENDED_EV",
    "SUSPENDED_EVSE",
    "FINISHING",
    "FAULTED",
    "UNAVAILABLE",
    "RESERVED",
    "RESTARTING",
    "FACILITY_FINISHING",
    "IDLE",
    "EV_CONNECTED",
]


class Coordinator(Enum):
    """Coordinator type."""

    CHARGERS = 1
    OPERATIONAL_DATA = 2


@dataclass(frozen=True, kw_only=True)
class DefaPowerSensorDescription(SensorEntityDescription):
    """Class to describe an DEFA Power sensor entity."""

    field_name: str
    round_digits: int | None = None
    disabled_by_default: bool = False
    options: list[str] | None = None


@dataclass(frozen=True, kw_only=True)
class DefaPowerConnectorSensorDescription(DefaPowerSensorDescription):
    """Class to describe an DEFA Power Connector sensor entity."""

    coordinator: Coordinator = Coordinator.CHARGERS


DEFA_POWER_CHARGER_SENSOR_TYPES: tuple[DefaPowerSensorDescription, ...] = (
    DefaPowerSensorDescription(
        key="currency_code",
        name="Currency code",
        icon="mdi:currency-usd",
        field_name="currencyCode",
        options=CURRENCY_CODE_VALUES,
        device_class=SensorDeviceClass.ENUM,
        disabled_by_default=True,
    ),
)

DEFA_POWER_CONNECTOR_SENSOR_TYPES: tuple[DefaPowerConnectorSensorDescription, ...] = (
    DefaPowerConnectorSensorDescription(
        key="meter_value",
        name="Meter value",
        icon="mdi:counter",
        field_name="meterValue",
        coordinator=Coordinator.OPERATIONAL_DATA,
        round_digits=3,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.ENERGY,
    ),
    DefaPowerConnectorSensorDescription(
        key="transaction_meter_value",
        name="Transaction meter value",
        icon="mdi:counter",
        field_name="transactionMeterValue",
        coordinator=Coordinator.OPERATIONAL_DATA,
        round_digits=3,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.ENERGY,
    ),
    DefaPowerConnectorSensorDescription(
        key="power_consumption",
        name="Power consumption",
        icon="mdi:lightning-bolt",
        field_name="powerConsumption",
        coordinator=Coordinator.OPERATIONAL_DATA,
        round_digits=3,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    DefaPowerConnectorSensorDescription(
        key="charging_state",
        name="Charging state",
        icon="mdi:battery-charging",
        field_name="chargingState",
        options=CHARGING_STATE_VALUES,
        coordinator=Coordinator.OPERATIONAL_DATA,
        device_class=SensorDeviceClass.ENUM,
    ),
    DefaPowerConnectorSensorDescription(
        key="status",
        name="Status",
        icon="mdi:ev-station",
        field_name="status",
        options=STATUS_VALUES,
        coordinator=Coordinator.OPERATIONAL_DATA,
        device_class=SensorDeviceClass.ENUM,
        disabled_by_default=True,
    ),
    DefaPowerConnectorSensorDescription(
        key="power",
        name="Power",
        icon="mdi:lightning-bolt",
        field_name="power",
        round_digits=2,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    DefaPowerConnectorSensorDescription(
        key="ampere",
        name="Ampere",
        icon="mdi:current-ac",
        field_name="ampere",
        round_digits=0,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    DefaPowerConnectorSensorDescription(
        key="firmware_version",
        name="Firmware version",
        icon="mdi:information-outline",
        field_name="firmwareVersion",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: DefaPowerConfigEntry, async_add_entities
):
    """Set up the sensor platform."""

    instance_id = entry.data.get("instance_id") or "default"
    entities: list[SensorEntity] = []

    for connector_id, val in entry.runtime_data["chargers"].items():
        entities.extend(
            DefaChargerEntity(
                connector_id,
                entry.runtime_data["chargers_coordinator"],
                sensorType,
                val["device"],
                instance_id,
            )
            for sensorType in DEFA_POWER_CHARGER_SENSOR_TYPES
        )

    for connector_id, val in entry.runtime_data["connectors"].items():
        for sensor_type in DEFA_POWER_CONNECTOR_SENSOR_TYPES:
            coordinator = entry.runtime_data["chargers_coordinator"]
            if sensor_type.coordinator == Coordinator.OPERATIONAL_DATA:
                coordinator = val["operational_data_coordinator"]

            entities.append(
                DefaConnectorEntity(
                    connector_id, coordinator, sensor_type, val["device"], instance_id
                )
            )

    async_add_entities(entities, update_before_add=True)


class DefaChargerEntity(CoordinatorEntity, SensorEntity):
    """Base class for DEFA Power entities."""

    state_val = None
    _attr_has_entity_name = True

    def __init__(
        self,
        id: str,
        coordinator,
        description: DefaPowerSensorDescription,
        device: ChargerDevice,
        instance_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, id)
        self.coordinator = coordinator
        self.entity_description = description
        # self._attr_name = f"{coordinator.name} {description.name}"
        self._attr_unique_id = f"{instance_id}_{id}_{description.key}"
        self._attr_translation_key = f"defa_power_{description.key}"
        if description.device_class is not None:
            self._attr_device_class = description.device_class
        if description.state_class is not None:
            self._attr_state_class = description.state_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_unit_of_measurement = description.native_unit_of_measurement
        self._attr_icon = description.icon

        if description.disabled_by_default:
            self._attr_entity_registry_enabled_default = False

        if description.round_digits is not None:
            self.attr_suggested_display_precision = description.round_digits

        self.id = id
        self._attr_device_info = device.get_device_info()
        self._set_state()

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    def _set_state(self):
        """Update the state from coordinator. Return True if the state has changed."""
        new_state = self.coordinator.data["chargers"][self.id][
            self.entity_description.field_name
        ]

        if new_state != self.state_val:
            self.state_val = new_state
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
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._attr_native_unit_of_measurement

    @property
    def options(self) -> list[str] | None:
        """Return the option of the sensor."""
        return self.entity_description.options


class DefaConnectorEntity(CoordinatorEntity, SensorEntity):
    """Base class for DEFA Power entities."""

    state_val = None
    _attr_has_entity_name = True

    def __init__(
        self,
        id: str,
        coordinator,
        description: DefaPowerConnectorSensorDescription,
        device: ConnectorDevice,
        instance_id: str,
    ) -> None:
        """Initialize the entity."""
        if description.coordinator == Coordinator.CHARGERS:
            self.id_lookup_required = True
            context = id
        else:
            self.id_lookup_required = False
            context = description.field_name

        super().__init__(coordinator, context)
        self.coordinator = coordinator
        self.entity_description = description
        # self._attr_name = f"{coordinator.name} {description.name}"
        self._attr_unique_id = f"{instance_id}_{id}_{description.key}"
        self._attr_translation_key = f"defa_power_{description.key}"
        if description.device_class is not None:
            self._attr_device_class = description.device_class
        if description.state_class is not None:
            self._attr_state_class = description.state_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_unit_of_measurement = description.native_unit_of_measurement
        self._attr_icon = description.icon

        if description.disabled_by_default:
            self._attr_entity_registry_enabled_default = False

        if description.round_digits is not None:
            self.attr_suggested_display_precision = description.round_digits

        self.id = id
        self._attr_device_info = device.get_device_info()
        self._set_state()

    @property
    def available(self):
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    def _set_state(self):
        """Update the state from coordinator. Return True if the state has changed."""
        if self.id_lookup_required:
            new_state = self.coordinator.data["connectors"][self.id][
                self.entity_description.field_name
            ]
        else:
            new_state = self.coordinator.data[self.entity_description.field_name]

        if new_state != self.state_val:
            self.state_val = new_state
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
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._attr_native_unit_of_measurement

    @property
    def options(self) -> list[str] | None:
        """Return the option of the sensor."""
        return self.entity_description.options
