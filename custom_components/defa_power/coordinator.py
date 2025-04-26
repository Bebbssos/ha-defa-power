"""Define coordinators for CloudCharge API."""

import asyncio
from collections.abc import Callable
import copy
from datetime import timedelta
import logging

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cloudcharge_api.client import CloudChargeAPIClient
from .cloudcharge_api.exceptions import CloudChargeAPIError, CloudChargeAuthError
from .cloudcharge_api.models import EcoModeConfiguration, EcoModeConfigurationRequest

CONF_TOKEN = "token"
CONF_USER_ID = "userId"

_LOGGER = logging.getLogger(__name__)


class CloudChargeChargepointCoordinator(DataUpdateCoordinator):
    """CloudCharge chargers coordinator."""

    def __init__(
        self, chargepoint_id: str, hass: HomeAssistant, client: CloudChargeAPIClient
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="CloudCharge chargers",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(minutes=15),
            # Set always_update to `False` if the data returned from the
            # api can be compared via `__eq__` to avoid duplicate updates
            # being dispatched to listeners
            always_update=True,
        )
        self.chargepoint_id = chargepoint_id
        self.client = client

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        # try:
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with asyncio.timeout(10):
            # Grab active context variables to limit data required to be fetched from API
            # Note: using context is not required if there is no need or ability to limit
            # data retrieved from API.
            try:
                chargepoint = await self.client.async_get_chargepoint(
                    self.chargepoint_id
                )
            except CloudChargeAuthError as err:
                raise ConfigEntryAuthFailed from err
            except CloudChargeAPIError as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err

            connectors = {}

            for alias, connector in chargepoint["aliasMap"].items():
                connector["chargepoint_id"] = chargepoint["id"]
                connectors[alias] = connector

            return {"chargepoint": chargepoint, "connectors": connectors}


class CloudChargeOperationalDataCoordinator(DataUpdateCoordinator):
    """CloudCharge operational data coordinator."""

    def __init__(
        self, connector_id: str, hass: HomeAssistant, client: CloudChargeAPIClient
    ) -> None:
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
        self.connector_id = connector_id
        self.client = client
        self.is_charging = False

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        # try:
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with asyncio.timeout(10):
            # Grab active context variables to limit data required to be fetched from API
            # Note: using context is not required if there is no need or ability to limit
            # data retrieved from API.
            try:
                data = await self.client.async_get_operational_data(self.connector_id)
            except CloudChargeAuthError as err:
                raise ConfigEntryAuthFailed from err
            except CloudChargeAPIError as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err

            charging_state = data.get("ocpp", {}).get("chargingState")

            if charging_state:
                # Update every 10 seconds while charging, otherwise every minute
                if self.is_charging and charging_state != "Charging":
                    self.is_charging = False
                    self.update_interval = timedelta(seconds=60)
                elif not self.is_charging and charging_state == "Charging":
                    self.is_charging = True
                    self.update_interval = timedelta(seconds=10)
                    await self.client.async_start_live_consumption(self.connector_id)
            return data


class CloudChargeEcoModeCoordinator(DataUpdateCoordinator):
    """CloudCharge operational data coordinator."""

    def __init__(
        self, connector_id: str, hass: HomeAssistant, client: CloudChargeAPIClient
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="CloudCharge eco mode data",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(minutes=15),
            # Set always_update to `False` if the data returned from the
            # api can be compared via `__eq__` to avoid duplicate updates
            # being dispatched to listeners
            always_update=True,
        )
        self.connector_id = connector_id
        self.client = client

        self._modified_data = None
        self._has_changes = False
        self._is_saving = False
        self._save_task = None

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        # try:
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with asyncio.timeout(10):
            # Grab active context variables to limit data required to be fetched from API
            # Note: using context is not required if there is no need or ability to limit
            # data retrieved from API.
            try:
                return await self.client.async_get_eco_mode_configuration(
                    self.connector_id
                )
            except CloudChargeAuthError as err:
                raise ConfigEntryAuthFailed from err
            except CloudChargeAPIError as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err

    def get_data(self):
        """Get current eco mode config (modified or latest from API)."""
        return self._modified_data if self._modified_data is not None else self.data

    async def set_data(self, callback: Callable[[EcoModeConfiguration], None]):
        """Apply a modification callback to the config and trigger save."""
        if self._modified_data is not None:
            modified_data = self._modified_data
        else:
            modified_data = copy.deepcopy(self.data)

        callback(modified_data)

        self._modified_data = modified_data
        self._has_changes = True

        if self._save_task is None or self._save_task.done():
            self._save_task = asyncio.create_task(self._save_changes())

        await self._save_task

    async def _save_changes(self):
        """Attempt to save all pending changes, batching if necessary."""
        if self._is_saving:
            return

        self._is_saving = True
        try:
            while self._has_changes:
                # Coalesce rapid-fire changes
                while self._has_changes:
                    self._has_changes = False
                    request: EcoModeConfigurationRequest = {
                        "active": self._modified_data["active"],
                        "pickupTimeEnabled": self._modified_data["pickupTimeEnabled"],
                        "hoursToCharge": self._modified_data["hoursToCharge"],
                        "dayOfWeekMap": self._modified_data["dayOfWeekMap"],
                    }
                    _LOGGER.info("Saving eco mode config: %s", request)
                    try:
                        await self.client.async_set_eco_mode_configuration(
                            self.connector_id, request
                        )
                    except Exception as err:
                        _LOGGER.error("Failed to save eco mode config: %s", err)
                        self._modified_data = None
                        raise  # Exit immediately, don’t retry

                _LOGGER.info("Refreshing eco mode config")

                # One or more changes were saved — now sync from API
                await self.async_refresh()

            # Clear before refresh so UI doesn't keep showing old data
            self._modified_data = None
            self.async_update_listeners()

            _LOGGER.info("Eco mode config updated successfully")
        finally:
            self._is_saving = False
            self._save_task = None
