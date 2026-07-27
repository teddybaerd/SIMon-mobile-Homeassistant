"""Data coordinator for SIMon mobile."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import (
    SimonMobileApi,
    SimonMobileAuthError,
    SimonMobileConnectionError,
    SimonMobileData,
)
from .const import DOMAIN, UPDATE_INTERVAL

LOGGER = logging.getLogger(__name__)


class SimonMobileCoordinator(DataUpdateCoordinator[SimonMobileData]):
    """Coordinate SIMon mobile updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: SimonMobileApi,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            logger=LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> SimonMobileData:
        """Fetch the latest data."""
        try:
            return await self.api.async_get_data()
        except SimonMobileAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SimonMobileConnectionError as err:
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected SIMon mobile API error: {err}") from err

