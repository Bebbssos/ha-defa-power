"""Runtime data structure for the DEFA Power integration."""

from typing import TypedDict

from homeassistant.config_entries import ConfigEntry

from .cloudcharge_api.client import CloudChargeAPIClient
from .coordinator import (
    CloudChargeActiveScheduleCoordinator,
    CloudChargeChargepointCoordinator,
    CloudChargeEcoModeCoordinator,
    CloudChargeManualSchedulesCoordinator,
    CloudChargeOperationalDataCoordinator,
)
from .devices import ChargePointDevice, ConnectorDevice


class RuntimeDataChargePoint(TypedDict):
    """Runtime data for a charger."""

    device: ChargePointDevice
    coordinator: CloudChargeChargepointCoordinator
    skipped_entities: list[str]
    has_subentry: bool
    subentry_id: str | None


class RuntimeDataConnectorCapabilities(TypedDict):
    """Capabilities of a connector."""

    ecoMode: bool
    manualSchedules: bool


class RuntimeDataConnector(TypedDict):
    """Runtime data for a connector."""

    device: ConnectorDevice
    alias: str
    operational_data_coordinator: CloudChargeOperationalDataCoordinator
    eco_mode_coordinator: CloudChargeEcoModeCoordinator | None
    manual_schedules_coordinator: CloudChargeManualSchedulesCoordinator | None
    active_schedule_coordinator: CloudChargeActiveScheduleCoordinator | None
    capabilities: RuntimeDataConnectorCapabilities
    chargepoint_id: str
    skipped_entities: list[str]
    subentry_id: str | None
    connection_type: str


class RuntimeData(TypedDict):
    """Runtime data for DEFA Power."""

    chargepoints: dict[str, RuntimeDataChargePoint]
    connectors: dict[str, RuntimeDataConnector]

    client: CloudChargeAPIClient


type DefaPowerConfigEntry = ConfigEntry[RuntimeData]
