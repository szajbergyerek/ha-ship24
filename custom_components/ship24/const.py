"""Constants for the Ship24 Package Tracker integration."""

DOMAIN = "ship24"

CONF_API_KEY = "api_key"
CONF_TRACKING_NUMBERS = "tracking_numbers"
CONF_PACKAGE_ALIASES = "package_aliases"

DEFAULT_SCAN_INTERVAL = 3600  # seconds (1 hour)

API_BASE_URL = "https://api.ship24.com/public/v1"
API_TIMEOUT = 30  # seconds

STATUS_MAP = {
    "pending": "Pending",
    "info_received": "Info Received",
    "in_transit": "In Transit",
    "out_for_delivery": "Out for Delivery",
    "failed_attempt": "Failed Delivery Attempt",
    "available_for_pickup": "Available for Pickup",
    "delivered": "Delivered",
    "exception": "Exception",
    "expired": "Expired",
}

ATTR_TRACKING_NUMBER = "tracking_number"
ATTR_FRIENDLY_NAME = "friendly_name"
ATTR_COURIER = "courier"
ATTR_STATUS_CODE = "status_code"
ATTR_LAST_EVENT = "last_event"
ATTR_LAST_EVENT_TIME = "last_event_time"
ATTR_LAST_LOCATION = "last_location"
ATTR_ESTIMATED_DELIVERY = "estimated_delivery"
ATTR_ORIGIN_COUNTRY = "origin_country"
ATTR_DESTINATION_COUNTRY = "destination_country"
ATTR_EVENTS = "events"
ATTR_SPOKEN_SUMMARY = "spoken_summary"
ATTR_PACKAGE_COUNT = "package_count"

SERVICE_ADD_PACKAGE = "add_package"
SERVICE_REMOVE_PACKAGE = "remove_package"
