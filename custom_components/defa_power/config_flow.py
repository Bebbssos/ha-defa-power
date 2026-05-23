"""Config flow for DEFA power integration."""

from collections.abc import Mapping
import logging
import re
from typing import Any
import uuid

import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.config_entries import ConfigFlowResult, ConfigSubentryFlow
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    SelectOptionDict,
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
    _login_data: dict[str, Any] | None = None
    _profile_name: str | None = None
    _connector_options: list[SelectOptionDict] | None = None
    _chargepoint_options: list[SelectOptionDict] | None = None

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
                else:
                    errors["base"] = "phonenumber_prelogin_error"
            except CloudChargeForbiddenError as e:
                _LOGGER.error("Forbidden %s error: %s", e.raw_message, e)
                if e.error_type == CloudChargeForbiddenErrorType.INVALID_DEV_TOKEN:
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
            if self.send_code_data is None:
                _LOGGER.error("SMS code step reached without prior send_code_data")
                return await self.async_step_send_code()
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
                return await self._async_finish_login(data)

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
                return await self._async_finish_login(data)

        return self.async_show_form(
            step_id="manual_entry", data_schema=MANUAL_ENTRY_SCHEMA, errors=errors
        )

    async def _async_finish_login(self, data: dict[str, Any]):
        """Shared post-login handler: fetch profile, then route to device selection or update."""
        self._login_data = data
        client = CloudChargeAPIClient(API_BASE_URL)
        client.import_credentials(data["credentials"])
        try:
            profile = await client.async_get_profile()
            first = (profile.get("firstName") or "").strip()
            last = (profile.get("lastName") or "").strip()
            name = f"{first} {last}".strip()
            self._profile_name = f"CloudCharge ({name})" if name else None
        except CloudChargeAPIError:
            self._profile_name = None

        if self.source in (config_entries.SOURCE_RECONFIGURE, config_entries.SOURCE_REAUTH):
            return self.__add_or_update_entry(data)
        return await self.async_step_select_devices()

    async def async_step_select_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select which connectors to add during initial setup."""
        if self._connector_options is None:
            client = CloudChargeAPIClient(API_BASE_URL)
            assert self._login_data is not None
            client.import_credentials(self._login_data["credentials"])
            try:
                chargepoint_ids = await client.async_get_chargepoint_ids()
                conn_options: list[SelectOptionDict] = []
                cp_options: list[SelectOptionDict] = []
                for cp_id in chargepoint_ids:
                    cp_data = await client.async_get_chargepoint(cp_id)
                    cp_name = cp_data.get("displayName") or cp_id
                    cp_options.append(SelectOptionDict(value=cp_id, label=cp_name))
                    for alias, val in (cp_data.get("aliasMap") or {}).items():
                        conn_id = val.get("id")
                        if not conn_id:
                            continue
                        conn_name = val.get("displayName") or alias
                        key = f"{conn_id}:{cp_id}"
                        conn_options.append(SelectOptionDict(value=key, label=f"{conn_name} ({cp_name})"))
                self._connector_options = conn_options
                self._chargepoint_options = cp_options
            except CloudChargeAPIError:
                self._connector_options = []
                self._chargepoint_options = []

        if not self._connector_options and not self._chargepoint_options:
            assert self._login_data is not None
            self._login_data["initial_connector_ids"] = []
            self._login_data["initial_chargepoint_ids"] = []
            return self.__add_or_update_entry(self._login_data)

        if user_input is not None:
            selected_connectors = user_input.get("connector_keys") or []
            selected_chargepoints = user_input.get("chargepoint_keys") or []
            assert self._login_data is not None
            self._login_data["initial_connector_ids"] = [
                {"connector_id": k.split(":")[0], "chargepoint_id": k.split(":")[1]}
                for k in selected_connectors
            ]
            self._login_data["initial_chargepoint_ids"] = selected_chargepoints
            return self.__add_or_update_entry(self._login_data)

        schema_fields: dict = {
            vol.Optional("connector_keys", default=[]): SelectSelector(
                SelectSelectorConfig(
                    options=self._connector_options or [],
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            ),
        }
        if self._chargepoint_options:
            schema_fields[vol.Optional("chargepoint_keys", default=[])] = SelectSelector(
                SelectSelectorConfig(
                    options=self._chargepoint_options,
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            )

        return self.async_show_form(
            step_id="select_devices",
            data_schema=vol.Schema(schema_fields),
        )

    def __add_or_update_entry(self, data: dict[str, Any]):
        title = self._profile_name or NAME

        if self.source in (
            config_entries.SOURCE_RECONFIGURE,
            config_entries.SOURCE_REAUTH,
        ):
            if self.source == config_entries.SOURCE_RECONFIGURE:
                entry = self._get_reconfigure_entry()
                reason = "reconfigure_successful"
            elif self.source == config_entries.SOURCE_REAUTH:
                entry = self._get_reauth_entry()
                reason = "reauth_successful"
            else:
                entry = None
                reason = "reauth_successful"

            if not entry:
                return self.async_abort(reason="existing_entry_not_found")

            data["instance_id"] = entry.data.get("instance_id")

            return self.async_update_reload_and_abort(
                entry,
                data_updates=data,
                title=title,
                reason=reason,
            )

        data["instance_id"] = get_instance_id()
        return self.async_create_entry(title=title, data=data)

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: config_entries.ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return subentry types supported by this integration."""
        return {
            "connector": ConnectorSubentryFlowHandler,
            "chargepoint": ChargepointSubentryFlowHandler,
        }

    @staticmethod
    @core.callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return DefaPowerOptionsFlowHandler(config_entry)


