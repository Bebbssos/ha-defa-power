"""Config flow for DEFA power integration."""

from collections.abc import Mapping
import logging
import re
from typing import Any
import uuid

import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.data_entry_flow import FlowResult
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
CONF_DEV_TOKEN_OPTIONS = "dev_token_options"
CONF_CUSTOM_DEV_TOKEN = "custom_dev_token"
CONF_USER_ID = "user_id"
CONF_TOKEN = "token"

SEND_CODE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PHONE_NUMBER): cv.string,
        vol.Required(CONF_DEV_TOKEN_OPTIONS): SelectSelector(
            SelectSelectorConfig(
                translation_key="dev_token_options",
                mode=SelectSelectorMode.LIST,
                options=[
                    "cloud_charge",
                    "defa_power",
                    "custom",
                ],
            )
        ),
        vol.Optional(CONF_CUSTOM_DEV_TOKEN): cv.string,
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

OPTIONS_CHOICE_SCHEMA = vol.Schema(
    {
        vol.Required("select_step"): SelectSelector(
            SelectSelectorConfig(
                translation_key="select_step",
                mode=SelectSelectorMode.LIST,
                options=[
                    "show_current_token",
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
    """DEFA Power config flow."""

    VERSION = 2
    MINOR_VERSION = 1

    send_code_data: dict[str, Any] | None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        return await self.async_step_choose_method()

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Handle the reconfigure."""
        return await self.async_step_choose_method()

    async def async_step_reauth(self, entry_data: Mapping[str, Any]):
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_choose_method()

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
                match user_input[CONF_DEV_TOKEN_OPTIONS]:
                    case "cloud_charge":
                        dev_token = "X5zVn6MCWvrf6ft2"
                    case "defa_power":
                        dev_token = "XqP3sCFKdg4vrV8J"
                    case "custom":
                        dev_token = user_input.get(CONF_CUSTOM_DEV_TOKEN)
                    case _:
                        dev_token = ""

                await client.async_send_sms_code(
                    user_input[CONF_PHONE_NUMBER], dev_token
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
                self.send_code_data = {
                    "phone_number": user_input[CONF_PHONE_NUMBER],
                    "dev_token": dev_token,
                }
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
                    self.send_code_data["phone_number"],
                    user_input[CONF_SMS_CODE],
                    self.send_code_data["dev_token"],
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
                return self.__add_or_update_entry(data)

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
                return self.__add_or_update_entry(data)

        return self.async_show_form(
            step_id="manual_entry", data_schema=MANUAL_ENTRY_SCHEMA, errors=errors
        )

    def __add_or_update_entry(self, data: Mapping[str, Any]):
        if self.source in (
            config_entries.SOURCE_RECONFIGURE,
            config_entries.SOURCE_REAUTH,
        ):
            if self.source == config_entries.SOURCE_RECONFIGURE:
                entry = self._get_reconfigure_entry()
            elif self.source == config_entries.SOURCE_REAUTH:
                entry = self._get_reauth_entry()
            else:
                entry = None

            if not entry:
                return self.async_abort(reason="existing_entry_not_found")

            data["instance_id"] = entry.data.get("instance_id")

            return self.async_update_reload_and_abort(
                entry,
                data_updates=data,
            )

        data["instance_id"] = get_instance_id()
        return self.async_create_entry(title=NAME, data=data)

    @staticmethod
    @core.callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return DefaPowerOptionsFlowHandler(config_entry)


class DefaPowerOptionsFlowHandler(config_entries.OptionsFlow):
    """DEFA Power options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            if user_input["select_step"] == "show_current_token":
                return await self.async_step_show_token()

        return self.async_show_form(
            step_id="init",
            data_schema=OPTIONS_CHOICE_SCHEMA,
        )

    async def async_step_show_token(self, user_input: dict[str, Any] | None = None):
        """Show the current token."""
        if user_input is not None:
            return await self.async_step_init()

        return self.async_show_form(
            step_id="show_token",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_USER_ID,
                        default=self.config_entry.data["credentials"]["user_id"],
                    ): cv.string,
                    vol.Optional(
                        CONF_TOKEN,
                        default=self.config_entry.data["credentials"]["token"],
                    ): cv.string,
                }
            ),
        )
