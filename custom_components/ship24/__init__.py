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
    CONF_TRACKING_NUMBERS,
    DOMAIN,
    SERVICE_ADD_PACKAGE,
    SERVICE_REMOVE_PACKAGE,
)
from .coordinator import Ship24Coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

ADD_PACKAGE_SCHEMA = vol.Schema(
    {
        vol.Required("tracking_number"): cv.string,
        vol.Optional("friendly_name", default=""): cv.string,
    }
)

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

    session = async_get_clientsession(hass)
    api = Ship24Api(api_key=api_key, session=session)

    coordinator = Ship24Coordinator(
        hass=hass,
        api=api,
        tracking_numbers=tracking_numbers,
        package_aliases=package_aliases,
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
        hass.data[DOMAIN].pop(entry.entry_id)
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
    Register Ship24 services for adding and removing tracked packages.

    Services are only registered once per HA instance (idempotent check).

    param hass: The Home Assistant instance.
    param entry: The config entry used to persist tracking numbers.

    :return: None
    """
    if hass.services.has_service(DOMAIN, SERVICE_ADD_PACKAGE):
        return

    async def handle_add_package(call: ServiceCall) -> None:
        """
        Handle the ship24.add_package service call.

        Adds a tracking number (with optional friendly name) to the options and reloads.

        param call: The service call data containing 'tracking_number' and optional 'friendly_name'.

        :return: None
        """
        tracking_number: str = call.data["tracking_number"].strip().upper()
        friendly_name: str = call.data.get("friendly_name", "").strip()

        current_numbers: list[str] = list(
            entry.options.get(CONF_TRACKING_NUMBERS, [])
        )
        current_aliases: dict[str, str] = dict(
            entry.options.get(CONF_PACKAGE_ALIASES, {})
        )

        if tracking_number not in current_numbers:
            current_numbers.append(tracking_number)

        if friendly_name:
            current_aliases[tracking_number] = friendly_name

        hass.config_entries.async_update_entry(
            entry,
            options={
                **entry.options,
                CONF_TRACKING_NUMBERS: current_numbers,
                CONF_PACKAGE_ALIASES: current_aliases,
            },
        )
        await hass.config_entries.async_reload(entry.entry_id)
        _LOGGER.info(
            "Added tracking number: %s (name: %s)",
            tracking_number,
            friendly_name or "-",
        )

    async def handle_remove_package(call: ServiceCall) -> None:
        """
        Handle the ship24.remove_package service call.

        Removes a tracking number and its alias from the options and reloads.

        param call: The service call data containing 'tracking_number'.

        :return: None
        """
        tracking_number: str = call.data["tracking_number"].strip().upper()

        current_numbers: list[str] = list(
            entry.options.get(CONF_TRACKING_NUMBERS, [])
        )
        current_aliases: dict[str, str] = dict(
            entry.options.get(CONF_PACKAGE_ALIASES, {})
        )

        if tracking_number in current_numbers:
            current_numbers.remove(tracking_number)
            current_aliases.pop(tracking_number, None)
            hass.config_entries.async_update_entry(
                entry,
                options={
                    **entry.options,
                    CONF_TRACKING_NUMBERS: current_numbers,
                    CONF_PACKAGE_ALIASES: current_aliases,
                },
            )
            await hass.config_entries.async_reload(entry.entry_id)
            _LOGGER.info("Removed tracking number: %s", tracking_number)
        else:
            _LOGGER.warning("Tracking number not found: %s", tracking_number)

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_PACKAGE,
        handle_add_package,
        schema=ADD_PACKAGE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_PACKAGE,
        handle_remove_package,
        schema=REMOVE_PACKAGE_SCHEMA,
    )
    _LOGGER.debug("Ship24 services registered")
