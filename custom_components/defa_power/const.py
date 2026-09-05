"""Constants for the DEFA Power integration."""

DOMAIN = "defa_power"
NAME = "DEFA Power"
API_BASE_URL = "https://prod.cloudcharge.se/services/user"

CONF_REQUEST_INTERVAL_MS = "request_interval_ms"
DEFAULT_REQUEST_INTERVAL_MS = 1000

# Config entry version handled by async_migrate_entry
CONFIG_ENTRY_VERSION = 3
CONFIG_ENTRY_MINOR_VERSION = 1

# Entry data keys holding the config flow selection until the subentries for it
# have been created during the first setup
INITIAL_CONNECTOR_IDS = "initial_connector_ids"
INITIAL_CHARGEPOINT_IDS = "initial_chargepoint_ids"
