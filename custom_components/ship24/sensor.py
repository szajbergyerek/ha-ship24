"""Sensor platform for the Ship24 Package Tracker integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_COURIER,
    ATTR_DESTINATION_COUNTRY,
    ATTR_ESTIMATED_DELIVERY,
    ATTR_EVENTS,
    ATTR_FRIENDLY_NAME,
    ATTR_LAST_EVENT,
    ATTR_LAST_EVENT_TIME,
    ATTR_LAST_LOCATION,
    ATTR_ORIGIN_COUNTRY,
    ATTR_PACKAGE_COUNT,
    ATTR_SPOKEN_SUMMARY,
    ATTR_STATUS_CODE,
    ATTR_TRACKING_NUMBER,
    DOMAIN,
)
from .coordinator import Ship24Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """
    Set up Ship24 sensor entities from a config entry.

    Creates a summary sensor plus one sensor per tracked package. Dynamically
    adds new package sensors as new tracking numbers appear after coordinator
    updates (e.g. packages added on the Ship24 website).

    param hass: The Home Assistant instance.
    param entry: The config entry for this integration instance.
    param async_add_entities: Callback to register new sensor entities.

    :return: None
    """
    coordinator: Ship24Coordinator = hass.data[DOMAIN][entry.entry_id]
    known_tracking_numbers: set[str] = set()

    async_add_entities([Ship24SummarySensor(coordinator, entry)])

    def _add_new_package_sensors() -> None:
        """Add sensors for any tracking numbers not yet registered."""
        current_numbers = set(coordinator.data or {})
        new_numbers = current_numbers - known_tracking_numbers
        if new_numbers:
            known_tracking_numbers.update(new_numbers)
            async_add_entities(
                [Ship24PackageSensor(coordinator, tn) for tn in new_numbers]
            )

    _add_new_package_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_package_sensors))


class Ship24SummarySensor(CoordinatorEntity[Ship24Coordinator], SensorEntity):
    """Sensor providing a spoken summary of all tracked packages for voice assistants."""

    _attr_icon = "mdi:package-variant-closed-shipping"
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: Ship24Coordinator,
        entry: ConfigEntry,
    ) -> None:
        """
        Initialize the Ship24 summary sensor.

        param coordinator: The Ship24 data coordinator.
        param entry: The config entry this sensor belongs to.
        """
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_summary"
        self._attr_name = "Ship24 Package Summary"

    @property
    def native_value(self) -> str:
        """
        Return the spoken summary as the sensor state (capped at 255 chars).

        Voice assistants read this state when the sensor is queried.

        :return: Spoken summary string, truncated if needed.
        """
        summary = self.coordinator.get_spoken_summary()
        if len(summary) > 255:
            summary = summary[:252] + "..."
        return summary

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """
        Return the full spoken summary and package count as attributes.

        :return: Dict with spoken_summary (full text) and package_count.
        """
        return {
            ATTR_SPOKEN_SUMMARY: self.coordinator.get_spoken_summary(),
            ATTR_PACKAGE_COUNT: len(self.coordinator.data or {}),
        }

    @property
    def device_info(self) -> dict[str, Any]:
        """
        Group the summary sensor under the main Ship24 integration device.

        :return: Dict with device identifiers and metadata.
        """
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "Ship24 Package Tracker",
            "manufacturer": "Ship24",
            "model": "Package Tracker",
        }


class Ship24PackageSensor(CoordinatorEntity[Ship24Coordinator], SensorEntity):
    """
    Sensor representing a single tracked package.

    Each package is its own HA device. With has_entity_name=True and name=None,
    the entity name equals the device name (friendly name or tracking number),
    showing a clean single label in the UI without duplication.
    """

    _attr_icon = "mdi:package-variant-closed"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Ship24Coordinator,
        tracking_number: str,
    ) -> None:
        """
        Initialize a Ship24 package sensor.

        param coordinator: The Ship24 data coordinator.
        param tracking_number: The package tracking number this sensor represents.
        """
        super().__init__(coordinator)
        self._tracking_number = tracking_number
        self._attr_unique_id = f"{DOMAIN}_{tracking_number}"
        self._attr_name = None

    @property
    def _package_data(self) -> dict[str, Any] | None:
        """
        Return the latest parsed data for this tracking number.

        :return: Dict with package fields, or None if not yet available.
        """
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._tracking_number)

    @property
    def _display_name(self) -> str:
        """
        Return the friendly name if configured, otherwise the tracking number.

        :return: Human-readable identifier for this package.
        """
        data = self._package_data
        if data:
            alias = data.get("friendly_name", "")
            if alias:
                return alias
        return self._tracking_number

    @property
    def native_value(self) -> str | None:
        """
        Return the current delivery status as the sensor state.

        :return: Human-readable status string, or None if data is unavailable.
        """
        data = self._package_data
        if data is None:
            return None
        return data.get("status")

    @property
    def icon(self) -> str:
        """
        Return a status-specific MDI icon.

        :return: MDI icon string.
        """
        data = self._package_data
        if data is None:
            return "mdi:package-variant-closed"
        return {
            "delivered": "mdi:package-variant-closed-check",
            "in_transit": "mdi:truck-fast",
            "out_for_delivery": "mdi:truck-delivery",
            "failed_attempt": "mdi:package-variant-remove",
            "exception": "mdi:alert-circle",
            "available_for_pickup": "mdi:store",
        }.get(data.get("status_code", ""), "mdi:package-variant-closed")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """
        Return additional state attributes for this package sensor.

        :return: Dict of attribute name to value.
        """
        data = self._package_data
        if data is None:
            return {}
        return {
            ATTR_TRACKING_NUMBER: data.get("tracking_number", ""),
            ATTR_FRIENDLY_NAME: data.get("friendly_name", ""),
            ATTR_STATUS_CODE: data.get("status_code", ""),
            ATTR_COURIER: data.get("courier", ""),
            ATTR_LAST_EVENT: data.get("last_event", ""),
            ATTR_LAST_EVENT_TIME: data.get("last_event_time", ""),
            ATTR_LAST_LOCATION: data.get("last_location", ""),
            ATTR_ESTIMATED_DELIVERY: data.get("estimated_delivery", ""),
            ATTR_ORIGIN_COUNTRY: data.get("origin_country", ""),
            ATTR_DESTINATION_COUNTRY: data.get("destination_country", ""),
            ATTR_EVENTS: data.get("events", []),
        }

    @property
    def device_info(self) -> dict[str, Any]:
        """
        Expose each package as its own HA device named by its friendly name or tracking number.

        :return: Dict with device identifiers and metadata.
        """
        return {
            "identifiers": {(DOMAIN, self._tracking_number)},
            "name": self._display_name,
            "manufacturer": "Ship24",
            "model": "Package Tracker",
        }
