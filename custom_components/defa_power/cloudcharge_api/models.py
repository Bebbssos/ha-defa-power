"""Models for CloudCharger API."""

from typing import Any, TypedDict


class CloudChargeApiCredentials(TypedDict, total=True):
    """CloudCharge API credentials."""

    user_id: str
    token: str


# Charger types
class ConnectorProperties(TypedDict, total=False):
    """Connector properties."""

    biddingArea: str | None
    broadcast: Any | None
    privateCharging: Any | None
    privateChargingSettings: Any | None
    publicCharging: Any | None
    publicChargingSettings: Any | None
    subscriptionCostDestination: Any | None
    visibleInApps: Any | None


class DiscountTariff(TypedDict, total=False):
    """Discount tariff."""

    fixedCost: float
    hourDivisor: float
    pricePerHour: float
    pricePerKwh: float
    type: str


class Capabilities(TypedDict, total=False):
    """Capabilities."""

    ecoMode: bool
    solar: bool
    accessControl: bool
    loadBalancing: bool
    bluetoothNetworkSetup: bool


class Connector(TypedDict, total=False):
    """Connector."""

    accessControlEnabled: bool
    ampere: int
    availability: str
    capabilities: Capabilities
    connector: int
    connectorProperties: ConnectorProperties
    connectorType: str
    discountTariff: DiscountTariff
    displayName: str | None
    errorCode: str
    errorInfo: str
    firmwareVersion: str
    hbTimeout: bool
    id: str
    info: Any | None
    loadBalancingActive: bool
    maxProfileCurrent: int
    meterValue: float
    model: str
    nickname: str | None
    power: float
    serialNumber: str
    smsAlias: str
    status: str
    statusUpdated: int
    tariff: DiscountTariff
    vendor: str


class ChargePoint(TypedDict, total=False):
    """ChargePoint."""

    access: str
    aliasMap: dict[str, Connector]
    billingMethod: str
    chargeSystemId: str
    connectorProperties: Any | None
    currencyCode: str
    discount: Any | None
    displayName: str
    id: str
    isFacility: bool
    isFavorite: bool
    isReservedForYou: bool
    latitude: float
    location: str
    locationDescription: str
    longitude: float
    nickname: str | None
    postalArea: str
    zipcode: str


class PrivateChargePoint(TypedDict, total=False):
    """Private chargepoint."""

    access: str
    data: ChargePoint
    type: str
    validFrom: str | None
    validTo: str | None


# Addidional connector data types
class OCPPData(TypedDict, total=False):
    """OCPP data."""

    chargingState: str
    status: str
    version: str


class OperationalData(TypedDict, total=False):
    """Operational data."""

    id: str
    ocpp: OCPPData
    errorCode: str
    info: Any | None
    hbLastAlive: str
    hbTimeout: bool
    meterValue: float
    transactionMeterValue: float
    powerConsumption: float


class LoadBalancer(TypedDict, total=False):
    """Load balancer."""

    serialNumber: str
    brand: str
    available: bool
    enabled: bool
    active: bool


class Ethernet(TypedDict, total=False):
    """Ethernet configuration."""

    active: bool
    enabled: bool


class WiFi(TypedDict, total=False):
    """WiFi configuration."""

    active: bool
    enabled: bool
    SSID: str
    signalStrength: str


class Mobile(TypedDict, total=False):
    """Mobile configuration."""

    active: bool
    enabled: bool
    signalStrength: str


class NetworkConfiguration(TypedDict, total=False):
    """Network configuration."""

    connectionType: str
    ethernet: Ethernet
    wifi: WiFi
    mobile: Mobile
