from typing import Any, TypedDict


class ConnectorProperties(TypedDict, total=False):
    biddingArea: str | None
    broadcast: Any | None
    privateCharging: Any | None
    privateChargingSettings: Any | None
    publicCharging: Any | None
    publicChargingSettings: Any | None
    subscriptionCostDestination: Any | None
    visibleInApps: Any | None


class DiscountTariff(TypedDict, total=False):
    fixedCost: float
    hourDivisor: float
    pricePerHour: float
    pricePerKwh: float
    type: str


class Connector(TypedDict, total=False):
    accessControlEnabled: bool
    ampere: int
    availability: str
    capabilities: dict[str, bool]
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


class Charger(TypedDict, total=False):
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
