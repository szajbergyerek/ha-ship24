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
        Validate the API key by making a lightweight API call.

        :return: True if the API key is valid, raises Ship24AuthError otherwise.
        """
        url = f"{API_BASE_URL}/trackers/search/results"
        payload = {"trackingNumbers": ["TEST_VALIDATION_000"]}
        try:
            async with self._session.post(
                url,
                headers=self._headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT),
            ) as response:
                if response.status == 401:
                    raise Ship24AuthError("Invalid API key")
                
                return True
        except aiohttp.ClientError as err:
            raise Ship24ApiError(f"Connection error during validation: {err}") from err

    async def get_tracking_results(
        self, tracking_numbers: list[str]
    ) -> list[dict[str, Any]]:
        """
        Fetch tracking results for the given list of tracking numbers.

        param tracking_numbers: List of tracking number strings to query.

        :return: List of tracking result dicts from the Ship24 API.
        """
        if not tracking_numbers:
            return []

        url = f"{API_BASE_URL}/trackers/search/results"
        payload = {"trackingNumbers": tracking_numbers}

        try:
            async with self._session.post(
                url,
                headers=self._headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT),
            ) as response:
                if response.status == 401:
                    raise Ship24AuthError("Invalid API key")
                if response.status not in (200, 207):
                    text = await response.text()
                    raise Ship24ApiError(
                        f"API returned status {response.status}: {text}"
                    )
                data = await response.json()
        except aiohttp.ClientError as err:
            raise Ship24ApiError(f"Connection error: {err}") from err

        trackings: list[dict[str, Any]] = (
            data.get("data", {}).get("trackings", [])
        )
        _LOGGER.debug("Received %d tracking result(s) from Ship24", len(trackings))
        return trackings
