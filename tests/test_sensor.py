"""Tests for Ship24 sensor entities."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.ship24.sensor import Ship24PackageSensor, Ship24SummarySensor


def _coordinator(data):
    """Return a mock coordinator with the given data."""
    c = MagicMock()
    c.data = data
    return c


def _entry(entry_id="test_entry"):
    """Return a mock config entry."""
    e = MagicMock()
    e.entry_id = entry_id
    return e


def _pkg(tracking_number="1Z999AA10123456784", friendly_name="", status="In Transit",
         status_code="in_transit", **kwargs):
    """Build a minimal package data dict for use in sensor tests."""
    return {
        "tracking_number": tracking_number,
        "friendly_name": friendly_name,
        "status": status,
        "status_code": status_code,
        "courier": kwargs.get("courier", "ups"),
        "last_event": kwargs.get("last_event", ""),
        "last_event_time": kwargs.get("last_event_time", ""),
        "last_location": kwargs.get("last_location", ""),
        "estimated_delivery": kwargs.get("estimated_delivery", ""),
        "origin_country": kwargs.get("origin_country", ""),
        "destination_country": kwargs.get("destination_country", ""),
        "events": kwargs.get("events", []),
    }


def test_summary_sensor_name():
    """Summary sensor has the expected fixed name."""
    sensor = Ship24SummarySensor(_coordinator({}), _entry())
    assert sensor.name == "Ship24 Package Summary"


def test_summary_sensor_unique_id():
    """Unique ID includes the entry ID and summary suffix."""
    sensor = Ship24SummarySensor(_coordinator({}), _entry("my_entry"))
    assert sensor.unique_id == "ship24_my_entry_summary"


def test_summary_sensor_has_entity_name_false():
    """Summary sensor does not use the has_entity_name pattern."""
    sensor = Ship24SummarySensor(_coordinator({}), _entry())
    assert sensor.has_entity_name is False


def test_summary_sensor_state_short():
    """State equals the summary when it is within 255 characters."""
    c = _coordinator(None)
    c.get_spoken_summary.return_value = "You have no tracked packages."
    sensor = Ship24SummarySensor(c, _entry())
    assert sensor.native_value == "You have no tracked packages."


def test_summary_sensor_state_truncated():
    """State is truncated to 255 characters with ellipsis when too long."""
    c = _coordinator(None)
    c.get_spoken_summary.return_value = "A" * 300
    sensor = Ship24SummarySensor(c, _entry())
    assert len(sensor.native_value) == 255
    assert sensor.native_value.endswith("...")


def test_summary_sensor_attributes():
    """spoken_summary and package_count attributes are present and correct."""
    long_text = "X" * 300
    c = _coordinator({"A": {}, "B": {}})
    c.get_spoken_summary.return_value = long_text
    sensor = Ship24SummarySensor(c, _entry())
    attrs = sensor.extra_state_attributes
    assert attrs["spoken_summary"] == long_text
    assert attrs["package_count"] == 2


def test_summary_sensor_device_info():
    """Device info groups the sensor under the main Ship24 device."""
    sensor = Ship24SummarySensor(_coordinator({}), _entry("eid"))
    info = sensor.device_info
    assert info["name"] == "Ship24 Package Tracker"
    assert ("ship24", "eid") in info["identifiers"]


def test_package_sensor_unique_id():
    """Unique ID is built from the domain and tracking number."""
    sensor = Ship24PackageSensor(_coordinator({}), "1Z999AA10123456784")
    assert sensor.unique_id == "ship24_1Z999AA10123456784"


def test_package_sensor_name_is_none():
    """name=None makes the entity name equal to the device name in HA."""
    sensor = Ship24PackageSensor(_coordinator({}), "1Z999AA10123456784")
    assert sensor.name is None


def test_package_sensor_has_entity_name_true():
    """Package sensor uses the has_entity_name=True HA naming pattern."""
    sensor = Ship24PackageSensor(_coordinator({}), "1Z999AA10123456784")
    assert sensor.has_entity_name is True


def test_package_sensor_state_in_transit():
    """State reflects the In Transit status."""
    data = {"1Z999AA10123456784": _pkg(status="In Transit")}
    sensor = Ship24PackageSensor(_coordinator(data), "1Z999AA10123456784")
    assert sensor.native_value == "In Transit"


def test_package_sensor_state_delivered():
    """State reflects the Delivered status."""
    data = {"RR123456789CN": _pkg("RR123456789CN", status="Delivered", status_code="delivered")}
    sensor = Ship24PackageSensor(_coordinator(data), "RR123456789CN")
    assert sensor.native_value == "Delivered"


def test_package_sensor_state_none_when_no_data():
    """State is None when the coordinator holds no data."""
    sensor = Ship24PackageSensor(_coordinator(None), "1Z999AA10123456784")
    assert sensor.native_value is None


def test_package_sensor_display_name_uses_friendly_name():
    """Display name returns the friendly name when one is configured."""
    data = {"1Z999AA10123456784": _pkg(friendly_name="Amazon Order")}
    sensor = Ship24PackageSensor(_coordinator(data), "1Z999AA10123456784")
    assert sensor._display_name == "Amazon Order"


def test_package_sensor_display_name_falls_back_to_tracking_number():
    """Display name returns the tracking number when no friendly name is set."""
    data = {"1Z999AA10123456784": _pkg()}
    sensor = Ship24PackageSensor(_coordinator(data), "1Z999AA10123456784")
    assert sensor._display_name == "1Z999AA10123456784"


def test_package_sensor_icon_in_transit():
    """In-transit status shows the fast truck icon."""
    data = {"X": _pkg("X", status_code="in_transit")}
    assert Ship24PackageSensor(_coordinator(data), "X").icon == "mdi:truck-fast"


def test_package_sensor_icon_out_for_delivery():
    """Out-for-delivery status shows the delivery truck icon."""
    data = {"X": _pkg("X", status_code="out_for_delivery")}
    assert Ship24PackageSensor(_coordinator(data), "X").icon == "mdi:truck-delivery"


def test_package_sensor_icon_delivered():
    """Delivered status shows the check-mark package icon."""
    data = {"X": _pkg("X", status_code="delivered")}
    assert Ship24PackageSensor(_coordinator(data), "X").icon == "mdi:package-variant-closed-check"


def test_package_sensor_icon_exception():
    """Exception status shows the alert-circle icon."""
    data = {"X": _pkg("X", status_code="exception")}
    assert Ship24PackageSensor(_coordinator(data), "X").icon == "mdi:alert-circle"


def test_package_sensor_icon_default_when_no_data():
    """Default closed-box icon is shown when no data is available."""
    sensor = Ship24PackageSensor(_coordinator(None), "X")
    assert sensor.icon == "mdi:package-variant-closed"


def test_package_sensor_attributes_populated():
    """All expected attributes are present and correctly populated."""
    pkg = _pkg(
        tracking_number="1Z999AA10123456784",
        friendly_name="Amazon Order",
        courier="ups",
        last_event="Departed facility",
        last_location="Frankfurt, DE",
        origin_country="US",
        destination_country="DE",
        events=[{"status": "Departed", "datetime": "2024-03-15", "location": "DE"}],
    )
    sensor = Ship24PackageSensor(_coordinator({"1Z999AA10123456784": pkg}), "1Z999AA10123456784")
    attrs = sensor.extra_state_attributes

    assert attrs["tracking_number"] == "1Z999AA10123456784"
    assert attrs["friendly_name"] == "Amazon Order"
    assert attrs["courier"] == "ups"
    assert attrs["last_location"] == "Frankfurt, DE"
    assert attrs["origin_country"] == "US"
    assert attrs["destination_country"] == "DE"
    assert len(attrs["events"]) == 1


def test_package_sensor_attributes_empty_when_no_data():
    """Attributes dict is empty when coordinator has no data."""
    sensor = Ship24PackageSensor(_coordinator(None), "1Z999AA10123456784")
    assert sensor.extra_state_attributes == {}


def test_package_sensor_device_info_with_alias():
    """Device name uses the friendly name when one is configured."""
    data = {"1Z999AA10123456784": _pkg(friendly_name="Amazon Order")}
    sensor = Ship24PackageSensor(_coordinator(data), "1Z999AA10123456784")
    info = sensor.device_info
    assert info["name"] == "Amazon Order"
    assert ("ship24", "1Z999AA10123456784") in info["identifiers"]


def test_package_sensor_device_info_without_alias():
    """Device name falls back to tracking number when no alias is set."""
    data = {"1Z999AA10123456784": _pkg()}
    sensor = Ship24PackageSensor(_coordinator(data), "1Z999AA10123456784")
    info = sensor.device_info
    assert info["name"] == "1Z999AA10123456784"
