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

# Entry data key telling the two kinds of config entry apart. Entries created
# before balancer support existed have no such key and are CloudCharge entries.
CONF_ENTRY_TYPE = "entry_type"
ENTRY_TYPE_CLOUDCHARGE = "cloudcharge"
ENTRY_TYPE_BALANCER = "balancer"

# Balancer entry data: the local IPv4 address of the interface the balancer
# multicast is received on, and the serials selected in the config flow
CONF_INTERFACE_IP = "interface_ip"
CONF_BALANCER_SERIAL = "serial"

# The balancer announces itself on the local network with a UDP multicast; no
# CloudCharge account is involved
BALANCER_MULTICAST_ADDR = "234.222.250.1"
BALANCER_MULTICAST_PORT = 57082
# How long the config flow listens for balancers
BALANCER_SCAN_TIMEOUT = 10
# How long entry setup waits for the first broadcast of each balancer
BALANCER_FIRST_BROADCAST_TIMEOUT = 5
# Entities go unavailable when no broadcast has been received for this long
BALANCER_STALE_TIMEOUT = 60
