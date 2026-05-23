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
    maxPower: bool
    manualSchedules: bool
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


# MyChargers types
class TokenInfo(TypedDict, total=False):
    """Token information for access."""

    status: str
    accessId: str
    chargePointId: Any
    connectorId: int
    endTime: str
    startTime: str
    role: str
    givingAccess: str
    receivingAccess: list[str]
    metaString: str


class ChargePointAccess(TypedDict, total=False):
    """Charge point access."""

    chargePoint: ChargePoint
    token: TokenInfo


class MyChargers(TypedDict, total=False):
    """My chargers response."""

    timestamp: str
    receivingAccess: list[ChargePointAccess]
    givingAccess: list[ChargePointAccess]


# Additional connector data types
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


class EcoModeConfigurationBase(TypedDict):
    """Base eco mode configuration fields."""

    active: bool
    dayOfWeekMap: dict[str, int | None]
    hoursToCharge: int
    pickupTimeEnabled: bool


class EcoModeConfigurationRequest(EcoModeConfigurationBase):
    """Eco mode configuration request payload."""


class EcoModeConfiguration(EcoModeConfigurationBase):
    """Eco mode configuration response."""

    percentageNotToCharge: int | None
    schedule: list[int]
    scheduleOverridden: bool


class ManualSchedule(TypedDict, total=False):
    """A single manual charge schedule."""

    id: int
    days: list[str]
    start: str
    stop: str
    enabled: bool
    priority: float


class ManualSchedules(TypedDict, total=False):
    """Response from the manual-schedules endpoint."""

    schedulingEnabled: bool
    scheduleOverridden: bool
    schedules: list[ManualSchedule]


class SchedulePeriod(TypedDict, total=False):
    """A single period within an active schedule."""

    startOfPeriod: int
    limit: float


class ActiveSchedule(TypedDict, total=False):
    """Schedule embedded in ActiveScheduleSettings."""

    type: str
    startOfSchedule: str
    schedulePeriods: list[SchedulePeriod]


class ActiveScheduleSettings(TypedDict, total=False):
    """Response from the schedule/active-settings and schedule/override endpoints."""

    active: list[str]
    capable: list[str]
    overrideSmartCharging: bool
    pausedBy: str | None
    pausedUntil: str | None
    schedule: ActiveSchedule
    startOfSession: int
    previousEcoModePickup: str | None
    quartersToCharge: list


class CarModel(TypedDict, total=False):
    """Car model within a user car."""

    name: str
    slug: str
    maxEffect: int
    connector: str
    batteryCapacity: int
    imageUrl: str
    fastChargeConnector: list[str]


class UserCar(TypedDict, total=False):
    """User car entry."""

    carId: str
    carModel: CarModel
    nickName: str | None
    carMake: str
    carType: str
    forceBusinessTrans: bool
    modelYear: Any | None


class UserProfile(TypedDict, total=False):
    """User profile response from /profile endpoint."""

    id: str
    phonenr: str
    groups: list[Any]  # internal structure unknown
    discounts: dict[str, Any]  # internal structure unknown
    rfidCards: list[Any]  # internal structure unknown
    sessionCounter: int
    totalTime: float
    energy: int
    faultCounter: int
    firstName: str
    lastName: str
    contactEmail: str
    invoiceEmail: str
    invoiceAddressStreet: str | None
    invoiceAddressZip: str | None
    invoiceAddressCountry: str | None
    invoiceAddressCity: str | None
    acceptedAgreement: bool
    classifyBusinessCardAsBusiness: Any | None
    lastDayOfMonthReceiptSummary: Any | None
    notificationStopCharge: bool
    notificationCancelCharge: bool
    notificationHomeChargerError: bool
    notificationHomeChargerUsed: bool
    notificationEcoMode: bool
    uiLanguage: str
    favorites: list[Any]  # internal structure unknown
    acceptedNewsletter: Any | None
    firebaseToken: str
    rfidCardMap: dict[str, Any]  # internal structure unknown
    stripeCardMap: dict[str, Any]  # internal structure unknown
    appSettings: dict[str, Any]
    userCarMap: dict[str, UserCar]
