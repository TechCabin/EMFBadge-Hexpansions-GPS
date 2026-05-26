""" L80K GPS App for Hexpansion"""
import app

from events.input import Buttons, BUTTON_TYPES, ButtonDownEvent, ButtonUpEvent
from system.eventbus import eventbus
from system.hexpansion.config import HexpansionConfig
from system.hexpansion.header import HexpansionHeader
from system.hexpansion.util import detect_eeprom_addr
from system.patterndisplay.events import PatternDisable, PatternEnable
from system.scheduler.events import RequestForegroundPopEvent, RequestForegroundPushEvent, RequestStopAppEvent
from tildagonos import tildagonos
from machine import I2C, UART, Pin
import time

# TODO: Replace this temporary development/pre-production PID with the
# final production PID (or load it from board metadata/config) once the
# production Hexpansion boards are finalized.
HEXPANSION_PID = 0x1295
DEFAULT_PORT = 3

# Hardware definitions:
TX_PIN  = 0    # HS_F for TX to GPS Module
RX_PIN  = 1    # HS_G for RX from GPS Module
RESET_PIN = 2  # HS_H for reset
PPS_PIN = 3    # HS_I for PPS


class L80KApp(app.App):         # pylint: disable=no-member
    def __init__(self, config: HexpansionConfig | None = None):
        super().__init__()

        self.VERSION = 1         # Increment this when making changes to the app that require the hexpansion app to be re-flashed with the new code.

        # If run from EEPROM on the hexpansion, the config will be passed in with the correct pin objects
        self.config: HexpansionConfig | None = config
        if config is None:
            # no config provided - search for hexpansion
            port = find_hexpansion_by_PID(HEXPANSION_PID)
            if port is not None:
                print("Found GPS hexpansion on port " + str(port))   
            else:
                print("No GPS hexpansion found, defaulting to port " + str(DEFAULT_PORT))
                port = DEFAULT_PORT 
            self.config = HexpansionConfig(port=port)

        self.tx_pin = self.config.pin[TX_PIN]
        self.rx_pin = self.config.pin[RX_PIN]

        self.button_states = Buttons(self)
        self.last_fix = None
        self.foreground = False

        # Event handlers for gaining and losing focus and for stopping the app
        eventbus.on_async(RequestStopAppEvent, self.handle_stop_app, self)
        eventbus.on_async(RequestForegroundPushEvent, self.on_resume, self)
        eventbus.on_async(RequestForegroundPopEvent, self.on_pause, self)

        self.uart = UART(1, baudrate=9600, tx=self.tx_pin, rx=self.rx_pin)
        self.reset = self.config.pin[RESET_PIN]
        self.reset.value(1)
        time.sleep_ms(100)
        self.reset.value(0)
        self.pps = self.config.pin[PPS_PIN]


    def deinit(self):
        """ Deinitialise the app, releasing any resources (e.g. UART) """
        self.uart.deinit()
        for hs_pin in self.config.pin:
            hs_pin.init(mode=Pin.IN)

    
    async def handle_stop_app(self, event: RequestStopAppEvent):
        """ Handle the RequestStopAppEvent so that we can release resources """
        if event.app == self:
            print("GPS: stopping app")
            self.deinit()


    async def on_resume(self, event: RequestForegroundPushEvent):
        """ Handle the RequestForegroundPushEvent to know when we gain focus """
        if event.app == self:
            print("GPS: resumed")
            eventbus.emit(PatternDisable())
            eventbus.on(ButtonDownEvent, self.handle_button_down, self)
            eventbus.on(ButtonUpEvent, self.handle_button_up, self)
            self.foreground = True


    async def on_pause(self, event: RequestForegroundPopEvent):
        """ Handle the RequestForegroundPopEvent to know when we lose focus """
        if event.app == self:
            print("GPS: paused")
            eventbus.emit(PatternEnable())
            eventbus.remove(ButtonDownEvent, self.handle_button_down, self)
            eventbus.remove(ButtonUpEvent, self.handle_button_up, self)


    def handle_button_down(self, event: ButtonDownEvent):
        """ Handle button down events """
        if BUTTON_TYPES["LEFT"] in event.button:
            print("Left Button Down")
            self.button_states.clear()

        if BUTTON_TYPES["RIGHT"] in event.button:
            print("Right Button Down")
            self.button_states.clear()

        if BUTTON_TYPES["DOWN"] in event.button:
            self.button_states.clear()

        if BUTTON_TYPES["CANCEL"] in event.button:
            self.button_states.clear()
            self.minimise()


    def handle_button_up(self, event: ButtonUpEvent):
        """ Handle button up events """
        if BUTTON_TYPES["LEFT"] in event.button:
            print("Left Button Up")
            self.button_states.clear()

        if BUTTON_TYPES["RIGHT"] in event.button:
            print("Right Button Up")
            self.button_states.clear()


    def update(self, delta):
        """ Update the app - this is called in the foreground and should contain the main logic of the app """
        if not self.foreground:
            # This triggers the automatic foreground display
            eventbus.emit(RequestForegroundPushEvent(self))
            self.foreground = True


    def background_update(self, delta):
        line = self.uart.readline()

        if line:
            print(line)
            try:
                line = line.decode().strip()

                result = parse_nmea_rmc(line)

                if result:
                    self.last_fix = result
                    print(result)

            except:
                pass


    def draw(self, ctx):
        ctx.rgb(0, 0.2, 0).rectangle(-120, -120, 240, 240).fill()
        ctx.rgb(0, 1, 0)

        if self.last_fix:
            ctx.move_to(-100, -10).text("Lat: " + str(round(self.last_fix["lat"], 5)))
            ctx.move_to(-100, 20).text("Lon: " + str(round(self.last_fix["lon"], 5)))
            for i in range(1, 13):
                tildagonos.leds[i] = (0, 10, 0)
                tildagonos.leds.write()
        else:
            ctx.move_to(-100, 0).text("Searching...")
            for i in range(1,13):
                tildagonos.leds[i] = (0,0,0)
                tildagonos.leds.write()


