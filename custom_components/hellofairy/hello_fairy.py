# Standard imports
import asyncio
import enum
import logging
import colorsys
from typing import Any, Callable, cast

# 3rd party imports
from bleak import BleakClient, BleakError, BleakScanner
from bleak.backends.client import BaseBleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection

CONTROL_UUID = "49535343-8841-43f4-a8d4-ecbe34729bb3"

class Conn(enum.Enum):
    DISCONNECTED = 1
    UNPAIRED = 2
    PAIRING = 3
    PAIRED = 4

class Direction(enum.IntEnum):
    NONE = 0x00
    UP = 0x01
    DOWN = 0x02
    LEFT = 0x03
    RIGHT = 0x04
    BLINK = 0x05

class MusicMode(enum.IntEnum):
    ENERGY = 0x11
    RHYTHM = 0x21
    BALL = 0x31
    SPECTRUM = 0x41

class SceneCategory(enum.IntEnum):
    NEW_YEAR = 0x01
    HALLOWEEN = 0x02
    EASTER = 0x03
    HEARTS = 0x04
    DUCKS = 0x05
    PLANTS = 0x06
    FLAGS = 0x07
    CARNIVAL = 0x08
    RELIGION = 0x09
    FAMILY = 0x0A
    ANIMALS = 0x0C
    ELECTRONICS = 0x0D
    FIREWORKS = 0x0E
    HOUSE = 0x0F
    DATE_TIME = 0x0D

_LOGGER = logging.getLogger(__name__)

