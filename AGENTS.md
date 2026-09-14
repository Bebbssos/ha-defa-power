# AGENTS.md

## What this repo is

Home Assistant custom integration for DEFA Power / eRange EV chargers. Distributed via HACS. Communicates with the CloudCharge API (`https://prod.cloudcharge.se/services/user`). Also reads DEFA Balancer load balancers directly from the local network (UDP multicast), which needs no CloudCharge account.

## No local toolchain

There is **no build system and no test runner** in this repo. No `pyproject.toml`, `Makefile`, `tox.ini`, or pre-commit hooks. All automated checks happen in CI only.

The one exception is `.ruff.toml`, which only configures import sorting to match Home Assistant core's style (`force-sort-within-sections`, `homeassistant` as first-party). Without it, editors running ruff flag every file with I001. It selects no extra lint rules and there is no lint step in CI.

To validate changes, push to GitHub — CI runs:
1. **HACS validation** (`hacs/action@main`)
2. **Hassfest** (`home-assistant/actions/hassfest@master`) — validates `manifest.json`, translations, and component structure

There is no way to run these locally without installing the tools manually.

## Dependencies

`manifest.json` has `requirements: []`. All dependencies (`aiohttp`, `homeassistant`) are provided by the HA runtime. **Do not add packages to `requirements`** unless they are genuinely third-party and not bundled with HA.

## Component directory

All integration code lives in `custom_components/defa_power/`. This is the only directory that matters for the integration itself.

## Architecture

**Two kinds of config entry** share the domain, told apart by `entry.data["entry_type"]` (`is_balancer_entry()` in `models.py`; entries without the key are CloudCharge entries from before balancer support). `async_setup_entry`, `async_unload_entry`, `async_migrate_entry`, the sensor platform, diagnostics, `async_get_supported_subentry_types` and `async_supports_options_flow` all branch on it. Keep any future CloudCharge entry migration behind that check — balancer entries carry no `credentials`.

- **CloudCharge entry** (`entry_type` absent or `"cloudcharge"`): one account; `chargepoint` and `connector` subentries. Everything below applies to these.
- **Balancer entry** (`entry_type == "balancer"`): one listening interface (`interface_ip`); `balancer` subentries keyed by serial. One `BalancerListener` per entry joins `234.222.250.1:57082` on that interface (`SO_REUSEADDR`/`SO_REUSEPORT`, so a config-flow scan can run beside it) and dispatches decoded packets to one push-based `BalancerCoordinator` per serial. The coordinator's `update_interval` is only a watchdog: `async_set_updated_data` reschedules it on every packet, so `_async_update_data` runs — and raises `UpdateFailed` — only after `BALANCER_STALE_TIMEOUT` of silence. Setup waits at most `BALANCER_FIRST_BROADCAST_TIMEOUT` for each balancer's first packet, then continues regardless; entities of a silent balancer just go unavailable. Only the `sensor` platform is forwarded. The wire format lives in `balancer/protocol.py`, reverse engineered — bytes 15..20 and 29..33 are still unknown, and the diagnostics dump includes the raw payload so they can be studied. Balancer device identifiers are `(DOMAIN, "balancer", serial)` and unique ids `balancer_{serial}_{key}`: no instance id, the serial is a real hardware id.

**Three coordinators** are created per connector:
- `CloudChargeChargepointCoordinator` — polls every 15 min
- `CloudChargeOperationalDataCoordinator` — polls every 60 s; drops to 10 s while `chargingState == "Charging"` and calls `async_start_live_consumption`
- `CloudChargeEcoModeCoordinator` — only created if `capabilities.ecoMode == True`; uses a write-coalesce pattern via `set_data(callback)` that batches rapid writes then refreshes

**Device hierarchy**: `ChargePointDevice` (parent) → `ConnectorDevice` (child, linked via `via_device_id`). Each chargepoint is registered in the device registry in `async_setup_entry` before its connectors are built, and the resulting device entry id is passed to `ConnectorDevice` — order matters. (`via_device` is deprecated and raises in HA 2026.9+ when the deprecation report cannot find an integration frame.)

**Entity skipping**: Entities where `value_fn` returns `None` at setup and `create_if_none=False` (default) are intentionally omitted, not created as unavailable.

## Key conventions

- `unique_id` pattern: `{instance_id}_{chargepoint_or_connector_id}_{entity_key}`
- Translation keys are prefixed with the domain: `defa_power_{entity_key}`
- Both `en.json` and `sv.json` translations must be kept in sync — hassfest validates completeness
- Config entry is `version=2, minor_version=1`; migration from v1 (`userId`/`token`) to v2 (`credentials: {user_id, token}`) exists in `__init__.py`
- API auth uses headers `x-authorization` (token) and `x-user` (user_id)
- Services target **connectors** (by `connector_alias`), not chargepoints — this is a common source of user confusion

## Releases

- HACS uses ZIP release: `hacs.json` sets `"zip_release": true`, `"filename": "defa_power.zip"`
- The `upload_zip.yaml` workflow triggers on tag push and creates a **draft** release — drafts must be manually published
- The ZIP must be named exactly `defa_power.zip`

## Tests

No tests exist. If adding them, use `pytest-homeassistant-custom-component`. The API client creates a new `aiohttp.ClientSession` per request, so calls are independently mockable.

## API reference

CloudCharge API swagger: `https://prod.cloudcharge.se/services/user/swagger.json`
