"""Runtime data structure for the DEFA Power integration."""

from typing import TypedDict

from homeassistant.config_entries import ConfigEntry

from .balancer.listener import BalancerListener
from .cloudcharge_api.client import CloudChargeAPIClient
from .const import CONF_ENTRY_TYPE, ENTRY_TYPE_BALANCER
from .coordinator import (
    BalancerCoordinator,
    CloudChargeActiveScheduleCoordinator,
    CloudChargeChargepointCoordinator,
    CloudChargeEcoModeCoordinator,
    CloudChargeManualSchedulesCoordinator,
    CloudChargeOperationalDataCoordinator,
)
from .devices import BalancerDevice, ChargePointDevice, ConnectorDevice


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


class RuntimeDataBalancer(TypedDict):
    """Runtime data for a balancer."""

    device: BalancerDevice
    coordinator: BalancerCoordinator
    subentry_id: str


class BalancerRuntimeData(TypedDict):
    """Runtime data for a balancer entry (one listening interface)."""

    listener: BalancerListener
    balancers: dict[str, RuntimeDataBalancer]


type DefaPowerConfigEntry = ConfigEntry[RuntimeData]
type DefaPowerBalancerConfigEntry = ConfigEntry[BalancerRuntimeData]


def is_balancer_entry(entry: ConfigEntry) -> bool:
    """Return whether the entry listens for balancers instead of using CloudCharge."""
    return entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_BALANCER


def balancer_entry_title(interface: str) -> str:
    """Return the default title of a balancer entry listening on an interface."""
    return f"DEFA Balancer ({interface})"
