"""DEFA Power sensor entities."""

from collections.abc import Callable
from enum import Enum
import logging
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
    dataclass,
)
from homeassistant.const import UnitOfElectricCurrent, UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    CloudChargeChargersCoordinator,
    CloudChargeOperationalDataCoordinator,
)

_LOGGER = logging.getLogger(__name__)


class Coordinator(Enum):
    """Coordinator type."""

    CHARGERS = 1
    OPERATIONAL_DATA = 2


@dataclass
class DefaPowerSensorDescriptionMixin:
    """Define an entity description mixin for sensor entities."""

    field_name: str
    round_digits: int | None
    disabled_by_default: bool


@dataclass
class DefaPowerSensorDescriptionConnectorMixin:
    """Define an entity description mixin for sensor entities."""

    coordinator: Coordinator


@dataclass
class DefaPowerSensorDescription(
    SensorEntityDescription, DefaPowerSensorDescriptionMixin
):
    """Class to describe an DEFA Power sensor entity."""


@dataclass
class DefaPowerSensorConnectorDescription(
    DefaPowerSensorDescription, DefaPowerSensorDescriptionConnectorMixin
):
    """Class to describe a DEFA Power sensor entity."""


DEFA_POWER_CHARGER_SENSOR_TYPES: Final[tuple[DefaPowerSensorDescription, ...]] = (
    DefaPowerSensorDescription(
        key="currency_code",
        name="Currency code",
        icon="mdi:currency-usd",
        field_name="currencyCode",
        round_digits=None,
        native_unit_of_measurement=None,
        disabled_by_default=True,
    ),
)

DEFA_POWER_CONNECTOR_SENSOR_TYPES: Final[
    tuple[DefaPowerSensorConnectorDescription, ...]
] = (
    DefaPowerSensorConnectorDescription(
        key="meter_value",
        name="Meter value",
        icon="mdi:counter",
        field_name="meterValue",
        coordinator=Coordinator.OPERATIONAL_DATA,
        round_digits=3,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        disabled_by_default=False,
    ),
    DefaPowerSensorConnectorDescription(
        key="transaction_meter_value",
        name="Transaction meter value",
        icon="mdi:counter",
        field_name="transactionMeterValue",
        coordinator=Coordinator.OPERATIONAL_DATA,
        round_digits=3,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.ENERGY,
        disabled_by_default=False,
    ),
    DefaPowerSensorConnectorDescription(
        key="power_consumption",
        name="Power consumption",
        icon="mdi:lightning-bolt",
        field_name="powerConsumption",
        coordinator=Coordinator.OPERATIONAL_DATA,
        round_digits=3,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        disabled_by_default=False,
    ),
    DefaPowerSensorConnectorDescription(
        key="charging_state",
        name="Charging state",
        icon="mdi:battery-charging",
        field_name="chargingState",
        coordinator=Coordinator.OPERATIONAL_DATA,
        round_digits=None,
        native_unit_of_measurement=None,
        disabled_by_default=False,
    ),
    DefaPowerSensorConnectorDescription(
        key="status",
        name="Status",
        icon="mdi:ev-station",
        field_name="status",
        coordinator=Coordinator.OPERATIONAL_DATA,
        round_digits=None,
        native_unit_of_measurement=None,
        disabled_by_default=True,
    ),
    DefaPowerSensorConnectorDescription(
        key="power",
        name="Power",
        icon="mdi:lightning-bolt",
        field_name="power",
        coordinator=Coordinator.CHARGERS,
        round_digits=2,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
        disabled_by_default=False,
    ),
    DefaPowerSensorConnectorDescription(
        key="ampere",
        name="Ampere",
        icon="mdi:current-ac",
        field_name="ampere",
        coordinator=Coordinator.CHARGERS,
        round_digits=0,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        disabled_by_default=False,
    ),
    DefaPowerSensorConnectorDescription(
        key="firmware_version",
        name="Firmware version",
        icon="mdi:information-outline",
        field_name="firmwareVersion",
        coordinator=Coordinator.CHARGERS,
        round_digits=None,
        native_unit_of_measurement=None,
        disabled_by_default=False,
    ),
)


