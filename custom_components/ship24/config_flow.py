"""Config flow for the Ship24 Package Tracker integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import Ship24Api, Ship24AuthError, Ship24ApiError
from .const import CONF_PACKAGE_ALIASES, CONF_TRACKING_NUMBERS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
    }
)


class Ship24ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup config flow for Ship24."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """
        Handle the first step: API key entry and validation.

        param user_input: Form data submitted by the user, or None on first load.

        :return: FlowResult directing the UI to the next step or showing errors.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY].strip()
            session = async_get_clientsession(self.hass)
            api = Ship24Api(api_key=api_key, session=session)

            try:
                await api.validate_api_key()
            except Ship24AuthError:
                errors["base"] = "invalid_auth"
            except Ship24ApiError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected error during Ship24 API key validation")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Ship24 Package Tracker",
                    data={CONF_API_KEY: api_key},
                    options={
                        CONF_TRACKING_NUMBERS: [],
                        CONF_PACKAGE_ALIASES: {},
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
            description_placeholders={
                "api_key_url": "https://dashboard.ship24.com/integrations/api-keys",
            },
        )
