# Balancer entries

Balancer config entries (`entry_type == "balancer"`). See [AGENTS.md](../AGENTS.md) for how entry types are told apart.

- One listening interface, stored by *name* in `interface` and resolved to its current IPv4 address at every setup by `balancer/interface.py`; `balancer` subentries keyed by serial.
- One `BalancerListener` per entry (not per balancer) joins `234.222.250.1:57082` and dispatches decoded packets to one push-based `BalancerCoordinator` per serial, whose `update_interval` is only a stale watchdog driven by the entry option `stale_timeout`.
- Setup waits at most `BALANCER_FIRST_BROADCAST_TIMEOUT` for a first packet, then continues; a silent balancer's entities just go unavailable.
- Only the `sensor` platform is forwarded.
- Wire format in `balancer/protocol.py`, reverse engineered — bytes 15..20 and 29..33 unknown, raw payload included in diagnostics, which also capture every packet on the group for `BALANCER_DIAGNOSTICS_CAPTURE_TIME` (decodable or not, via `BalancerListener.async_register_raw`). Chargers broadcast separately on UDP port 57083; that is not listened to.
- Device identifiers `(DOMAIN, "balancer", serial)`, unique ids `balancer_{serial}_{key}`: no instance id, the serial is a real hardware id.
- Several non-obvious choices here are deliberate and explained in code comments — the socket options in `listener.py`, the watchdog margin in `BalancerCoordinator`, and `async_get_supported_subentry_types` offering every type on every entry.
