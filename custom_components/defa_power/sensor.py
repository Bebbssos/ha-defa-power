"""DEFA Power sensor entities."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any, Generic, TypeVar

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DefaPowerConfigEntry
from .cloudcharge_api.models import ChargePoint, Connector, OperationalData
from .devices import ChargePointDevice, ConnectorDevice

_LOGGER = logging.getLogger(__name__)

CURRENCY_CODE_VALUES = [
    "cad",
    "chf",
    "czk",
    "dkk",
    "eur",
    "gbp",
    "huf",
    "hrk",
    "ils",
    "isk",
    "mtl",
    "skk",
    "nok",
    "sit",
    "pln",
    "ron",
    "rol",
    "sek",
    "usd",
    "xof",
]

CHARGING_STATE_MAP = {
    "EVConnected": "ev_connected",
    "Charging": "charging",
    "SuspendedEV": "suspended_ev",
    "SuspendedEVSE": "suspended_evse",
    "Idle": "idle",
    "UNRECOGNIZED": "unrecognized",
}
CHARGING_STATE_VALUES = list(CHARGING_STATE_MAP.values())

STATUS_VALUES = [
    "available",
    "occupied",
    "preparing",
    "charging",
    "suspended_ev",
    "suspended_evse",
    "finishing",
    "faulted",
    "unavailable",
    "reserved",
    "restarting",
    "facility_finishing",
    "idle",
    "ev_connected",
]


class Coordinator(Enum):
    """Coordinator type."""

    CHARGERS = 1
    OPERATIONAL_DATA = 2


T = TypeVar("T")


def to_lower_case_or_none(value: str | None) -> str | None:
    """Convert a string to lowercase or return None."""
    return value.lower() if value else None


@dataclass(frozen=True, kw_only=True)
class DefaPowerSensorDescription(Generic[T], SensorEntityDescription):
    """Class to describe an DEFA Power sensor entity."""

    round_digits: int | None = None
    disabled_by_default: bool = False
    options: list[str] | None = None
    value_fn: Callable[[T], Any] | None = None


@dataclass(frozen=True, kw_only=True)
class DefaPowerConnectorSensorDescription(DefaPowerSensorDescription[T]):
    """Class to describe an DEFA Power Connector sensor entity."""

    coordinator: Coordinator = Coordinator.CHARGERS


DEFA_POWER_CHARGEPOINT_SENSOR_TYPES: tuple[DefaPowerSensorDescription, ...] = (
    DefaPowerSensorDescription[ChargePoint](
        key="currency_code",
        icon="mdi:currency-usd",
        options=CURRENCY_CODE_VALUES,
        device_class=SensorDeviceClass.ENUM,
        disabled_by_default=True,
        value_fn=lambda data: to_lower_case_or_none(data.get("currencyCode")),
    ),
)


def get_charging_state(data):
    """Get the charging state from the data."""
    ocpp = data.get("ocpp")
    if ocpp is None:
        return None

    state = ocpp.get("chargingState")
    return CHARGING_STATE_MAP.get(state, state.lower() if state else None)


DEFA_POWER_CONNECTOR_SENSOR_TYPES: tuple[DefaPowerConnectorSensorDescription, ...] = (
    DefaPowerConnectorSensorDescription[OperationalData](
        key="meter_value",
        icon="mdi:counter",
        coordinator=Coordinator.OPERATIONAL_DATA,
        round_digits=3,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda data: data.get("meterValue"),
    ),
    DefaPowerConnectorSensorDescription[OperationalData](
        key="transaction_meter_value",
        icon="mdi:counter",
        coordinator=Coordinator.OPERATIONAL_DATA,
        round_digits=3,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        value_fn=lambda data: data.get("transactionMeterValue"),
    ),
    DefaPowerConnectorSensorDescription[OperationalData](
        key="power_consumption",
        icon="mdi:lightning-bolt",
        coordinator=Coordinator.OPERATIONAL_DATA,
        round_digits=3,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda data: data.get("powerConsumption"),
    ),
    DefaPowerConnectorSensorDescription[OperationalData](
        key="charging_state",
        icon="mdi:battery-charging",
        options=CHARGING_STATE_VALUES,
        coordinator=Coordinator.OPERATIONAL_DATA,
        device_class=SensorDeviceClass.ENUM,
        value_fn=get_charging_state,
    ),
    DefaPowerConnectorSensorDescription[OperationalData](
        key="status",
        icon="mdi:ev-station",
        options=STATUS_VALUES,
        coordinator=Coordinator.OPERATIONAL_DATA,
        device_class=SensorDeviceClass.ENUM,
        disabled_by_default=True,
        value_fn=lambda data: to_lower_case_or_none(data.get("ocpp", {}).get("status")),
    ),
    DefaPowerConnectorSensorDescription[Connector](
        key="power",
        icon="mdi:lightning-bolt",
        round_digits=2,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        value_fn=lambda data: data.get("power"),
    ),
    DefaPowerConnectorSensorDescription[Connector](
        key="firmware_version",
        icon="mdi:information-outline",
        value_fn=lambda data: data.get("firmwareVersion"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: DefaPowerConfigEntry, async_add_entities
):
    """Set up the sensor platform."""

    instance_id = entry.data.get("instance_id") or "default"
    entities: list[SensorEntity] = []

    for chargepoint_id, val in entry.runtime_data["chargepoints"].items():
        entities.extend(
            DefaChargePointEntity(
                chargepoint_id,
                val["coordinator"],
                sensorType,
                val["device"],
                instance_id,
            )
            for sensorType in DEFA_POWER_CHARGEPOINT_SENSOR_TYPES
        )

    for connector_id, val in entry.runtime_data["connectors"].items():
        for sensor_type in DEFA_POWER_CONNECTOR_SENSOR_TYPES:
            if sensor_type.coordinator == Coordinator.OPERATIONAL_DATA:
                coordinator = val["operational_data_coordinator"]
            else:
                chargepoint_id = val["chargepoint_id"]
                chargepoint_data = entry.runtime_data["chargepoints"][chargepoint_id]
                coordinator = chargepoint_data["coordinator"]

            entities.append(
                DefaConnectorEntity(
                    connector_id,
                    val["alias"],
                    coordinator,
                    sensor_type,
                    val["device"],
                    instance_id,
                )
            )

    async_add_entities(entities, update_before_add=True)


class DefaChargePointEntity(CoordinatorEntity, SensorEntity):
    """Base class for DEFA Power entities."""

    state_val = None
    _attr_has_entity_name = True

    def __init__(
        self,
        id: str,
        coordinator,
        description: DefaPowerSensorDescription,
        device: ChargePointDevice,
        instance_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, id)
        self.coordinator = coordinator
        self.entity_description = description
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
            self._attr_suggested_display_precision = description.round_digits

        self.id = id
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
            self.coordinator.data["chargepoint"]
        )

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
        alias: str,
        coordinator,
        description: DefaPowerConnectorSensorDescription,
        device: ConnectorDevice,
        instance_id: str,
    ) -> None:
        """Initialize the entity."""
        if description.coordinator == Coordinator.CHARGERS:
            self.id_lookup_required = True
            context = alias
        else:
            self.id_lookup_required = False
            context = description.key

        super().__init__(coordinator, context)
        self.coordinator = coordinator
        self.entity_description = description
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
            self._attr_suggested_display_precision = description.round_digits

        self.id = id
        self.alias = alias
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

        if self.id_lookup_required:
            new_state = self.entity_description.value_fn(
                self.coordinator.data["connectors"][self.alias]
            )
        else:
            new_state = self.entity_description.value_fn(self.coordinator.data)

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
