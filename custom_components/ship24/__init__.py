"""The Ship24 Package Tracker integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api import Ship24Api
from .const import (
    CONF_PACKAGE_ALIASES,
    CONF_SUPPRESSED_NUMBERS,
    CONF_TRACKING_NUMBERS,
    DOMAIN,
    SERVICE_REMOVE_PACKAGE,
)
from .coordinator import Ship24Coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

REMOVE_PACKAGE_SCHEMA = vol.Schema(
    {
        vol.Required("tracking_number"): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Set up Ship24 from a config entry.

    Creates the API client, coordinator, registers services, and forwards
    platform setup to the sensor platform.

    param hass: The Home Assistant instance.
    param entry: The config entry to set up.

    :return: True if setup succeeded.
    """
    hass.data.setdefault(DOMAIN, {})

    api_key: str = entry.data[CONF_API_KEY]
    tracking_numbers: list[str] = entry.options.get(CONF_TRACKING_NUMBERS, [])
    package_aliases: dict[str, str] = entry.options.get(CONF_PACKAGE_ALIASES, {})
    suppressed_numbers: list[str] = entry.options.get(CONF_SUPPRESSED_NUMBERS, [])

    session = async_get_clientsession(hass)
    api = Ship24Api(api_key=api_key, session=session)

    coordinator = Ship24Coordinator(
        hass=hass,
        api=api,
        tracking_numbers=tracking_numbers,
        package_aliases=package_aliases,
        suppressed_numbers=suppressed_numbers,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    _register_services(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """
    Unload a Ship24 config entry and clean up resources.

    param hass: The Home Assistant instance.
    param entry: The config entry to unload.

    :return: True if unload succeeded.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    Reload the config entry when options are updated.

    param hass: The Home Assistant instance.
    param entry: The config entry that was updated.

    :return: None
    """
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """
    Register Ship24 services for removing tracked packages.

    Services are only registered once per HA instance (idempotent check).

    param hass: The Home Assistant instance.
    param entry: The config entry used to persist suppressed tracking numbers.

    :return: None
    """
    if hass.services.has_service(DOMAIN, SERVICE_REMOVE_PACKAGE):
        return

    async def handle_remove_package(call: ServiceCall) -> None:
        """
        Handle the ship24.remove_package service call.

        Adds the tracking number to the suppressed list so it is excluded
        from future syncs, then reloads the integration.

        param call: The service call data containing 'tracking_number'.

        :return: None
        """
        tracking_number: str = call.data["tracking_number"].strip().upper()

        suppressed: list[str] = list(entry.options.get(CONF_SUPPRESSED_NUMBERS, []))

        if tracking_number not in suppressed:
            suppressed.append(tracking_number)
            hass.config_entries.async_update_entry(
                entry,
                options={
                    **entry.options,
                    CONF_SUPPRESSED_NUMBERS: suppressed,
                },
            )
            await hass.config_entries.async_reload(entry.entry_id)
            _LOGGER.info("Suppressed tracking number: %s", tracking_number)
        else:
            _LOGGER.warning("Tracking number already suppressed: %s", tracking_number)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_PACKAGE,
        handle_remove_package,
        schema=REMOVE_PACKAGE_SCHEMA,
    )
    _LOGGER.debug("Ship24 services registered")
