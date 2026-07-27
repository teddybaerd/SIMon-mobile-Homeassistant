"""Sensors for SIMon mobile."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import Consumption, ConsumptionPackage
from .const import DOMAIN
from .coordinator import SimonMobileCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SIMon mobile sensors."""
    coordinator: SimonMobileCoordinator = entry.runtime_data
    known_package_keys: set[str] = set()

    async_add_entities(
        [
            SimonMobileTotalDataSensor(coordinator, entry),
            SimonMobileUsedDataSensor(coordinator, entry),
            SimonMobileRemainingDataSensor(coordinator, entry),
            SimonMobileUsagePercentSensor(coordinator, entry),
            SimonMobileExpirationSensor(coordinator, entry),
            SimonMobileSmsRemainingSensor(coordinator, entry),
        ]
    )

    @callback
    def _add_package_entities() -> None:
        new_entities: list[SimonMobilePackageRemainingSensor] = []
        for package, consumption in coordinator.data.by_type("DATA"):
            key = f"{package.id}_{consumption.type}"
            if key not in known_package_keys:
                known_package_keys.add(key)
                new_entities.append(
                    SimonMobilePackageRemainingSensor(
                        coordinator, entry, package, consumption
                    )
                )
        if new_entities:
            async_add_entities(new_entities)

    _add_package_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_package_entities))


class SimonMobileSensorBase(
    CoordinatorEntity[SimonMobileCoordinator], SensorEntity
):
    """Base class for SIMon mobile sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SimonMobileCoordinator,
        entry: ConfigEntry,
        key: str,
    ) -> None:
        """Initialize a sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._entry.unique_id))},
            name=self._entry.title,
            manufacturer="Vodafone GmbH",
            model="SIMon mobile",
            configuration_url="https://www.simonmobile.de/mein-simon/uebersicht",
        )

    def _data_items(self) -> list[tuple[ConsumptionPackage, Consumption]]:
        """Return all data-volume items."""
        return self.coordinator.data.by_type("DATA")


class SimonMobileTotalDataSensor(SimonMobileSensorBase):
    """Total available data allowance."""

    _attr_translation_key = "data_total"
    _attr_native_unit_of_measurement = "GB"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: SimonMobileCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "data_total")

    @property
    def native_value(self) -> float:
        """Return total data allowance."""
        return sum(item.maximum for _, item in self._data_items())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return allowance details."""
        return {
            "packages": [
                {
                    "name": package.name,
                    "package_type": package.package_type,
                    "consumed": item.consumed,
                    "remaining": item.left,
                    "total": item.maximum,
                    "unit": item.unit,
                    "expiration_date": (
                        item.expiration_date.isoformat()
                        if item.expiration_date
                        else None
                    ),
                    "display_separately": item.display_separately,
                }
                for package, item in self._data_items()
            ]
        }


class SimonMobileUsedDataSensor(SimonMobileSensorBase):
    """Used data allowance."""

    _attr_translation_key = "data_used"
    _attr_native_unit_of_measurement = "GB"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: SimonMobileCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "data_used")

    @property
    def native_value(self) -> float:
        """Return used data."""
        return sum(item.consumed for _, item in self._data_items())


class SimonMobileRemainingDataSensor(SimonMobileSensorBase):
    """Remaining data allowance."""

    _attr_translation_key = "data_remaining"
    _attr_native_unit_of_measurement = "GB"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: SimonMobileCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "data_remaining")

    @property
    def native_value(self) -> float:
        """Return remaining data."""
        return sum(item.left for _, item in self._data_items())


class SimonMobileUsagePercentSensor(SimonMobileSensorBase):
    """Used data as a percentage."""

    _attr_translation_key = "data_used_percent"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: SimonMobileCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "data_used_percent")

    @property
    def native_value(self) -> float:
        """Return used percentage."""
        maximum = sum(item.maximum for _, item in self._data_items())
        consumed = sum(item.consumed for _, item in self._data_items())
        return round(consumed / maximum * 100, 2) if maximum else 0


class SimonMobileExpirationSensor(SimonMobileSensorBase):
    """Next data allowance expiration."""

    _attr_translation_key = "next_expiration"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: SimonMobileCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "next_expiration")

    @property
    def native_value(self) -> datetime | None:
        """Return the earliest expiration."""
        dates = [
            item.expiration_date
            for _, item in self._data_items()
            if item.expiration_date is not None
        ]
        return min(dates) if dates else None


class SimonMobileSmsRemainingSensor(SimonMobileSensorBase):
    """Remaining SMS allowance."""

    _attr_translation_key = "sms_remaining"
    _attr_native_unit_of_measurement = "SMS"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SimonMobileCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "sms_remaining")

    @property
    def available(self) -> bool:
        """Return whether SMS data exists."""
        return super().available and bool(self.coordinator.data.by_type("SMS"))

    @property
    def native_value(self) -> float:
        """Return remaining SMS."""
        return sum(
            item.left for _, item in self.coordinator.data.by_type("SMS")
        )


class SimonMobilePackageRemainingSensor(SimonMobileSensorBase):
    """Remaining allowance for one tariff component."""

    _attr_native_unit_of_measurement = "GB"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: SimonMobileCoordinator,
        entry: ConfigEntry,
        package: ConsumptionPackage,
        consumption: Consumption,
    ) -> None:
        """Initialize the package sensor."""
        self._package_id = package.id
        self._consumption_type = consumption.type
        self._attr_name = f"{package.name} verbleibend"
        super().__init__(
            coordinator,
            entry,
            f"package_{package.id}_{consumption.type.lower()}_remaining",
        )

    def _current(self) -> tuple[ConsumptionPackage, Consumption] | None:
        """Return the current matching package."""
        return next(
            (
                (package, item)
                for package, item in self._data_items()
                if package.id == self._package_id
                and item.type == self._consumption_type
            ),
            None,
        )

    @property
    def available(self) -> bool:
        """Return whether the package still exists."""
        return super().available and self._current() is not None

    @property
    def native_value(self) -> float | None:
        """Return remaining package allowance."""
        current = self._current()
        return current[1].left if current else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return package details."""
        current = self._current()
        if not current:
            return {}
        package, item = current
        return {
            "package_type": package.package_type,
            "consumed": item.consumed,
            "total": item.maximum,
            "expiration_date": (
                item.expiration_date.isoformat() if item.expiration_date else None
            ),
        }

