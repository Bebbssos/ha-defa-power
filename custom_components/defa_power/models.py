"""Runtime data structure for the DEFA Power integration."""

from typing import TypedDict

from homeassistant.config_entries import ConfigEntry

from .cloudcharge_api.client import CloudChargeAPIClient
from .coordinator import (
    CloudChargeChargepointCoordinator,
    CloudChargeEcoModeCoordinator,
    CloudChargeOperationalDataCoordinator,
)
from .devices import ChargePointDevice, ConnectorDevice


class RuntimeDataChargePoint(TypedDict):
    """Runtime data for a charger."""

    device: ChargePointDevice
    coordinator: CloudChargeChargepointCoordinator


class RuntimeDataConnectorCapabilities(TypedDict):
    """Capabilities of a connector."""

    ecoMode: bool


class RuntimeDataConnector(TypedDict):
    """Runtime data for a connector."""

    device: ConnectorDevice
    alias: str
    operational_data_coordinator: CloudChargeOperationalDataCoordinator
    eco_mode_coordinator: CloudChargeEcoModeCoordinator
    capabilities: RuntimeDataConnectorCapabilities
    chargepoint_id: str


class RuntimeData(TypedDict):
    """Runtime data for DEFA Power."""

    chargepoints: dict[str, RuntimeDataChargePoint]
    connectors: dict[str, RuntimeDataConnector]

    client: CloudChargeAPIClient


type DefaPowerConfigEntry = ConfigEntry[RuntimeData]
