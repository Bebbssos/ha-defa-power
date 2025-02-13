from typing import TypedDict

from homeassistant.config_entries import ConfigEntry

from .cloudcharge_api.client import CloudChargeAPIClient
from .coordinator import (
    CloudChargeChargersCoordinator,
    CloudChargeOperationalDataCoordinator,
)
from .devices import ChargePointDevice, ConnectorDevice


class RuntimeDataChargePoint(TypedDict):
    """Runtime data for a charger."""

    device: ChargePointDevice


class RuntimeDataConnector(TypedDict):
    """Runtime data for a connector."""

    device: ConnectorDevice
    alias: str
    operational_data_coordinator: CloudChargeOperationalDataCoordinator


class RuntimeData(TypedDict):
    """Runtime data for DEFA Power."""

    chargers_coordinator: CloudChargeChargersCoordinator
    chargerPoints: dict[str, RuntimeDataChargePoint]
    connectors: dict[str, RuntimeDataConnector]

    client: CloudChargeAPIClient


type DefaPowerConfigEntry = ConfigEntry[RuntimeData]
