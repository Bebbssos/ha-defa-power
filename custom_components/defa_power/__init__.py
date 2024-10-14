import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the DEFA Power integration."""
    _LOGGER.info("Setting up DEFA Power integration")
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry) -> bool:
    """Set up DEFA Power from a config entry."""
    _LOGGER.info("Setting up DEFA Power from config entry")
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading DEFA Power config entry")
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    return True
