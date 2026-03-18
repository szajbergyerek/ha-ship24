"""Ship24 API client for the Ship24 Package Tracker integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import API_BASE_URL, API_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class Ship24ApiError(Exception):
    """Raised when the Ship24 API returns an error."""


class Ship24AuthError(Ship24ApiError):
    """Raised when the API key is invalid or unauthorized."""


class Ship24Api:
    """Async client for the Ship24 REST API."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession) -> None:
        """
        Initialize the Ship24 API client.

        param api_key: The Ship24 API bearer token.
        param session: An active aiohttp ClientSession to use for requests.
        """
        self._api_key = api_key
        self._session = session

    @property
    def _headers(self) -> dict[str, str]:
        """
        Return the default HTTP headers for API requests.

        :return: Dict with Authorization and Content-Type headers.
        """
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def validate_api_key(self) -> bool:
        """
        Validate the API key using the couriers endpoint.

        Ship24 returns 403 (not 401) for invalid/missing API keys.

        :return: True if the API key is valid, raises Ship24AuthError otherwise.
        """
        url = f"{API_BASE_URL}/couriers"
        try:
            async with self._session.get(
                url,
                headers=self._headers,
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT),
            ) as response:
                if response.status == 403:
                    raise Ship24AuthError("Invalid or unauthorized API key")
                return True
        except aiohttp.ClientError as err:
            raise Ship24ApiError(f"Connection error during validation: {err}") from err

    async def get_all_tracker_numbers(self) -> list[str]:
        """
        Fetch all tracking numbers registered in the Ship24 account.

        Handles pagination automatically, fetching up to 100 trackers per page.

        :return: List of tracking number strings from the account.
        """
        url = f"{API_BASE_URL}/trackers"
        tracking_numbers: list[str] = []
        page = 1

        while True:
            try:
                async with self._session.get(
                    url,
                    headers=self._headers,
                    params={"page": page, "limit": 100},
                    timeout=aiohttp.ClientTimeout(total=API_TIMEOUT),
                ) as response:
                    if response.status == 403:
                        raise Ship24AuthError("Invalid or unauthorized API key")
                    if response.status != 200:
                        _LOGGER.warning(
                            "Ship24 GET /trackers returned status %d", response.status
                        )
                        break
                    data = await response.json()
                    trackers = data.get("data", {}).get("trackers", [])
                    if not trackers:
                        break
                    for tracker in trackers:
                        tn = tracker.get("trackingNumber")
                        if tn:
                            tracking_numbers.append(tn)
                    if len(trackers) < 100:
                        break
                    page += 1
            except Ship24AuthError:
                raise
            except aiohttp.ClientError as err:
                _LOGGER.warning("Connection error fetching tracker list: %s", err)
                break

        _LOGGER.debug("Found %d tracker(s) in Ship24 account", len(tracking_numbers))
        return tracking_numbers

    async def get_tracking_results(
        self, tracking_numbers: list[str]
    ) -> list[dict[str, Any]]:
        """
        Fetch tracking results for the given list of tracking numbers.

        Uses POST /public/v1/trackers/track per tracking number, which creates
        the tracker subscription if it does not exist (idempotent) and returns
        the current tracking result in a single call.

        param tracking_numbers: List of tracking number strings to query.

        :return: List of tracking result dicts, one per successfully fetched number.
        """
        if not tracking_numbers:
            return []

        results: list[dict[str, Any]] = []
        url = f"{API_BASE_URL}/trackers/track"

        for tracking_number in tracking_numbers:
            payload = {"trackingNumber": tracking_number}
            try:
                async with self._session.post(
                    url,
                    headers=self._headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=API_TIMEOUT),
                ) as response:
                    if response.status == 403:
                        raise Ship24AuthError("Invalid or unauthorized API key")
                    if response.status not in (200, 201):
                        text = await response.text()
                        _LOGGER.warning(
                            "Ship24 returned status %d for %s: %s",
                            response.status,
                            tracking_number,
                            text,
                        )
                        continue
                    data = await response.json()
                    trackings = data.get("data", {}).get("trackings", [])
                    for tracking in trackings:
                        if tracking:
                            results.append(tracking)
            except Ship24AuthError:
                raise
            except aiohttp.ClientError as err:
                _LOGGER.warning(
                    "Connection error fetching %s: %s", tracking_number, err
                )
                continue

        _LOGGER.debug("Fetched %d tracking result(s) from Ship24", len(results))
        return results
