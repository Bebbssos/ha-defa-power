"""Config flow for DEFA power integration."""

import logging
import re
from typing import Any
import uuid

import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .cloudcharge_api.client import CloudChargeAPIClient
from .cloudcharge_api.exceptions import (
    CloudChargeAPIError,
    CloudChargeAuthError,
    CloudChargeBadRequestError,
    CloudChargeBadRequestErrorType,
    CloudChargeForbiddenError,
    CloudChargeForbiddenErrorType,
    CloudChargeRequestError,
)
from .const import API_BASE_URL, DOMAIN, NAME

_LOGGER = logging.getLogger(__name__)

CONF_PHONE_NUMBER = "phone_number"
CONF_SMS_CODE = "sms_code"
CONF_DEV_TOKEN = "dev_token"
CONF_USER_ID = "user_id"
CONF_TOKEN = "token"

SEND_CODE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PHONE_NUMBER): cv.string,
        vol.Optional(CONF_DEV_TOKEN): cv.string,
    }
)
AUTH_SCHEMA = vol.Schema({vol.Required(CONF_SMS_CODE): cv.string})
MANUAL_ENTRY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USER_ID): cv.string,
        vol.Required(CONF_TOKEN): cv.string,
    }
)
CHOICE_SCHEMA = vol.Schema(
    {
        vol.Required("method"): SelectSelector(
            SelectSelectorConfig(
                translation_key="login_method",
                mode=SelectSelectorMode.LIST,
                options=[
                    "phone_number",
                    "manual",
                ],
            )
        )
    }
)


async def send_code(
    phoneNumber: str, devToken: str | None, hass: core.HomeAssistant
) -> None:
    """Send the code to the user."""
    session = async_get_clientsession(hass)

    # Construct the payload dynamically
    payload = {"phoneNr": phoneNumber}
    if devToken:
        payload["devToken"] = devToken

    await session.post(
        f"{API_BASE_URL}/prelogin",
        json=payload,
    )


async def login(
    phoneNumber: str, smsCode: str, devToken: str | None, hass: core.HomeAssistant
) -> None:
    """Login with the code."""
    session = async_get_clientsession(hass)

    payload = {"phoneNr": phoneNumber, "password": smsCode}
    if devToken:
        payload["devToken"] = devToken

    request = await session.post(
        f"{API_BASE_URL}/login",
        json=payload,
    )

    response = await request.json()

    return {"userId": response.get("id"), "token": response.get("token")}


def get_instance_id():
    """Generate a unique instance id."""
    return str(uuid.uuid4())


def normalize_phone_number(phone_number: str) -> str:
    """Normalize phone number to remove non-numeric characters."""
    return re.sub(r"\D", "", phone_number)


class DefaPowerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """DEFA power config flow."""

    VERSION = 2
    MINOR_VERSION = 1

    send_code_data: dict[str, Any] | None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        return await self.async_step_choose_method(user_input)

    async def async_step_reauth(self, user_input: dict[str, Any] | None = None):
        """Handle re-authentication."""
        return await self.async_step_choose_method(user_input)

    async def async_step_choose_method(self, user_input: dict[str, Any] | None = None):
        """Step to choose the method of configuration."""
        if user_input is not None:
            if user_input["method"] == "phone_number":
                return await self.async_step_send_code()
            if user_input["method"] == "manual":
                return await self.async_step_manual_entry()

        return self.async_show_form(step_id="choose_method", data_schema=CHOICE_SCHEMA)

    async def async_step_send_code(self, user_input: dict[str, Any] | None = None):
        """Enter phone number to receive the code."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                user_input[CONF_PHONE_NUMBER] = normalize_phone_number(
                    user_input[CONF_PHONE_NUMBER]
                )
                client = CloudChargeAPIClient(API_BASE_URL)
                await client.async_send_sms_code(
                    user_input[CONF_PHONE_NUMBER], user_input.get(CONF_DEV_TOKEN)
                )
            except CloudChargeBadRequestError as e:
                _LOGGER.error("Bad request %s error: %s", e.raw_message, e)
                if e.error_type == CloudChargeBadRequestErrorType.INVALID_PHONE_NUMBER:
                    errors["base"] = "phonenumber_invalid"
                elif e.error_type == CloudChargeBadRequestErrorType.INVALID_DEV_TOKEN:
                    errors["base"] = "phonenumber_invalid_dev_token"
                else:
                    errors["base"] = "phonenumber_prelogin_error"
            except CloudChargeRequestError as e:
                _LOGGER.error("Request error: %s", e)
                errors["base"] = "phonenumber_request_error"
            if not errors:
                # Input is valid, set data.
                self.send_code_data = user_input
                # Return the form of the next step.
                return await self.async_step_sms_code()

        return self.async_show_form(
            step_id="send_code", data_schema=SEND_CODE_SCHEMA, errors=errors
        )

    async def async_step_sms_code(self, user_input: dict[str, Any] | None = None):
        """Enter the SMS code."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Validate the path.
            data = {}
            try:
                client = CloudChargeAPIClient(API_BASE_URL)
                await client.async_login_with_phone_number(
                    self.send_code_data[CONF_PHONE_NUMBER],
                    user_input[CONF_SMS_CODE],
                    self.send_code_data.get(CONF_DEV_TOKEN),
                )
                data["credentials"] = client.export_credentials()
            except CloudChargeBadRequestError as e:
                _LOGGER.error("Bad request %s error: %s", e.raw_message, e)
                if e.error_type == CloudChargeBadRequestErrorType.INVALID_PHONE_NUMBER:
                    errors["base"] = "phonenumber_invalid"
                else:
                    errors["base"] = "phonenumber_login_error"
            except CloudChargeForbiddenError as e:
                _LOGGER.error("Forbidden %s error: %s", e.raw_message, e)
                if e.error_type == CloudChargeForbiddenErrorType.INVALID_DEV_TOKEN:
                    errors["base"] = "phonenumber_invalid_dev_token"
                elif (
                    e.error_type
                    == CloudChargeForbiddenErrorType.INVALID_LOGIN_CREDENTIALS
                ):
                    errors["base"] = "phonenumber_invalid_login"
                elif (
                    e.error_type
                    == CloudChargeForbiddenErrorType.NO_LOGIN_ATTEMPTS_FOUND
                ):
                    errors["base"] = "phonenumber_no_login_attempts_found"
                else:
                    errors["base"] = "phonenumber_login_error"
            except CloudChargeRequestError as e:
                _LOGGER.error("Request error: %s", e)
                errors["base"] = "phonenumber_request_error"

            if not errors:
                # User is done adding repos, create the config entry.
                data["instance_id"] = get_instance_id()
                return self.async_create_entry(title=NAME, data=data)

        return self.async_show_form(
            step_id="sms_code", data_schema=AUTH_SCHEMA, errors=errors
        )

    async def async_step_manual_entry(self, user_input: dict[str, Any] | None = None):
        """Step to manually enter userId and token."""
        errors: dict[str, str] = {}
        if user_input is not None:
            # Validate the input.
            user_id = user_input[CONF_USER_ID]
            token = user_input[CONF_TOKEN]
            data = {}
            try:
                client = CloudChargeAPIClient(API_BASE_URL)
                await client.async_login_with_token(user_id, token)
                data["credentials"] = client.export_credentials()
            except CloudChargeAuthError as e:
                _LOGGER.error("Auth error: %s", e)
                errors["base"] = "manual_entry_auth_error"
            except CloudChargeAPIError as e:
                _LOGGER.error("Request error: %s", e)
                errors["base"] = "manual_entry_request_error"

            if not errors:
                data["instance_id"] = get_instance_id()
                return self.async_create_entry(title=NAME, data=data)

        return self.async_show_form(
            step_id="manual_entry", data_schema=MANUAL_ENTRY_SCHEMA, errors=errors
        )