class ConnectorSubentryFlowHandler(ConfigSubentryFlow):
    """Handle adding a connector subentry."""

    _options: list[SelectOptionDict] | None = None
    _titles: dict[str, str] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Handle the user step."""
        entry = self._get_entry()

        if self._options is None:
            try:
                options, titles = await self._fetch_connector_options(entry)
            except CloudChargeAPIError as err:
                _LOGGER.error("Failed to fetch connectors for subentry flow: %s", err)
                return self.async_abort(reason="cannot_connect")

            if not options:
                return self.async_abort(reason="no_connectors_available")

            self._options = options
            self._titles = titles

        if user_input is not None:
            key = user_input["connector_key"]
            connector_id, chargepoint_id = key.split(":", 1)
            title = (self._titles or {}).get(key, connector_id)
            return self.async_create_entry(
                title=title,
                data={"connector_id": connector_id, "chargepoint_id": chargepoint_id, "connection_type": "cloudcharge"},
                unique_id=connector_id,
            )

        assert self._options is not None
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("connector_key"): SelectSelector(
                        SelectSelectorConfig(
                            options=self._options,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def _fetch_connector_options(
        self, entry: config_entries.ConfigEntry
    ) -> tuple[list[SelectOptionDict], dict[str, str]]:
        """Fetch available connectors, excluding already-added ones."""
        client = CloudChargeAPIClient(API_BASE_URL)
        client.import_credentials(entry.data["credentials"])

        already_added = {
            sub.data["connector_id"]
            for sub in entry.subentries.values()
            if sub.subentry_type == "connector"
        }

        chargepoint_ids = await client.async_get_chargepoint_ids()
        options: list[SelectOptionDict] = []
        titles: dict[str, str] = {}

        for cp_id in chargepoint_ids:
            cp_data = await client.async_get_chargepoint(cp_id)
            cp_name = cp_data.get("displayName") or cp_id
            for alias, val in (cp_data.get("aliasMap") or {}).items():
                conn_id = val.get("id")
                if not conn_id or conn_id in already_added:
                    continue
                conn_name = val.get("displayName") or alias
                key = f"{conn_id}:{cp_id}"
                label = f"{conn_name} ({cp_name})"
                options.append(SelectOptionDict(value=key, label=label))
                titles[key] = label

        return options, titles


class ChargepointSubentryFlowHandler(ConfigSubentryFlow):
    """Handle adding a chargepoint subentry."""

    _options: list[SelectOptionDict] | None = None
    _titles: dict[str, str] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.SubentryFlowResult:
        """Handle the user step."""
        entry = self._get_entry()

        if self._options is None:
            try:
                options, titles = await self._fetch_chargepoint_options(entry)
            except CloudChargeAPIError as err:
                _LOGGER.error(
                    "Failed to fetch chargepoints for subentry flow: %s", err
                )
                return self.async_abort(reason="cannot_connect")

            if not options:
                return self.async_abort(reason="no_chargepoints_available")

            self._options = options
            self._titles = titles

        if user_input is not None:
            cp_id = user_input["chargepoint_key"]
            title = (self._titles or {}).get(cp_id, cp_id)
            return self.async_create_entry(
                title=title,
                data={"chargepoint_id": cp_id},
                unique_id=cp_id,
            )

        assert self._options is not None
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("chargepoint_key"): SelectSelector(
                        SelectSelectorConfig(
                            options=self._options,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def _fetch_chargepoint_options(
        self, entry: config_entries.ConfigEntry
    ) -> tuple[list[SelectOptionDict], dict[str, str]]:
        """Fetch available chargepoints, excluding already-added ones."""
        client = CloudChargeAPIClient(API_BASE_URL)
        client.import_credentials(entry.data["credentials"])

        already_added = {
            sub.data["chargepoint_id"]
            for sub in entry.subentries.values()
            if sub.subentry_type == "chargepoint"
        }

        chargepoint_ids = await client.async_get_chargepoint_ids()
        options: list[SelectOptionDict] = []
        titles: dict[str, str] = {}

        for cp_id in chargepoint_ids:
            if cp_id in already_added:
                continue
            try:
                cp_data = await client.async_get_chargepoint(cp_id)
                cp_name = cp_data.get("displayName") or cp_id
            except CloudChargeAPIError:
                cp_name = cp_id
            options.append(SelectOptionDict(value=cp_id, label=cp_name))
            titles[cp_id] = cp_name

        return options, titles


class DefaPowerOptionsFlowHandler(config_entries.OptionsFlow):
    """DEFA Power options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            if user_input["select_step"] == "show_current_token":
                return await self.async_step_show_token()

        return self.async_show_form(
            step_id="init",
            data_schema=OPTIONS_CHOICE_SCHEMA,
        )

    async def async_step_show_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
