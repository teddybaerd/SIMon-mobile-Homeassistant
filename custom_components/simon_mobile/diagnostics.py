"""Diagnostics for SIMon mobile."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_PASSWORD, CONF_USERNAME
from .coordinator import SimonMobileCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics."""
    coordinator: SimonMobileCoordinator = entry.runtime_data
    return {
        "config_entry": async_redact_data(
            dict(entry.data), {CONF_USERNAME, CONF_PASSWORD}
        ),
        "last_update_success": coordinator.last_update_success,
        "packages": [
            {
                "id": package.id,
                "name": package.name,
                "type": package.package_type,
                "consumptions": [
                    {
                        "consumed": item.consumed,
                        "left": item.left,
                        "max": item.maximum,
                        "type": item.type,
                        "unit": item.unit,
                        "expiration_date": (
                            item.expiration_date.isoformat()
                            if item.expiration_date
                            else None
                        ),
                    }
                    for item in package.consumptions
                ],
            }
            for package in coordinator.data.packages
        ],
    }

