"""DataUpdateCoordinator for the Ship24 Package Tracker integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Ship24Api, Ship24ApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, STATUS_MAP

_LOGGER = logging.getLogger(__name__)


class Ship24Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches Ship24 data for all tracked packages."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: Ship24Api,
        tracking_numbers: list[str],
        package_aliases: dict[str, str] | None = None,
    ) -> None:
        """
        Initialize the Ship24 coordinator.

        param hass: The Home Assistant instance.
        param api: An initialized Ship24Api client.
        param tracking_numbers: List of tracking numbers to monitor.
        param package_aliases: Optional dict mapping tracking number to friendly name.

        :return: None
        """
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self.tracking_numbers: list[str] = list(tracking_numbers)
        self.package_aliases: dict[str, str] = package_aliases or {}

    async def _async_update_data(self) -> dict[str, Any]:
        """
        Fetch updated tracking data from the Ship24 API.

        :return: Dict keyed by tracking number with parsed package data.
        """
        try:
            raw_trackings = await self.api.get_tracking_results(self.tracking_numbers)
        except Ship24ApiError as err:
            raise UpdateFailed(f"Error communicating with Ship24 API: {err}") from err

        result: dict[str, Any] = {}
        for tracking in raw_trackings:
            parsed = _parse_tracking(tracking, self.package_aliases)
            if parsed:
                result[parsed["tracking_number"]] = parsed

        return result

    def get_spoken_summary(self) -> str:
        """
        Build a human-readable summary sentence for all tracked packages.

        Suitable for use as TTS output or a voice assistant response.

        :return: A spoken-language summary string of all package statuses.
        """
        if not self.data:
            return "No package data available yet."

        packages = list(self.data.values())
        count = len(packages)

        if count == 0:
            return "You have no tracked packages."

        parts: list[str] = []
        for pkg in packages:
            name = pkg.get("friendly_name") or pkg["tracking_number"]
            status = pkg.get("status", "Unknown")
            location = pkg.get("last_location", "")
            eta = pkg.get("estimated_delivery", "")

            sentence = f"{name} is {status}"
            if location:
                sentence += f", last seen in {location}"
            if eta and "delivered" not in status.lower():
                eta_date = eta[:10] if len(eta) >= 10 else eta
                sentence += f", estimated delivery {eta_date}"
            parts.append(sentence)

        intro = (
            "You have 1 tracked package."
            if count == 1
            else f"You have {count} tracked packages."
        )
        return intro + " " + ". ".join(parts) + "."


def _parse_tracking(
    tracking: dict[str, Any],
    aliases: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """
    Parse a raw Ship24 tracking result into a flat dict for use by sensors.

    param tracking: A single tracking dict from the Ship24 API response.
    param aliases: Optional dict mapping tracking number to a friendly name.

    :return: Parsed dict with normalized fields, or None if tracking number missing.
    """
    tracker: dict[str, Any] = tracking.get("tracker", {})
    shipment: dict[str, Any] = tracking.get("shipment") or {}
    events: list[dict[str, Any]] = tracking.get("events", []) or []

    tracking_number: str | None = tracker.get("trackingNumber")
    if not tracking_number:
        return None

    raw_status = (
        shipment.get("statusCode")
        or shipment.get("statusCategory")
        or "pending"
    )
    friendly_status = STATUS_MAP.get(
        raw_status, raw_status.replace("_", " ").title()
    )

    sorted_events = sorted(
        events,
        key=lambda e: e.get("occurrenceDatetime", ""),
        reverse=True,
    )

    last_event: dict[str, Any] = sorted_events[0] if sorted_events else {}
    delivery: dict[str, Any] = shipment.get("delivery") or {}

    event_list = [
        {
            "status": e.get("status", ""),
            "datetime": e.get("occurrenceDatetime", ""),
            "location": e.get("location", ""),
        }
        for e in sorted_events[:10]
    ]

    friendly_name = (aliases or {}).get(tracking_number, "")

    return {
        "tracking_number": tracking_number,
        "friendly_name": friendly_name,
        "status": friendly_status,
        "status_code": raw_status,
        "courier": _get_courier(tracker, last_event),
        "last_event": last_event.get("status", ""),
        "last_event_time": last_event.get("occurrenceDatetime", ""),
        "last_location": last_event.get("location", ""),
        "estimated_delivery": delivery.get("estimatedDeliveryDate", ""),
        "origin_country": shipment.get("originCountryCode", ""),
        "destination_country": shipment.get("destinationCountryCode", ""),
        "events": event_list,
    }


def _get_courier(tracker: dict[str, Any], last_event: dict[str, Any]) -> str:
    """
    Extract the courier name from tracker or event data.

    param tracker: The tracker dict from Ship24 response.
    param last_event: The most recent tracking event dict.

    :return: Courier name string, empty string if unknown.
    """
    for field in ("courierCode", "slug", "sourceCode"):
        value = tracker.get(field) or last_event.get(field)
        if value:
            return str(value)
    return ""
