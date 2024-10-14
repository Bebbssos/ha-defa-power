from datetime import timedelta
from enum import Enum
import logging
from typing import Callable, Final

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
    dataclass,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PATH,
    UnitOfElectricCurrent,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    CloudChargeChargersCoordinator,
    CloudChargeOperationalDataCoordinator,
)

_LOGGER = logging.getLogger(__name__)
# Time between updating data
SCAN_INTERVAL = timedelta(seconds=15)

CONF_TOKEN = "token"
CONF_USER_ID = "userId"

REPO_SCHEMA = vol.Schema(
    {vol.Required(CONF_PATH): cv.string, vol.Optional(CONF_NAME): cv.string}
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_TOKEN): cv.string,
        vol.Required(CONF_USER_ID): cv.string,
    }
)


class Coordinator(Enum):
    """Coordinator type."""

    CHARGERS = 1
    OPERATIONAL_DATA = 2


@dataclass
class DefaPowerSensorDescriptionMixin:
    """Define an entity description mixin for sensor entities."""

    field_name: str


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
    """Class to describe an DEFA Power sensor entity."""


DEFA_POWER_CHARGER_SENSOR_TYPES: Final[tuple[DefaPowerSensorDescription, ...]] = (
    DefaPowerSensorDescription(
        key="currency_code",
        name="Currency code",
        icon="mdi:currency-usd",
        field_name="currencyCode",
        native_unit_of_measurement=None,
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
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY,
    ),
    DefaPowerSensorConnectorDescription(
        key="transaction_meter_value",
        name="Transaction meter value",
        icon="mdi:counter",
        field_name="transactionMeterValue",
        coordinator=Coordinator.OPERATIONAL_DATA,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.ENERGY,
    ),
    DefaPowerSensorConnectorDescription(
        key="power_consumption",
        name="Power consumption",
        icon="mdi:lightning-bolt",
        field_name="powerConsumption",
        coordinator=Coordinator.OPERATIONAL_DATA,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    DefaPowerSensorConnectorDescription(
        key="charging_state",
        name="Charging state",
        icon="mdi:battery-charging",
        field_name="chargingState",
        coordinator=Coordinator.OPERATIONAL_DATA,
        native_unit_of_measurement=None,
    ),
    DefaPowerSensorConnectorDescription(
        key="status",
        name="Status",
        icon="mdi:ev-station",
        field_name="status",
        coordinator=Coordinator.OPERATIONAL_DATA,
        native_unit_of_measurement=None,
    ),
    DefaPowerSensorConnectorDescription(
        key="power",
        name="Power",
        icon="mdi:lightning-bolt",
        field_name="power",
        coordinator=Coordinator.CHARGERS,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    DefaPowerSensorConnectorDescription(
        key="ampere",
        name="Ampere",
        icon="mdi:current-ac",
        field_name="ampere",
        coordinator=Coordinator.CHARGERS,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
)


class ChargerDevice:
    def __init__(self, data):
        """Initialize the device."""
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, data["id"])},
            name=data.get("displayName") or data["id"],
        )

    def get_device_info(self):
        """Return the device info."""
        return self._device_info


class ConnectorDevice:
    def __init__(self, data):
        """Initialize the device."""
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, data["id"])},
            manufacturer=data["vendor"],
            model=data["model"],
            name=data.get("displayName") or data.get("smsAlias") or data["id"],
            sw_version=data["firmwareVersion"],
            serial_number=data["serialNumber"],
            via_device=(DOMAIN, data["chargerId"]),
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

    chargersCoordinator = CloudChargeChargersCoordinator(hass, config)
    await chargersCoordinator.async_config_entry_first_refresh()
    entities = []

    # for charger_data in coordinator.data:
    #     charger = Charger(charger_data["data"])
    #     charger_entity = DefaPowerChargerSensor(charger)
    #     entities.append(charger_entity)
    #     for connector in charger["aliasMap"].values():
    #         connector_entity = DefaPowerChargerConnectorSensor(
    #             connector, charger_entity
    #         )
    #         entities.append(connector_entity)
    for connectorId, val in chargersCoordinator.data["chargers"].items():
        device = ChargerDevice(val)
        entities.extend(
            DefaChargerEntity(connectorId, chargersCoordinator, sensorType, device)
            for sensorType in DEFA_POWER_CHARGER_SENSOR_TYPES
        )

    for connectorId, val in chargersCoordinator.data["connectors"].items():
        operational_data_coordinator = CloudChargeOperationalDataCoordinator(
            connectorId, hass, config
        )
        await operational_data_coordinator.async_config_entry_first_refresh()
        device = ConnectorDevice(val)

        for sensorType in DEFA_POWER_CONNECTOR_SENSOR_TYPES:
            if sensorType.coordinator == Coordinator.CHARGERS:
                coordinator = chargersCoordinator
            elif sensorType.coordinator == Coordinator.OPERATIONAL_DATA:
                coordinator = operational_data_coordinator

            entities.append(
                DefaConnectorEntity(connectorId, coordinator, sensorType, device)
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
    ):
        """Initialize the entity."""
        super().__init__(coordinator, id)
        self.coordinator = coordinator
        self.entity_description = description
        # self._attr_name = f"{coordinator.name} {description.name}"
        self._attr_unique_id = f"{id}_{description.key}"
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_icon = description.icon
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
        self._attr_unique_id = f"{id}_{description.key}"
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_icon = description.icon
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