class Lamp:
    """The class that represents a Hello Fairy lamp"""

    def __init__(self, ble_device: BLEDevice):
        self._client: BleakClient | None = None
        self._ble_device = ble_device
        self._mac = self._ble_device.address
        _LOGGER.debug(f"Initializing Hello Fairy Lamp {self._ble_device.name} ({self._mac})")
        
        self._is_on = False
        self._rgb = (0, 0, 0)
        self._brightness = 100
        self._effect = None
        self._speed = 100
        self._direction = Direction.NONE
        self._music_sensitivity = 50
        self._music_mode = None
        self._scene_category = None
        self._scene_effect = None
        
        self._state_callbacks: list[Callable[[], None]] = []
        self._conn = Conn.DISCONNECTED
        self._pair_resp_event = asyncio.Event()
        self._read_service = False
        self._is_client_bluez = True

        # Полный список эффектов из вашего json
        self._effects = {
            # Новый год (01)
            "new_year_santa_reindeer": {"category": SceneCategory.NEW_YEAR, "effect": 1},
            "new_year_snow": {"category": SceneCategory.NEW_YEAR, "effect": 2},
            "new_year_sock": {"category": SceneCategory.NEW_YEAR, "effect": 3},
            "new_year_santa": {"category": SceneCategory.NEW_YEAR, "effect": 4},
            "new_year_tree": {"category": SceneCategory.NEW_YEAR, "effect": 5},
            "new_year_candle": {"category": SceneCategory.NEW_YEAR, "effect": 6},
            
            # Хэллоуин (02)
            "halloween_pumpkin": {"category": SceneCategory.HALLOWEEN, "effect": 1},
            "halloween_transparent_pumpkin": {"category": SceneCategory.HALLOWEEN, "effect": 2},
            "halloween_spider": {"category": SceneCategory.HALLOWEEN, "effect": 3},
            "halloween_ghost": {"category": SceneCategory.HALLOWEEN, "effect": 4},
            "halloween_ghost2": {"category": SceneCategory.HALLOWEEN, "effect": 5},
            "halloween_cat": {"category": SceneCategory.HALLOWEEN, "effect": 6},
            
            # Пасха (03)
            "easter_egg": {"category": SceneCategory.EASTER, "effect": 1},
            "easter_egg2": {"category": SceneCategory.EASTER, "effect": 2},
            "easter_flying_chubs": {"category": SceneCategory.EASTER, "effect": 3},
            "easter_basket": {"category": SceneCategory.EASTER, "effect": 4},
            "easter_chubs": {"category": SceneCategory.EASTER, "effect": 5},
            
            # Сердечки (04)
            "hearts_flower": {"category": SceneCategory.HEARTS, "effect": 1},
            "hearts_hearts": {"category": SceneCategory.HEARTS, "effect": 2},
            "hearts_big_heart": {"category": SceneCategory.HEARTS, "effect": 3},
            "hearts_tetris_heart": {"category": SceneCategory.HEARTS, "effect": 4},
            "hearts_heart_arrow": {"category": SceneCategory.HEARTS, "effect": 5},
            
            # Утки (05)
            "ducks_duck1": {"category": SceneCategory.DUCKS, "effect": 1},
            "ducks_duck2": {"category": SceneCategory.DUCKS, "effect": 2},
            "ducks_duck3": {"category": SceneCategory.DUCKS, "effect": 3},
            "ducks_duck4": {"category": SceneCategory.DUCKS, "effect": 4},
            "ducks_duck5": {"category": SceneCategory.DUCKS, "effect": 5},
            
            # Растения (06)
            "plants_flower1": {"category": SceneCategory.PLANTS, "effect": 1},
            "plants_watering_can": {"category": SceneCategory.PLANTS, "effect": 2},
            "plants_mug": {"category": SceneCategory.PLANTS, "effect": 3},
            "plants_flower2": {"category": SceneCategory.PLANTS, "effect": 4},
            "plants_mug2": {"category": SceneCategory.PLANTS, "effect": 5},
            
            # Флаги (07)
            "flags_usa": {"category": SceneCategory.FLAGS, "effect": 1},
            "flags_france": {"category": SceneCategory.FLAGS, "effect": 3},
            "flags_australia": {"category": SceneCategory.FLAGS, "effect": 4},
            "flags_germany": {"category": SceneCategory.FLAGS, "effect": 5},
            "flags_canada": {"category": SceneCategory.FLAGS, "effect": 6},
            "flags_spain": {"category": SceneCategory.FLAGS, "effect": 7},
            "flags_britain": {"category": SceneCategory.FLAGS, "effect": 8},
            "flags_italy": {"category": SceneCategory.FLAGS, "effect": 9},
            "flags_japan": {"category": SceneCategory.FLAGS, "effect": 10},
            
            # Карнавал (08)
            "carnival_mask": {"category": SceneCategory.CARNIVAL, "effect": 1},
            "carnival_balls": {"category": SceneCategory.CARNIVAL, "effect": 2},
            "carnival_harlequin": {"category": SceneCategory.CARNIVAL, "effect": 3},
            "carnival_harlequin2": {"category": SceneCategory.CARNIVAL, "effect": 4},
            "carnival_clown": {"category": SceneCategory.CARNIVAL, "effect": 5},
            "carnival_balls2": {"category": SceneCategory.CARNIVAL, "effect": 6},
            
            # Религия (09)
            "religion1": {"category": SceneCategory.RELIGION, "effect": 1},
            "religion2": {"category": SceneCategory.RELIGION, "effect": 2},
            "religion3": {"category": SceneCategory.RELIGION, "effect": 3},
            "religion4": {"category": SceneCategory.RELIGION, "effect": 4},
            
            # Семья (0A)
            "family1": {"category": SceneCategory.FAMILY, "effect": 1},
            "family2": {"category": SceneCategory.FAMILY, "effect": 2},
            "family3": {"category": SceneCategory.FAMILY, "effect": 3},
            "family4": {"category": SceneCategory.FAMILY, "effect": 4},
            "family5": {"category": SceneCategory.FAMILY, "effect": 5},
            
            # Животные (0C)
            "animals_dino": {"category": SceneCategory.ANIMALS, "effect": 1},
            "animals_turtle": {"category": SceneCategory.ANIMALS, "effect": 2},
            "animals_elephant": {"category": SceneCategory.ANIMALS, "effect": 3},
            "animals_deer": {"category": SceneCategory.ANIMALS, "effect": 4},
            
            # Электроника (0D)
            "electronics_professor": {"category": SceneCategory.ELECTRONICS, "effect": 1},
            "electronics_astronaut": {"category": SceneCategory.ELECTRONICS, "effect": 2},
            "electronics_rocket": {"category": SceneCategory.ELECTRONICS, "effect": 3},
            "electronics_datetime": {"category": SceneCategory.ELECTRONICS, "effect": 4},
            "electronics_timer": {"category": SceneCategory.ELECTRONICS, "effect": 5},
            "electronics_color_change": {"category": SceneCategory.ELECTRONICS, "effect": 6},
            "electronics_paint_rain": {"category": SceneCategory.ELECTRONICS, "effect": 7},
            "electronics_glare": {"category": SceneCategory.ELECTRONICS, "effect": 8},
            "electronics_colors": {"category": SceneCategory.ELECTRONICS, "effect": 9},
            "electronics_palette": {"category": SceneCategory.ELECTRONICS, "effect": 10},
            "electronics_tunnel": {"category": SceneCategory.ELECTRONICS, "effect": 11},
            "electronics_tunnel2": {"category": SceneCategory.ELECTRONICS, "effect": 12},
            "electronics_tunnel3": {"category": SceneCategory.ELECTRONICS, "effect": 13},
            "electronics_tunnel4": {"category": SceneCategory.ELECTRONICS, "effect": 14},
            "electronics_palette2": {"category": SceneCategory.ELECTRONICS, "effect": 15},
            "electronics_windmill": {"category": SceneCategory.ELECTRONICS, "effect": 16},
            "electronics_shutter": {"category": SceneCategory.ELECTRONICS, "effect": 17},
            "electronics_3d_palette": {"category": SceneCategory.ELECTRONICS, "effect": 18},
            "electronics_countdown": {"category": SceneCategory.ELECTRONICS, "effect": 20},
            "electronics_heart": {"category": SceneCategory.ELECTRONICS, "effect": 21},
            "electronics_diamond": {"category": SceneCategory.ELECTRONICS, "effect": 22},
            "electronics_rain2": {"category": SceneCategory.ELECTRONICS, "effect": 23},
            "electronics_4spheres": {"category": SceneCategory.ELECTRONICS, "effect": 24},
            "electronics_universe": {"category": SceneCategory.ELECTRONICS, "effect": 25},
            "electronics_kaleidoscope": {"category": SceneCategory.ELECTRONICS, "effect": 26},
            "electronics_kaleidoscope2": {"category": SceneCategory.ELECTRONICS, "effect": 27},
            "electronics_flight": {"category": SceneCategory.ELECTRONICS, "effect": 28},
            
            # Салюты (0E)
            "fireworks_countdown": {"category": SceneCategory.FIREWORKS, "effect": 1},
            "fireworks_firework": {"category": SceneCategory.FIREWORKS, "effect": 2},
            "fireworks_firework2": {"category": SceneCategory.FIREWORKS, "effect": 3},
            "fireworks_salute": {"category": SceneCategory.FIREWORKS, "effect": 4},
            "fireworks_icecream": {"category": SceneCategory.FIREWORKS, "effect": 5},
            "fireworks_fire": {"category": SceneCategory.FIREWORKS, "effect": 6},
            "fireworks_snowdrift": {"category": SceneCategory.FIREWORKS, "effect": 7},
            "fireworks_skittles": {"category": SceneCategory.FIREWORKS, "effect": 8},
            
            # Дом (0F)
            "house_person": {"category": SceneCategory.HOUSE, "effect": 1},
            "house_sail": {"category": SceneCategory.HOUSE, "effect": 2},
            "house_tag": {"category": SceneCategory.HOUSE, "effect": 3},
            "house_shop": {"category": SceneCategory.HOUSE, "effect": 4},
            "house_bubbles": {"category": SceneCategory.HOUSE, "effect": 5},
            "house_worm": {"category": SceneCategory.HOUSE, "effect": 6},
            "house_dollar": {"category": SceneCategory.HOUSE, "effect": 7},
            
            # Музыкальные режимы
            "music_energy": {"mode": MusicMode.ENERGY, "type": "music"},
            "music_rhythm": {"mode": MusicMode.RHYTHM, "type": "music"},
            "music_ball": {"mode": MusicMode.BALL, "type": "music"},
            "music_spectrum": {"mode": MusicMode.SPECTRUM, "type": "music"},
        }

    def __str__(self) -> str:
        return f"<Lamp {self._mac} {'ON' if self._is_on else 'OFF'} bri_{self._brightness} rgb_{self._rgb}>"

    def add_callback_on_state_changed(self, func: Callable[[], None]) -> None:
        self._state_callbacks.append(func)

    def run_state_changed_cb(self) -> None:
        for func in self._state_callbacks:
            func()

    def diconnected_cb(self, client: BaseBleakClient) -> None:
        _LOGGER.debug(f"Disconnected CB from client {client}")
        self._conn = Conn.DISCONNECTED
        self.run_state_changed_cb()

    async def connect(self, num_tries: int = 3) -> None:
        if self._client and not self._client.is_connected:
            await self.disconnect()
        if self._conn == Conn.PAIRING or self._conn == Conn.PAIRED:
            return
            
        _LOGGER.debug("Initiating new connection")
        try:
            if self._client:
                await self.disconnect()

            _LOGGER.debug(f"Connecting now to {self._ble_device}:...")
            self._client = await establish_connection(
                BleakClient,
                device=self._ble_device,
                name=self._mac,
                disconnected_callback=self.diconnected_cb,
                max_attempts=4,
            )
            self._conn = Conn.PAIRED
            _LOGGER.debug(f"Connected: {self._client.is_connected}")
            
            # Реклама HA, что лампа доступна
            self.run_state_changed_cb()

        except asyncio.TimeoutError:
            _LOGGER.error("Connection Timeout error")
        except BleakError as err:
            _LOGGER.error(f"Connection: BleakError: {err}")

    async def disconnect(self) -> None:
        if self._client is None:
            return
        try:
            await self._client.disconnect()
        except asyncio.TimeoutError:
            _LOGGER.error("Disconnection: Timeout error")
        except BleakError as err:
            _LOGGER.error(f"Disconnection: BleakError: {err}")
        self._conn = Conn.DISCONNECTED

    def calculate_checksum(self, data_bytes):
        """Вычисляет XOR контрольную сумму"""
        checksum = 0
        for b in data_bytes:
            checksum ^= b
        return checksum

    async def send_command(self, payload):
        """Отправляет команду с контрольной суммой"""
        checksum = self.calculate_checksum(payload)
        command = bytes(list(payload) + [checksum])
        
        await self.connect()
        if self._conn == Conn.PAIRED and self._client is not None:
            try:
                await self._client.write_gatt_char(CONTROL_UUID, bytearray(command))
                await asyncio.sleep(0.3)
                return True
            except asyncio.TimeoutError:
                _LOGGER.error("Send Cmd: Timeout error")
            except BleakError as err:
                _LOGGER.error(f"Send Cmd: BleakError: {err}")
        return False

    async def turn_on(self) -> None:
        bits = bytes([0xaa, 0x02, 0x01, 0x01])
        _LOGGER.debug("Send Cmd: Turn On")
        if await self.send_command(bits):
            self._is_on = True

    async def turn_off(self) -> None:
        bits = bytes([0xaa, 0x02, 0x01, 0x00])
        _LOGGER.debug("Send Cmd: Turn Off")
        if await self.send_command(bits):
            self._is_on = False

    async def set_color_hsb(self, hue: float, saturation: float, brightness: float) -> None:
        """
        Установить цвет в формате HSB
        hue: 0-360 градусов
        saturation: 0-100%
        brightness: 0-100%
        """
        # Конвертируем значения
        h_val = int((hue / 360.0) * 511)
        h_val = min(max(0, h_val), 511)
        
        s_val = int((saturation / 100.0) * 1000)
        b_val = int((brightness / 100.0) * 1000)
        s_val = min(max(0, s_val), 1000)
        b_val = min(max(0, b_val), 1000)
        
        # Разделяем на байты
        h_high, h_low = divmod(h_val, 256)
        s_high, s_low = divmod(s_val, 256)
        b_high, b_low = divmod(b_val, 256)
        
        payload = bytes([0xaa, 0x03, 0x07, 0x01, h_high, h_low,
                        s_high, s_low,
                        b_high, b_low])
        
        _LOGGER.debug(f"Set color HSB: H={hue}, S={saturation}, B={brightness}")
        _LOGGER.debug(f"Command bytes: {payload.hex()}")
        
        if await self.send_command(payload):
            # Конвертируем HSB в RGB для хранения
            r, g, b = [int(x * 255) for x in colorsys.hsv_to_rgb(hue/360, saturation/100, brightness/100)]
            self._rgb = (r, g, b)
            self._brightness = int((brightness / 100.0) * 255)
            self._effect = None  # Сбрасываем эффект при выборе цвета
            return True
        return False

    async def set_color_rgb(self, red: int, green: int, blue: int, brightness: int = None) -> None:
        """Установить цвет RGB"""
        if brightness is None:
            brightness = 100
        else:
            # brightness передается 0-100%
            brightness = max(0, min(100, brightness))
        
        _LOGGER.debug(f"Setting RGB: R={red}, G={green}, B={blue}, Brightness={brightness}%")
        
        # Конвертируем RGB в HSV
        r_norm = red / 255.0
        g_norm = green / 255.0
        b_norm = blue / 255.0
        
        # Находим максимум и минимум
        cmax = max(r_norm, g_norm, b_norm)
        cmin = min(r_norm, g_norm, b_norm)
        delta = cmax - cmin
        
        # Вычисляем Hue
        if delta == 0:
            h = 0
        elif cmax == r_norm:
            h = 60 * (((g_norm - b_norm) / delta) % 6)
        elif cmax == g_norm:
            h = 60 * (((b_norm - r_norm) / delta) + 2)
        else:  # cmax == b_norm
            h = 60 * (((r_norm - g_norm) / delta) + 4)
        
        # Вычисляем Saturation
        s = 0 if cmax == 0 else (delta / cmax)
        
        # Hue в диапазоне 0-360
        hue = h % 360
        saturation = s * 100
        value = cmax * 100  # Value из HSV
        
        _LOGGER.debug(f"Converted to HSV: H={hue:.1f}, S={saturation:.1f}%, V={value:.1f}%")
        
        # Учитываем яркость
        actual_brightness = brightness * (value / 100.0)
        
        _LOGGER.debug(f"Final HSB for device: H={hue:.1f}, S={saturation:.1f}%, B={actual_brightness:.1f}%")
        
        success = await self.set_color_hsb(hue, saturation, actual_brightness)
        
        if success:
            # Сохраняем цвет
            self._rgb = (red, green, blue)
            self._brightness = int((brightness / 100.0) * 255)
        
        return success

    async def set_scene(self, category: int, effect: int, speed: int = 100, direction: int = Direction.NONE) -> None:
        """Установить сцену"""
        speed_val = min(max(1, speed), 100)
        payload = bytes([
            0xaa, 0xd8, 0x05,
            category, effect,
            speed_val, direction,
            0x64
        ])
        
        _LOGGER.debug(f"Set scene: category={category}, effect={effect}, speed={speed}, direction={direction}")
        if await self.send_command(payload):
            self._scene_category = category
            self._scene_effect = effect
            self._speed = speed_val
            self._direction = direction
            self._effect = f"scene_{category}_{effect}"
            # Сбрасываем цвет при установке сцены
            self._rgb = (0, 0, 0)
            return True
        return False

    async def set_music_mode(self, mode: int, sensitivity: int = 50) -> None:
        """Установить музыкальный режим"""
        sensitivity_val = min(max(1, sensitivity), 100)
        payload = bytes([
            0xaa, 0x03, 0x09, 0x03,
            mode, sensitivity_val,
            0x03, 0xe8, 0x00, 0x00, 0x03, 0xe8
        ])
        
        _LOGGER.debug(f"Set music mode: mode={mode}, sensitivity={sensitivity}")
        if await self.send_command(payload):
            self._music_mode = mode
            self._music_sensitivity = sensitivity_val
            self._effect = f"music_{mode}"
            # Сбрасываем цвет при установке музыкального режима
            self._rgb = (0, 0, 0)
            return True
        return False

    async def set_speed(self, speed: int) -> None:
        """Установить скорость для текущей сцены"""
        if self._scene_category and self._scene_effect:
            await self.set_scene(self._scene_category, self._scene_effect, speed, self._direction)
        self._speed = speed

    async def set_direction(self, direction: int) -> None:
        """Установить направление прокрутки"""
        if self._scene_category and self._scene_effect:
            await self.set_scene(self._scene_category, self._scene_effect, self._speed, direction)
        self._direction = direction

    async def set_music_sensitivity(self, sensitivity: int) -> None:
        """Установить чувствительность музыкального режима"""
        if self._music_mode:
            await self.set_music_mode(self._music_mode, sensitivity)
        self._music_sensitivity = sensitivity

    @property
    def mac(self) -> str:
        return self._mac

    @property
    def available(self) -> bool:
        return self._conn == Conn.PAIRED

    @property
    def is_on(self) -> bool:
        return self._is_on

    @property
    def brightness(self) -> int:
        return self._brightness

    @property
    def color(self) -> tuple[int, int, int]:
        return self._rgb

    @property
    def effect_list(self) -> list[str]:
        return list(self._effects.keys())

    @property
    def current_effect(self) -> str:
        return self._effect

    @property
    def speed(self) -> int:
        return self._speed

    @property
    def direction(self) -> int:
        return self._direction

    @property
    def music_sensitivity(self) -> int:
        return self._music_sensitivity

    def get_prop_min_max(self) -> dict[str, Any]:
        return {
            "brightness": {"min": 0, "max": 255},
            "speed": {"min": 1, "max": 100},
            "sensitivity": {"min": 1, "max": 100},
        }

async def discover_hello_fairy_lamps(
    scanner: type[BleakScanner] | None = None,
) -> list[dict[str, Any]]:
    """Сканирование устройств Hello Fairy"""
    lamp_list = []
    scanner = scanner if scanner is not None else BleakScanner

    devices = await scanner.discover()
    for d in devices:
        lamp_list.append({"ble_device": d})
        _LOGGER.info(f"found {d.name} with mac: {d.address}, details:{d.details}")
    return lamp_list