class ChargerDevice:
    """Representation of a DEFA Power charger device."""

    def __init__(self, data, instance_id):
        """Initialize the device."""
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, instance_id, data["id"])},
            name=data.get("displayName") or data["id"],
        )

    def get_device_info(self):
        """Return the device info."""
        return self._device_info


class ConnectorDevice:
    """Representation of a DEFA Power connector device."""

    def __init__(self, data, instance_id):
        """Initialize the device."""
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, instance_id, data["id"])},
            manufacturer=data["vendor"],
            model=data["model"],
            name=data.get("displayName") or data.get("smsAlias") or data["id"],
            sw_version=data["firmwareVersion"],
            serial_number=data["serialNumber"],
            via_device=(DOMAIN, instance_id, data["chargerId"]),
        )

    def get_device_info(self):
        """Return the device info."""
        return self._device_info


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""

    instance_id = config.get("instance_id") or "default"
    chargersCoordinator = CloudChargeChargersCoordinator(hass, config)
    await chargersCoordinator.async_config_entry_first_refresh()
    entities = []

    for connectorId, val in chargersCoordinator.data["chargers"].items():
        device = ChargerDevice(val, instance_id)
        entities.extend(
            DefaChargerEntity(
                connectorId, chargersCoordinator, sensorType, device, instance_id
            )
            for sensorType in DEFA_POWER_CHARGER_SENSOR_TYPES
        )

    for connectorId, val in chargersCoordinator.data["connectors"].items():
        operational_data_coordinator = CloudChargeOperationalDataCoordinator(
            connectorId, hass, config
        )
        await operational_data_coordinator.async_config_entry_first_refresh()
        device = ConnectorDevice(val, instance_id)

        for sensorType in DEFA_POWER_CONNECTOR_SENSOR_TYPES:
            if sensorType.coordinator == Coordinator.CHARGERS:
                coordinator = chargersCoordinator
            elif sensorType.coordinator == Coordinator.OPERATIONAL_DATA:
                coordinator = operational_data_coordinator

            entities.append(
                DefaConnectorEntity(
                    connectorId, coordinator, sensorType, device, instance_id
                )
            )

    async_add_entities(entities, update_before_add=True)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensor platform from a config entry."""
    await async_setup_platform(hass, entry.data, async_add_entities)


class DefaChargerEntity(CoordinatorEntity):
    """Base class for DEFA Power entities."""

    def __init__(
        self,
        id: str,
        coordinator,
        description: DefaPowerSensorDescription,
        device: ChargerDevice,
        instance_id: str,
    ):
        """Initialize the entity."""
        super().__init__(coordinator, id)
        self.coordinator = coordinator
        self.entity_description = description
        # self._attr_name = f"{coordinator.name} {description.name}"
        self._attr_unique_id = f"{instance_id}_{id}_{description.key}"
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
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
        self.state_val = self.coordinator.data["chargers"][self.id][
            self.entity_description.field_name
        ]

    @callback
    def _handle_coordinator_update(self) -> None:
        self._set_state()
        self.async_write_ha_state()

    @property
    def state(self):
        """Return the state of the entity."""
        return self.state_val

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._attr_native_unit_of_measurement


class DefaConnectorEntity(CoordinatorEntity):
    """Base class for DEFA Power entities."""

    def __init__(
        self,
        id: str,
        coordinator,
        description: DefaPowerSensorConnectorDescription,
        device: ConnectorDevice,
        instance_id: str,
    ):
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
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
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
        if self.id_lookup_required:
            self.state_val = self.coordinator.data["connectors"][self.id][
                self.entity_description.field_name
            ]
        else:
            self.state_val = self.coordinator.data[self.entity_description.field_name]

    @callback
    def _handle_coordinator_update(self) -> None:
        self._set_state()
        self.async_write_ha_state()

    @property
    def state(self):
        """Return the state of the entity."""
        return self.state_val

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._attr_native_unit_of_measurement
