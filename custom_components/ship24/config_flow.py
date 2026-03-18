"""Config flow for the Ship24 Package Tracker integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "Ship24OptionsFlow":
        """
        Return the options flow handler for this config entry.

        param config_entry: The existing config entry to configure options for.

        :return: An initialized Ship24OptionsFlow instance.
        """
        return Ship24OptionsFlow(config_entry)


class Ship24OptionsFlow(config_entries.OptionsFlow):
    """Handle options (tracking numbers and friendly names) for an existing Ship24 entry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """
        Initialize the Ship24 options flow.

        param config_entry: The config entry whose options are being modified.
        """
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """
        Handle the options form: manage tracked packages with optional friendly names.

        Format per line: TRACKINGNUMBER or TRACKINGNUMBER:Friendly Name
        Empty lines are ignored. Duplicates are removed.

        param user_input: Form data submitted by the user, or None on first load.

        :return: FlowResult updating the options or showing the form.
        """
        errors: dict[str, str] = {}

        current_numbers: list[str] = self.config_entry.options.get(
            CONF_TRACKING_NUMBERS, []
        )
        current_aliases: dict[str, str] = self.config_entry.options.get(
            CONF_PACKAGE_ALIASES, {}
        )

        # Reconstruct textarea lines from stored data
        lines = []
        for number in current_numbers:
            alias = current_aliases.get(number, "")
            lines.append(f"{number}:{alias}" if alias else number)
        current_text = "\n".join(lines)

        if user_input is not None:
            raw_text: str = user_input.get(CONF_TRACKING_NUMBERS, "")
            tracking_numbers: list[str] = []
            package_aliases: dict[str, str] = {}

            seen: set[str] = set()
            for line in raw_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if ":" in line:
                    number, _, alias = line.partition(":")
                    number = number.strip().upper()
                    alias = alias.strip()
                else:
                    number = line.upper()
                    alias = ""

                if number and number not in seen:
                    seen.add(number)
                    tracking_numbers.append(number)
                    if alias:
                        package_aliases[number] = alias

            return self.async_create_entry(
                title="",
                data={
                    CONF_TRACKING_NUMBERS: tracking_numbers,
                    CONF_PACKAGE_ALIASES: package_aliases,
                },
            )

        options_schema = vol.Schema(
            {
                vol.Optional(CONF_TRACKING_NUMBERS, default=current_text): str,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
            description_placeholders={
                "example": "1Z999AA10123456784:Amazon Order\nRR123456789CN:AliExpress\nJD014600000000",
            },
        )
