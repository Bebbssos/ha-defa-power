"""Diagnostics for DEFA Power integration."""

from functools import partial
import time
from typing import Any

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.core import HomeAssistant

from .models import DefaPowerConfigEntry
from .utils.id_anonymizer import IdAnonymizer


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: DefaPowerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    data = {}
    id_anonymizer = IdAnonymizer()

    data["chargepoints"] = {}
    for chargepoint_id, val in entry.runtime_data["chargepoints"].items():
        aid = id_anonymizer.anonymize(chargepoint_id, "anonymized_id")
        d = {"skipped_entities": val["skipped_entities"]}
        data["chargepoints"][aid] = d

    data["connectors"] = {}
    for connector_id, val in entry.runtime_data["connectors"].items():
        aid = id_anonymizer.anonymize(connector_id, "anonymized_id")
        d = {
            "chargepoint_id": id_anonymizer.anonymize(
                val["chargepoint_id"], "anonymized_id"
            ),
            "skipped_entities": val["skipped_entities"],
            "capabilities": val["capabilities"],
            "alias": id_anonymizer.anonymize(val["alias"], "anonymized_alias"),
        }
        data["connectors"][aid] = d

    data["api_responses"] = await _async_get_api_responses(entry, id_anonymizer)

    return data


async def _async_get_api_responses(
    entry: DefaPowerConfigEntry, id_anonymizer: IdAnonymizer
):
    client = entry.runtime_data["client"]
    data = {}

    await _async_call_api(
        data, "get_private_chargepoints", client.async_get_private_chargepoints
    )
    await _async_call_api(data, "get_my_chargers", client.async_get_my_chargers)

    data["chargepoints"] = {}
    for chargepoint_id in entry.runtime_data["chargepoints"]:
        d = {}
        data["chargepoints"][
            id_anonymizer.anonymize(chargepoint_id, "anonymized_id")
        ] = d
        await _async_call_api(
            d, "get_chargepoint", partial(client.async_get_chargepoint, chargepoint_id)
        )

    data["connectors"] = {}
    for connector_id in entry.runtime_data["connectors"]:
        d = {}
        data["connectors"][id_anonymizer.anonymize(connector_id, "anonymized_id")] = d
        await _async_call_api(
            d,
            "get_operational_data",
            partial(client.async_get_operational_data, connector_id),
        )
        await _async_call_api(
            d,
            "get_eco_mode_configuration",
            partial(client.async_get_eco_mode_configuration, connector_id),
        )
        await _async_call_api(
            d,
            "get_load_balancer",
            partial(client.async_get_load_balancer, connector_id),
        )
        await _async_call_api(
            d,
            "get_network_configuration",
            partial(client.async_get_network_configuration, connector_id),
        )
        await _async_call_api(
            d,
            "get_max_current_alternatives",
            partial(client.async_get_max_current_alternatives, connector_id),
        )

    return async_redact_data(
        _anonymize_object(data, id_anonymizer),
        [
            "location",
            "locationDescription",
            "zipcode",
            "postalArea",
            "latitude",
            "longitude",
            "serialNumber",
            "displayName",
            "nickname",
            "SSID",
        ],
    )


async def _async_call_api(data: dict[str, Any], prop: str, call: callable):
    """Call an API method and handle exceptions."""
    try:
        start_time = time.perf_counter()
        res = await call()
        execution_time = time.perf_counter() - start_time
        data[prop] = res
        data[f"{prop}_execution_time"] = round(execution_time, 3)
    except Exception as e:
        data[prop] = (
            f"An exception of type {type(e).__name__} occurred. Arguments:\n{e.args!r}"
        )


def _anonymize_object(
    obj: dict | list | Any, id_anonymizer: IdAnonymizer
) -> dict | list | Any:
    """Recursively anonymize sensitive IDs in an object."""
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            # Handle keys that need anonymization
            if key in ("id", "chargeSystemId") and isinstance(value, str):
                result[key] = id_anonymizer.anonymize(value, "anonymized_id")
            elif key == "smsAlias" and isinstance(value, str):
                result[key] = id_anonymizer.anonymize(value, "anonymized_alias")
            # Special handling for aliasMap which contains connector IDs as keys
            elif key == "aliasMap" and isinstance(value, dict):
                anonymized_map = {}
                for connector_id, connector_data in value.items():
                    # Anonymize the connector ID key
                    anonymized_key = id_anonymizer.anonymize(
                        connector_id, "anonymized_alias"
                    )
                    # Recursively anonymize the connector data values
                    anonymized_map[anonymized_key] = _anonymize_object(
                        connector_data, id_anonymizer
                    )
                result[key] = anonymized_map
            else:
                # For all other keys, recursively process the value
                result[key] = _anonymize_object(value, id_anonymizer)
        return result
    elif isinstance(obj, list):
        return [_anonymize_object(item, id_anonymizer) for item in obj]
    else:
        # Return primitive values unchanged
        return obj
