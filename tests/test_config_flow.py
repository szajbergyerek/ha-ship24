"""Tests for Ship24 config flow and options flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.data_entry_flow import FlowResultType

from custom_components.ship24.const import DOMAIN


async def test_step_user_shows_form(hass):
    """Config flow initial step renders the API key form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_step_user_invalid_auth(hass):
    """Config flow shows invalid_auth error when API key is rejected (403)."""
    from custom_components.ship24.api import Ship24AuthError

    with patch(
        "custom_components.ship24.config_flow.Ship24Api.validate_api_key",
        side_effect=Ship24AuthError("Invalid API key"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"api_key": "bad_key"}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"


async def test_step_user_cannot_connect(hass):
    """Config flow shows cannot_connect error on network failure."""
    from custom_components.ship24.api import Ship24ApiError

    with patch(
        "custom_components.ship24.config_flow.Ship24Api.validate_api_key",
        side_effect=Ship24ApiError("Connection error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"api_key": "any_key"}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"]["base"] == "cannot_connect"


async def test_step_user_success(hass):
    """Config flow creates a config entry on successful API key validation."""
    with patch(
        "custom_components.ship24.config_flow.Ship24Api.validate_api_key",
        return_value=True,
    ), patch(
        "custom_components.ship24.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"api_key": "valid_key_123"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["api_key"] == "valid_key_123"
    assert result["options"]["tracking_numbers"] == []
    assert result["options"]["package_aliases"] == {}


