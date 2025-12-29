"""Select platform for Hello Fairy."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .hello_fairy import Direction

_LOGGER = logging.getLogger(__name__)

DIRECTION_OPTIONS = {
    Direction.NONE: "None",
    Direction.UP: "Up",
    Direction.DOWN: "Down",
    Direction.LEFT: "Left",
    Direction.RIGHT: "Right",
    Direction.BLINK: "Blink",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Hello Fairy select."""
    entry_id = config_entry.entry_id
    
    if DOMAIN not in hass.data or entry_id not in hass.data[DOMAIN]:
        return
    
    entry_data = hass.data[DOMAIN][entry_id]
    
    # Получаем световую сущность
    light_entity = entry_data.get("light_entity")
    if not light_entity:
        _LOGGER.error("Light entity not found for entry %s", entry_id)
        return

    async_add_entities([HelloFairyDirectionSelect(light_entity)])


class HelloFairyDirectionSelect(SelectEntity):
    """Representation of a Hello Fairy direction select."""

    def __init__(self, light_entity) -> None:
        """Initialize the select."""
        self._light = light_entity
        self._attr_name = f"{light_entity.name} Scroll Direction"
        self._attr_unique_id = f"{light_entity._mac}_direction"
        self._attr_device_info = light_entity.device_info
        self._attr_options = list(DIRECTION_OPTIONS.values())
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def current_option(self) -> str | None:
        """Return the current option."""
        direction = self._light._direction
        return DIRECTION_OPTIONS.get(direction)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        # Найти ключ по значению
        for key, value in DIRECTION_OPTIONS.items():
            if value == option:
                await self._light.async_set_direction(key)
                break