def find_hexpansion_by_PID(pid) -> int | None:
    """ Search for a hexpansion with the given PID and return its port number, or None if not found """
    for port in range(1, 7):
        i2c = I2C(port)
        # Autodetect eeprom addr and address length (some EEPROMs use 8-bit addressing, some use 16-bit)
        eeprom_addr, addr_len = detect_eeprom_addr(i2c)
        if addr_len is None or eeprom_addr is None:
            continue
        try:
            header_bytes = i2c.readfrom_mem(eeprom_addr, 0x00, 32, addrsize=8*addr_len)
            hexpansion_header = HexpansionHeader.from_bytes(header_bytes)
        except OSError:         # no hexpansion on this port
            continue
        except RuntimeError:    # blank EEPROM on this port
            continue
        except ValueError:      # invalid header data
            continue
        except Exception as e:  # Error reading header - could be a non-hexpansion device or a faulty hexpansion
            print(f"GPS:Error reading hexpansion header on port {port}: {e}")
            continue
        if hexpansion_header.pid == pid:
            return port
    return None


def parse_nmea_rmc(line):
    parts = line.split(',')

    if parts[0] not in ("$GNRMC", "$GPRMC"):
        return None
    elif parts[2] != "A":  # A = valid, V = invalid
        return None
    else:
        lat_raw = parts[3]
        lat_dir = parts[4]
        lon_raw = parts[5]
        lon_dir = parts[6]

        if not lat_raw or not lon_raw:
            return None

    # Convert to decimal degrees
        lat = float(lat_raw[:2]) + float(lat_raw[2:]) / 60
        lon = float(lon_raw[:3]) + float(lon_raw[3:]) / 60

        if lat_dir == "S":
            lat = -lat
        if lon_dir == "W":
            lon = -lon

        return {
            "lat": lat,
            "lon": lon
        }


__app_export__ = L80KApp
