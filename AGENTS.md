# AGENTS.md

## What this repo is

Home Assistant custom integration for DEFA Power / eRange EV chargers. Distributed via HACS. Communicates with the CloudCharge API (`https://prod.cloudcharge.se/services/user`).

## No local toolchain

There is **no build system, no test runner, no linter, no formatter config** in this repo. No `pyproject.toml`, `Makefile`, `tox.ini`, or pre-commit hooks. All automated checks happen in CI only.

To validate changes, push to GitHub — CI runs:
1. **HACS validation** (`hacs/action@main`)
2. **Hassfest** (`home-assistant/actions/hassfest@master`) — validates `manifest.json`, translations, and component structure

There is no way to run these locally without installing the tools manually.

## Dependencies

`manifest.json` has `requirements: []`. All dependencies (`aiohttp`, `homeassistant`) are provided by the HA runtime. **Do not add packages to `requirements`** unless they are genuinely third-party and not bundled with HA.

## Component directory

All integration code lives in `custom_components/defa_power/`. This is the only directory that matters for the integration itself.

## Architecture

**Three coordinators** are created per connector:
- `CloudChargeChargepointCoordinator` — polls every 15 min
- `CloudChargeOperationalDataCoordinator` — polls every 60 s; drops to 10 s while `chargingState == "Charging"` and calls `async_start_live_consumption`
- `CloudChargeEcoModeCoordinator` — only created if `capabilities.ecoMode == True`; uses a write-coalesce pattern via `set_data(callback)` that batches rapid writes then refreshes

**Device hierarchy**: `ChargePointDevice` (parent) → `ConnectorDevice` (child, linked via `via_device`). Parent devices are registered before child devices — order matters.

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
