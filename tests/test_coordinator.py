"""Tests for the Ship24 coordinator and data parsing functions."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.ship24.coordinator import (
    Ship24Coordinator,
    _get_courier,
    _parse_tracking,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(filename: str) -> dict:
    """Load a JSON fixture file from the fixtures directory."""
    with open(FIXTURES_DIR / filename) as f:
        return json.load(f)


def make_coordinator(data: dict | None, tracking_numbers: list | None = None) -> Ship24Coordinator:
    """Create a Ship24Coordinator with mocked hass and api."""
    hass = MagicMock()
    api = MagicMock()
    coordinator = Ship24Coordinator(hass=hass, api=api, tracking_numbers=tracking_numbers or [])
    coordinator.data = data
    return coordinator


def test_parse_tracking_in_transit():
    """Parse a standard in-transit tracking result."""
    data = load_fixture("tracking_in_transit.json")
    result = _parse_tracking(data)

    assert result is not None
    assert result["tracking_number"] == "1Z999AA10123456784"
    assert result["status"] == "In Transit"
    assert result["status_code"] == "in_transit"
    assert result["last_event"] == "Departed facility"
    assert result["last_location"] == "Frankfurt, DE"
    assert result["last_event_time"] == "2024-03-15T14:30:00.000Z"
    assert result["estimated_delivery"] == "2024-03-16T00:00:00.000Z"
    assert result["origin_country"] == "US"
    assert result["destination_country"] == "DE"
    assert result["courier"] == "ups"
    assert result["friendly_name"] == ""
    assert len(result["events"]) == 2


def test_parse_tracking_delivered():
    """Parse a delivered package result."""
    data = load_fixture("tracking_delivered.json")
    result = _parse_tracking(data)

    assert result is not None
    assert result["tracking_number"] == "RR123456789CN"
    assert result["status"] == "Delivered"
    assert result["status_code"] == "delivered"
    assert result["last_event"] == "Delivered"
    assert result["last_location"] == "Budapest, HU"
    assert result["origin_country"] == "CN"
    assert result["destination_country"] == "HU"
    assert result["estimated_delivery"] == ""


def test_parse_tracking_no_events():
    """Parse a result with no events and null shipment."""
    data = load_fixture("tracking_no_data.json")
    result = _parse_tracking(data)

    assert result is not None
    assert result["tracking_number"] == "JD014600000000"
    assert result["status"] == "Pending"
    assert result["last_event"] == ""
    assert result["last_location"] == ""
    assert result["events"] == []


def test_parse_tracking_with_alias():
    """Alias is included in the parsed result when provided."""
    data = load_fixture("tracking_in_transit.json")
    result = _parse_tracking(data, aliases={"1Z999AA10123456784": "Amazon Order"})
    assert result["friendly_name"] == "Amazon Order"


def test_parse_tracking_alias_not_matching():
    """Unrelated alias does not affect the tracking number."""
    data = load_fixture("tracking_in_transit.json")
    result = _parse_tracking(data, aliases={"OTHER_NUMBER": "Some Name"})
    assert result["friendly_name"] == ""


def test_parse_tracking_missing_tracking_number():
    """Returns None when tracker has no trackingNumber field."""
    result = _parse_tracking({"tracker": {}, "shipment": {}, "events": []})
    assert result is None


def test_parse_tracking_null_shipment():
    """Handles null shipment gracefully and defaults to Pending status."""
    data = load_fixture("tracking_in_transit.json")
    data = dict(data)
    data["shipment"] = None
    result = _parse_tracking(data)

    assert result is not None
    assert result["status"] == "Pending"
    assert result["estimated_delivery"] == ""


def test_parse_tracking_events_sorted_newest_first():
    """Most recent event is the first in the list and returned as last_event."""
    data = load_fixture("tracking_in_transit.json")
    result = _parse_tracking(data)

    assert result["last_event"] == "Departed facility"
    assert result["events"][0]["status"] == "Departed facility"


def test_get_courier_from_tracker_courierCode():
    """Courier is read from tracker courierCode field."""
    assert _get_courier({"courierCode": "ups"}, {}) == "ups"


def test_get_courier_from_tracker_slug():
    """Courier falls back to slug field when courierCode is absent."""
    assert _get_courier({"slug": "dhl"}, {}) == "dhl"


def test_get_courier_from_event_sourceCode():
    """Courier is read from event sourceCode when tracker has no courier fields."""
    assert _get_courier({}, {"sourceCode": "fedex"}) == "fedex"


def test_get_courier_empty():
    """Returns empty string when no courier info is available."""
    assert _get_courier({}, {}) == ""


def test_spoken_summary_no_data():
    """Returns a safe message when coordinator data is None."""
    coordinator = make_coordinator(None)
    assert coordinator.get_spoken_summary() == "No package data available yet."


def test_spoken_summary_empty_dict():
    """Returns a message when there are no tracked packages."""
    coordinator = make_coordinator({})
    assert coordinator.get_spoken_summary() == "You have no tracked packages."


def test_spoken_summary_single_package_with_alias():
    """Single package summary uses the friendly name, includes location and ETA."""
    coordinator = make_coordinator({
        "1Z999AA10123456784": {
            "tracking_number": "1Z999AA10123456784",
            "friendly_name": "Amazon Order",
            "status": "In Transit",
            "last_location": "Frankfurt, DE",
            "estimated_delivery": "2024-03-16T00:00:00.000Z",
        }
    })
    summary = coordinator.get_spoken_summary()
    assert "1 tracked package" in summary
    assert "Amazon Order is In Transit" in summary
    assert "Frankfurt, DE" in summary
    assert "2024-03-16" in summary


def test_spoken_summary_uses_tracking_number_when_no_alias():
    """Tracking number is used in the summary when no friendly name is set."""
    coordinator = make_coordinator({
        "1Z999AA10123456784": {
            "tracking_number": "1Z999AA10123456784",
            "friendly_name": "",
            "status": "In Transit",
            "last_location": "",
            "estimated_delivery": "",
        }
    })
    summary = coordinator.get_spoken_summary()
    assert "1Z999AA10123456784 is In Transit" in summary


def test_spoken_summary_delivered_omits_eta():
    """Delivered packages do not include estimated delivery in the summary."""
    coordinator = make_coordinator({
        "RR123456789CN": {
            "tracking_number": "RR123456789CN",
            "friendly_name": "AliExpress",
            "status": "Delivered",
            "last_location": "Budapest",
            "estimated_delivery": "2024-03-16T00:00:00.000Z",
        }
    })
    summary = coordinator.get_spoken_summary()
    assert "estimated delivery" not in summary


def test_spoken_summary_multiple_packages():
    """Summary mentions total count and all package names."""
    coordinator = make_coordinator({
        "AAA": {
            "tracking_number": "AAA",
            "friendly_name": "Package A",
            "status": "In Transit",
            "last_location": "",
            "estimated_delivery": "",
        },
        "BBB": {
            "tracking_number": "BBB",
            "friendly_name": "Package B",
            "status": "Delivered",
            "last_location": "",
            "estimated_delivery": "",
        },
    })
    summary = coordinator.get_spoken_summary()
    assert "2 tracked packages" in summary
    assert "Package A" in summary
    assert "Package B" in summary


async def test_coordinator_async_update_data_parses_results():
    """Coordinator fetches data via API and returns correctly parsed tracking dicts."""
    api = AsyncMock()
    api.get_all_tracker_numbers.return_value = []
    api.get_tracking_results.return_value = [load_fixture("tracking_in_transit.json")]

    coordinator = Ship24Coordinator(
        hass=MagicMock(),
        api=api,
        tracking_numbers=["1Z999AA10123456784"],
        package_aliases={"1Z999AA10123456784": "Amazon Order"},
    )

    result = await coordinator._async_update_data()

    assert "1Z999AA10123456784" in result
    assert result["1Z999AA10123456784"]["status"] == "In Transit"
    assert result["1Z999AA10123456784"]["friendly_name"] == "Amazon Order"
    api.get_tracking_results.assert_called_once_with(["1Z999AA10123456784"])


async def test_coordinator_async_update_data_empty():
    """Coordinator returns empty dict when API returns no results."""
    api = AsyncMock()
    api.get_all_tracker_numbers.return_value = []
    api.get_tracking_results.return_value = []

    coordinator = Ship24Coordinator(hass=MagicMock(), api=api, tracking_numbers=[])
    result = await coordinator._async_update_data()
    assert result == {}


async def test_coordinator_async_update_data_skips_missing_tracker():
    """Coordinator skips entries where the tracking number is absent in the response."""
    api = AsyncMock()
    api.get_all_tracker_numbers.return_value = []
    api.get_tracking_results.return_value = [
        {"tracker": {}, "shipment": {}, "events": []}
    ]

    coordinator = Ship24Coordinator(hass=MagicMock(), api=api, tracking_numbers=["BAD"])
    result = await coordinator._async_update_data()
    assert result == {}
