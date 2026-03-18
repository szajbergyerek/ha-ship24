"""The Ship24 Package Tracker integration."""

from __future__ import annotations

import logging

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
from .intent import async_setup_intents

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

REMOVE_PACKAGE_SCHEMA = vol.Schema(
    {
        vol.Optional("tracking_number"): cv.string,
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

    _register_services(hass, entry)
    await async_setup_intents(hass)

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

        If tracking_number is provided, suppresses that single package.
        If omitted, suppresses all currently delivered packages.

        Updates the coordinator in memory immediately and persists the suppressed
        list to config entry options — no integration reload is needed.

        param call: The service call data, optionally containing 'tracking_number'.

        :return: None
        """
        coordinator: Ship24Coordinator | None = hass.data.get(DOMAIN, {}).get(
            entry.entry_id
        )

        raw_tn: str = call.data.get("tracking_number", "").strip().upper()

        if raw_tn:
            to_suppress = [raw_tn]
        else:
            if not coordinator or not coordinator.data:
                _LOGGER.warning("No coordinator data available to find delivered packages")
                return
            to_suppress = [
                tn
                for tn, pkg in coordinator.data.items()
                if pkg.get("status_code") == "delivered"
            ]
            if not to_suppress:
                _LOGGER.info("No delivered packages found to suppress")
                return

        suppressed: list[str] = list(entry.options.get(CONF_SUPPRESSED_NUMBERS, []))
        added = [tn for tn in to_suppress if tn not in suppressed]

        if not added:
            _LOGGER.info("All requested package(s) already suppressed")
            return

        suppressed.extend(added)

        # Update coordinator in memory immediately so sensors reflect the change
        if coordinator:
            coordinator.suppressed_numbers.update(added)
            if coordinator.data:
                new_data = {
                    tn: pkg
                    for tn, pkg in coordinator.data.items()
                    if tn not in coordinator.suppressed_numbers
                }
                coordinator.async_set_updated_data(new_data)

        # Persist suppressed list to config entry options (no reload needed)
        hass.config_entries.async_update_entry(
            entry,
            options={**entry.options, CONF_SUPPRESSED_NUMBERS: suppressed},
        )

        _LOGGER.info("Suppressed %d package(s): %s", len(added), added)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_PACKAGE,
        handle_remove_package,
        schema=REMOVE_PACKAGE_SCHEMA,
    )
    _LOGGER.debug("Ship24 services registered")
