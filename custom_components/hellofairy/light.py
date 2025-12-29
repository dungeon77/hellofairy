""" light platform """
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.color import color_hs_to_RGB, color_RGB_to_hs

from .const import DOMAIN
from .hello_fairy import Lamp

if TYPE_CHECKING:
    from bleak.backends.device import BLEDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform from config_entry."""
    _LOGGER.debug(
        f"light async_setup_entry: setting up the config entry {config_entry.title} "
        f"with data:{config_entry.data}"
    )
    name = config_entry.data.get(CONF_NAME) or DOMAIN
    
    # Получаем BLE устройство
    ble_device = hass.data[DOMAIN][config_entry.entry_id]["ble_device"]
    
    # Создаем сущность
    entity = HelloFairyLight(name, ble_device, config_entry.entry_id)
    
    # Сохраняем ссылку на сущность для других платформ
    hass.data[DOMAIN][config_entry.entry_id]["light_entity"] = entity
    
    async_add_entities([entity])


class HelloFairyLight(LightEntity):
    """Representation of a Hello Fairy light."""

    def __init__(self, name: str, ble_device: BLEDevice, entry_id: str) -> None:
        """Initialize the light."""
        self._name = name
        self._mac = ble_device.address
        self._entry_id = entry_id
        self._attr_unique_id = self._mac
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._mac)},
            name=self._name,
            manufacturer="HelloFairy",
            model="Hello Fairy LED Strip",
        )

        self._is_on = False
        self._hs_color = (0.0, 100.0)  # Инициализация корректными значениями (красный)
        self._brightness = 255
        self._effect = None
        self._speed = 100
        self._direction = 0
        self._music_sensitivity = 50
        self._available = True

        _LOGGER.info(f"Initializing Hello Fairy Entity: {self._name}, {self._mac}")
        self._dev = Lamp(ble_device)
        
        # Регистрируем callback для обновлений состояния
        self._dev.add_callback_on_state_changed(self._state_changed)
        
        # Определяем поддерживаемые режимы цвета
        self._attr_supported_color_modes = {ColorMode.HS}
        self._attr_color_mode = ColorMode.HS
        self._attr_supported_features = LightEntityFeature.EFFECT

    def _state_changed(self) -> None:
        """Callback при изменении состояния устройства."""
        try:
            self._available = self._dev.available
            self._is_on = self._dev.is_on
            
            # Яркость из устройства (0-255)
            device_brightness = self._dev.brightness
            if device_brightness is not None:
                self._brightness = device_brightness
            
            # Цвет из устройства
            device_color = self._dev.color
            if device_color and device_color != (0, 0, 0):
                try:
                    self._hs_color = color_RGB_to_hs(*device_color)
                except Exception as e:
                    _LOGGER.debug(f"Error converting RGB to HS: {e}")
            
            self._effect = self._dev.current_effect
            self._speed = self._dev.speed
            self._direction = self._dev.direction
            self._music_sensitivity = self._dev.music_sensitivity
            
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Error in state_changed callback: {e}")

    @property
    def name(self) -> str:
        """Return the name of the light."""
        return self._name

    @property
    def available(self) -> bool:
        return self._available

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def brightness(self) -> int:
        return self._brightness

    @property
    def hs_color(self) -> tuple[float, float]:
        """Return the HS color value."""
        return self._hs_color

    @property
    def effect_list(self) -> list[str]:
        """Return the list of supported effects."""
        return self._dev.effect_list

    @property
    def effect(self) -> str | None:
        return self._effect

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "speed": self._speed,
            "direction": self._direction,
            "music_sensitivity": self._music_sensitivity,
            "mac_address": self._mac,
        }

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # Сохраняем ссылку на себя в hass.data
        if DOMAIN in self.hass.data and self._entry_id in self.hass.data[DOMAIN]:
            self.hass.data[DOMAIN][self._entry_id]["entities"] = self.hass.data[DOMAIN][self._entry_id].get("entities", {})
            self.hass.data[DOMAIN][self._entry_id]["entities"]["light"] = self
        
        # Обновляем состояние при добавлении
        self.async_schedule_update_ha_state(force_refresh=True)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        _LOGGER.debug("Running async_will_remove_from_hass")
        try:
            await self._dev.disconnect()
        except Exception:
            _LOGGER.debug(f"Exception disconnecting from {self._mac}", exc_info=True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        _LOGGER.debug(f"Turn on with kwargs: {kwargs}")

        # Включить сначала, если выключен
        if not self._is_on:
            await self._dev.turn_on()
            self._is_on = True
            await asyncio.sleep(0.1)

        # Установка цвета через палитру
        if ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]
            if hs_color is None:
                _LOGGER.error("hs_color is None!")
                return
                
            rgb = color_hs_to_RGB(*hs_color)
            
            # Яркость из kwargs или текущая
            brightness = kwargs.get(ATTR_BRIGHTNESS, self._brightness)
            brightness_percent = int((brightness / 255.0) * 100)
            
            # Ограничиваем значения
            r = max(0, min(255, rgb[0]))
            g = max(0, min(255, rgb[1]))
            b = max(0, min(255, rgb[2]))
            
            _LOGGER.debug(f"Setting RGB color: ({r}, {g}, {b}), brightness: {brightness_percent}%")
            
            success = await self._dev.set_color_rgb(r, g, b, brightness_percent)
            
            if success:
                self._hs_color = hs_color
                self._brightness = brightness
                self._effect = None  # Сбрасываем эффект при выборе цвета
            
            await asyncio.sleep(0.1)

        # Установка яркости
        elif ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            brightness_percent = int((brightness / 255.0) * 100)
            
            # Если цвет уже установлен, обновляем с текущим цветом
            if self._hs_color != (0.0, 0.0):
                rgb = color_hs_to_RGB(*self._hs_color)
                success = await self._dev.set_color_rgb(rgb[0], rgb[1], rgb[2], brightness_percent)
            else:
                # Иначе просто устанавливаем яркость (белый цвет)
                success = await self._dev.set_color_hsb(0, 0, brightness_percent)
            
            if success:
                self._brightness = brightness
            
            await asyncio.sleep(0.1)

        # Установка эффекта
        elif ATTR_EFFECT in kwargs:
            effect_name = kwargs[ATTR_EFFECT]
            _LOGGER.debug(f"Setting effect: {effect_name}")
            
            effect_data = self._dev._effects.get(effect_name)
            
            if effect_data:
                if effect_data.get("type") == "music":
                    # Музыкальный режим
                    success = await self._dev.set_music_mode(
                        effect_data["mode"].value, 
                        self._music_sensitivity
                    )
                else:
                    # Сцена
                    success = await self._dev.set_scene(
                        effect_data["category"].value,
                        effect_data["effect"],
                        self._speed,
                        self._direction
                    )
                
                if success:
                    self._effect = effect_name
                    # Сбрасываем цвет при установке эффекта
                    self._hs_color = (0.0, 0.0)
            
            await asyncio.sleep(0.1)

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._dev.turn_off()
        self._is_on = False
        self.async_write_ha_state()

    async def async_set_speed(self, speed: int) -> None:
        """Set scene speed."""
        await self._dev.set_speed(speed)
        self._speed = speed
        self.async_write_ha_state()

    async def async_set_direction(self, direction: int) -> None:
        """Set scroll direction."""
        await self._dev.set_direction(direction)
        self._direction = direction
        self.async_write_ha_state()

    async def async_set_music_sensitivity(self, sensitivity: int) -> None:
        """Set music sensitivity."""
        await self._dev.set_music_sensitivity(sensitivity)
        self._music_sensitivity = sensitivity
        self.async_write_ha_state()