"""Number platform for Hello Fairy."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import (
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hello Fairy numbers."""
    entry_id = config_entry.entry_id
    
    if DOMAIN not in hass.data or entry_id not in hass.data[DOMAIN]:
        return
    
    entry_data = hass.data[DOMAIN][entry_id]
    
    # Получаем световую сущность
    light_entity = entry_data.get("light_entity")
    if not light_entity:
        _LOGGER.error("Light entity not found for entry %s", entry_id)
        return

    numbers = [
        HelloFairySpeedNumber(light_entity),
        HelloFairySensitivityNumber(light_entity),
    ]
    
    async_add_entities(numbers)


class HelloFairySpeedNumber(NumberEntity):
    """Representation of a Hello Fairy speed number."""

    def __init__(self, light_entity) -> None:
        """Initialize the number."""
        self._light = light_entity
        self._attr_name = f"{light_entity.name} Speed"
        self._attr_unique_id = f"{light_entity._mac}_speed"
        self._attr_device_info = light_entity.device_info
        self._attr_native_min_value = 1
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_mode = NumberMode.SLIDER
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return float(self._light._speed)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self._light.async_set_speed(int(value))


class HelloFairySensitivityNumber(NumberEntity):
    """Representation of a Hello Fairy sensitivity number."""

    def __init__(self, light_entity) -> None:
        """Initialize the number."""
        self._light = light_entity
        self._attr_name = f"{light_entity.name} Music Sensitivity"
        self._attr_unique_id = f"{light_entity._mac}_sensitivity"
        self._attr_device_info = light_entity.device_info
        self._attr_native_min_value = 1
        self._attr_native_max_value = 100
        self._attr_native_step = 1
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_mode = NumberMode.SLIDER
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def native_value(self) -> float:
        """Return the current value."""
        return float(self._light._music_sensitivity)

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self._light.async_set_music_sensitivity(int(value))