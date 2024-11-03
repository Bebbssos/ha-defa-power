"""CloudCharge API client."""

import aiohttp

from .exceptions import (
    CloudChargeAuthError,
    CloudChargeBadRequestError,
    CloudChargeForbiddenError,
    CloudChargeNotLoggedInError,
    CloudChargeRequestError,
)
from .models import (
    CloudChargeApiCredentials,
    LoadBalancer,
    NetworkConfiguration,
    OperationalData,
    PrivateChargePoint,
    ChargePoint,
)


# Swagger file for api can be found at https://prod.cloudcharge.se/services/user/swagger.json
class CloudChargeAPIClient:
    """CloudCharge API client."""

    __logged_in = False

    def __init__(self, base_url: str) -> None:
        """Initialize the client."""
        self.__base_url = base_url
        self.__headers = {}

    async def async_login_with_token(self, user_id: str, token: str):
        """Login with token and test."""
        headers = self.__build_auth_headers(user_id, token)

        async with (
            aiohttp.ClientSession() as session,
            session.get(f"{self.__base_url}/profile", headers=headers) as response,
        ):
            await self.__async_check_response(response)

        self.__headers = headers
        self.__logged_in = True

    def set_login(self, user_id: str, token: str):
        """Set login details without testing."""
        self.__headers = self.__build_auth_headers(user_id, token)
        self.__logged_in = True

    async def async_send_sms_code(
        self, phone_number: str, dev_token: str | None = None
    ):
        """Send SMS code to phone number."""
        payload = {"phoneNr": phone_number}
        if dev_token:
            payload["devToken"] = dev_token

        async with (
            aiohttp.ClientSession() as session,
            session.post(f"{self.__base_url}/prelogin", json=payload) as response,
        ):
            await self.__async_check_response(response)

    async def async_login_with_phone_number(
        self,
        phone_number: str,
        code: str,
        dev_token: str | None = None,
    ):
        """Login with phone number and code."""
        payload = {"phoneNr": phone_number, "password": code}
        if dev_token:
            payload["devToken"] = dev_token

        async with (
            aiohttp.ClientSession() as session,
            session.post(f"{self.__base_url}/login", json=payload) as response,
        ):
            await self.__async_check_response(response)
            data = await response.json()

            self.__headers = self.__build_auth_headers(
                data.get("id"), data.get("token")
            )
            self.__logged_in = True

    def forget_login(self):
        """Forget login details. Does not send logout request."""
        self.__logged_in = False
        self.__headers = {}

    async def async_logout(self):
        """Logout."""
        self.__check_logged_in()

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.__base_url}/logout", headers=self.__headers
            ) as response,
        ):
            await self.__async_check_response(response)

        self.forget_login()

    def is_logged_in(self):
        """Check if logged in."""
        return self.__logged_in

    def __check_logged_in(self):
        """Raise exception if not logged in."""
        if not self.is_logged_in():
            raise CloudChargeNotLoggedInError

    async def __async_check_response(self, response: aiohttp.ClientResponse):
        """Check response for errors."""
        if response.status == 401:
            raise CloudChargeAuthError

        if response.status == 400:
            try:
                message = await response.text()
            except:  # noqa: E722
                message = ""

            raise CloudChargeBadRequestError(message)

        if response.status == 403:
            try:
                message = await response.text()
            except:  # noqa: E722
                message = ""

            raise CloudChargeForbiddenError(message)

        if not response.ok:
            raise CloudChargeRequestError

    async def async_get_private_chargepoints(self) -> list[PrivateChargePoint]:
        """Get private chargepoints. Login required."""
        self.__check_logged_in()

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{self.__base_url}/chargers/private", headers=self.__headers
            ) as response,
        ):
            await self.__async_check_response(response)
            return await response.json()

    async def async_get_chargepoint(self, chargepoint_id: str) -> ChargePoint:
        """Get chargepoint. Login required."""
        self.__check_logged_in()

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.__base_url}/chargepoints/get", headers=self.__headers, json={"token": chargepoint_id}
            ) as response,
        ):
            await self.__async_check_response(response)
            return await response.json()

    async def async_get_operational_data(self, connector_id: str) -> OperationalData:
        """Get operational data. Login required."""
        self.__check_logged_in()

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{self.__base_url}/connector/{connector_id}/operationaldata",
                headers=self.__headers,
            ) as response,
        ):
            await self.__async_check_response(response)
            return await response.json()

    async def async_get_load_balancer(self, connector_id: str) -> LoadBalancer:
        """Get load balancer data. Login required."""
        self.__check_logged_in()

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{self.__base_url}/connector/{connector_id}/loadBalancer",
                headers=self.__headers,
            ) as response,
        ):
            await self.__async_check_response(response)
            return await response.json()

    async def async_get_network_configuration(
        self, connector_id: str
    ) -> NetworkConfiguration:
        """Get network configuration. Login required."""
        self.__check_logged_in()

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{self.__base_url}/connector/{connector_id}/networkconfiguration",
                headers=self.__headers,
            ) as response,
        ):
            await self.__async_check_response(response)
            return await response.json()

    async def async_start_live_consumption(self, connector_id: str):
        """Start live consumption. Login required."""
        self.__check_logged_in()

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.__base_url}/connector/{connector_id}/startliveconsumption",
                headers=self.__headers,
            ) as response,
        ):
            await self.__async_check_response(response)

    async def async_get_max_current_alternatives(
        self, connector_id: str
    ) -> dict[str, float]:
        """Get max current alternatives (dict[current, charging power]). Login required."""
        self.__check_logged_in()

        async with (
            aiohttp.ClientSession() as session,
            session.get(
                f"{self.__base_url}/connector/{connector_id}/maxcurrent/alternatives",
                headers=self.__headers,
            ) as response,
        ):
            await self.__async_check_response(response)
            return await response.json()

    async def async_set_max_current(self, connector_id: str, current: int):
        """Set max current. Login required."""
        self.__check_logged_in()

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.__base_url}/connector/{connector_id}/maxcurrent?current={current}",
                headers=self.__headers,
            ) as response,
        ):
            await self.__async_check_response(response)

    async def async_start_charging(self, connector_alias: str):
        """Start charging. Login required."""
        self.__check_logged_in()

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.__base_url}/charging/start",
                headers=self.__headers,
                json={"alias": connector_alias},
            ) as response,
        ):
            await self.__async_check_response(response)

    async def async_stop_charging(self, connector_alias: str):
        """Stop charging. Login required."""
        self.__check_logged_in()

        async with (
            aiohttp.ClientSession() as session,
            session.post(
                f"{self.__base_url}/charging/stop",
                headers=self.__headers,
                json={"alias": connector_alias},
            ) as response,
        ):
            await self.__async_check_response(response)

    def __build_auth_headers(self, user_id: str, token: str):
        """Build headers."""
        return {"x-authorization": token, "x-user": user_id}

    def export_credentials(self) -> CloudChargeApiCredentials:
        """Export cloud charge api credentials. Login required."""
        self.__check_logged_in()
        return {
            "user_id": self.__headers.get("x-user"),
            "token": self.__headers.get("x-authorization"),
        }

    def import_credentials(self, credentials: CloudChargeApiCredentials):
        """Import cloud charge api credentials."""
        self.set_login(credentials["user_id"], credentials["token"])

    async def async_import_and_validate_credentials(
        self, credentials: CloudChargeApiCredentials
    ):
        """Import and validate cloud charge api credentials."""
        self.async_login_with_token(credentials["user_id"], credentials["token"])
