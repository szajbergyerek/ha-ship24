"""Intent handlers for the Ship24 Package Tracker integration."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, SERVICE_REMOVE_PACKAGE

_LOGGER = logging.getLogger(__name__)

INTENT_REMOVE_PACKAGE = "Ship24RemovePackage"


async def async_setup_intents(hass: HomeAssistant) -> None:
    """
    Register Ship24 intent handlers with Home Assistant.

    Only registers once per HA instance to avoid overwrite warnings on reload.

    param hass: The Home Assistant instance.

    :return: None
    """
    if hass.data.get(DOMAIN, {}).get("_intents_registered"):
        return
    intent.async_register(hass, RemovePackageIntentHandler())
    hass.data.setdefault(DOMAIN, {})["_intents_registered"] = True
    _LOGGER.debug("Ship24 intent handlers registered")


class RemovePackageIntentHandler(intent.IntentHandler):
    """Handle the Ship24RemovePackage intent to remove a tracked package."""

    intent_type = INTENT_REMOVE_PACKAGE
    slot_schema = {
        "tracking_number": cv.string,
    }

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        """
        Handle a remove package intent by calling the ship24.remove_package service.

        param intent_obj: The intent object containing slot data.

        :return: An IntentResponse with a confirmation speech string.
        """
        tracking_number: str = (
            intent_obj.slots.get("tracking_number", {}).get("value", "").strip().upper()
        )

        if not tracking_number:
            response = intent_obj.create_response()
            response.async_set_speech("I didn't catch the tracking number. Please try again.")
            return response

        await intent_obj.hass.services.async_call(
            DOMAIN,
            SERVICE_REMOVE_PACKAGE,
            {"tracking_number": tracking_number},
            blocking=True,
        )

        _LOGGER.info("Removed package via voice intent: %s", tracking_number)
        response = intent_obj.create_response()
        response.async_set_speech(
            f"Done. Package {tracking_number} has been removed from tracking."
        )
        return response
