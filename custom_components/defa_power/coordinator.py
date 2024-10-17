"""Define coordinators for CloudCharge API."""

import asyncio
from datetime import timedelta
import logging

from .models import Charger
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_component import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_BASE_URL

CONF_TOKEN = "token"
CONF_USER_ID = "userId"

_LOGGER = logging.getLogger(__name__)


class CloudChargeChargersCoordinator(DataUpdateCoordinator):
    """CloudCharge chargers coordinator."""

    def __init__(self, hass, config: ConfigType):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="CloudCharge chargers",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(minutes=60),
            # Set always_update to `False` if the data returned from the
            # api can be compared via `__eq__` to avoid duplicate updates
            # being dispatched to listeners
            always_update=True,
        )
        self.config = config

    async def _async_setup(self):
        """Set up the coordinator."""
        self.session = async_get_clientsession(self.hass)
        self.headers = {
            "x-authorization": self.config[CONF_TOKEN],
            "x-user": self.config[CONF_USER_ID],
        }

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        # try:
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with asyncio.timeout(10):
            # Grab active context variables to limit data required to be fetched from API
            # Note: using context is not required if there is no need or ability to limit
            # data retrieved from API.
            response = await self.session.get(
                f"{API_BASE_URL}/chargers/private", headers=self.headers
            )

            if response.status == 401:
                raise ConfigEntryAuthFailed

            if response.status != 200:
                raise UpdateFailed(f"Error communicating with API: {response.status}")

            chargers_data: list[Charger] = await response.json()

            chargers = {}
            connectors = {}

            for charger_data in chargers_data:
                charger = charger_data["data"]
                chargers[charger["id"]] = charger
                for connector in charger["aliasMap"].values():
                    connector["chargerId"] = charger["id"]
                    connectors[connector["id"]] = connector

            return {"chargers": chargers, "connectors": connectors}

        #     except ApiAuthError as err:
        #     # Raising ConfigEntryAuthFailed will cancel future updates
        #     # and start a config flow with SOURCE_REAUTH (async_step_reauth)
        #     raise ConfigEntryAuthFailed from err
        # except ApiError as err:
        #     raise UpdateFailed(f"Error communicating with API: {err}")


class CloudChargeOperationalDataCoordinator(DataUpdateCoordinator):
    """CloudCharge operational data coordinator."""

    def __init__(self, connectorId: str, hass, config: ConfigType):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="CloudCharge operational data",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=60),
            # Set always_update to `False` if the data returned from the
            # api can be compared via `__eq__` to avoid duplicate updates
            # being dispatched to listeners
            always_update=True,
        )
        self.connectorId = connectorId
        self.config = config
        self.is_charging = False

    async def _async_setup(self):
        """Set up the coordinator."""
        self.session = async_get_clientsession(self.hass)
        self.headers = {
            "x-authorization": self.config[CONF_TOKEN],
            "x-user": self.config[CONF_USER_ID],
        }

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        # try:
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with asyncio.timeout(10):
            # Grab active context variables to limit data required to be fetched from API
            # Note: using context is not required if there is no need or ability to limit
            # data retrieved from API.
            response = await self.session.get(
                f"{API_BASE_URL}/connector/{self.connectorId}/operationaldata",
                headers=self.headers,
            )

            if response.status == 401:
                raise ConfigEntryAuthFailed

            if response.status != 200:
                raise UpdateFailed(f"Error communicating with API: {response.status}")

            data = await response.json()

            data["chargingState"] = data["ocpp"]["chargingState"]
            data["status"] = data["ocpp"]["status"]
            del data["ocpp"]

            # Update every 10 seconds while charging, otherwise every minute
            if self.is_charging and data["chargingState"] != "Charging":
                self.is_charging = False
                self.update_interval = timedelta(seconds=60)
            elif not self.is_charging and data["chargingState"] == "Charging":
                self.is_charging = True
                self.update_interval = timedelta(seconds=10)
                await self.session.post(
                    f"{API_BASE_URL}/connector/{self.connectorId}/startliveconsumption",
                    headers=self.headers,
                )
            return data

        #     except ApiAuthError as err:
        #     # Raising ConfigEntryAuthFailed will cancel future updates
        #     # and start a config flow with SOURCE_REAUTH (async_step_reauth)
        #     raise ConfigEntryAuthFailed from err
        # except ApiError as err:
        #     raise UpdateFailed(f"Error communicating with API: {err}")
