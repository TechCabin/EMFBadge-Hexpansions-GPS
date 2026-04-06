import app

from events.input import Buttons, BUTTON_TYPES, ButtonDownEvent, ButtonUpEvent
from system.eventbus import eventbus
from tildagonos import tildagonos
from machine import UART,Pin
import time

class L80KApp(app.App):
    def __init__(self):
        self.button_states = Buttons(self)
        self.last_fix = None
        eventbus.on(ButtonDownEvent, self._handle_buttondown, self)
        eventbus.on(ButtonUpEvent, self._handle_buttonup, self)
        self.uart = UART(1, baudrate=9600, tx=Pin(34), rx = Pin(33))
        self.ubx_buffer = b""
        self.reset = Pin(47, Pin.OUT)
        self.reset.value(1)
        time.sleep(0.1)
        self.reset.value(0)
        self.pps = Pin(48, Pin.IN)


    def on_resume(self):
        print("resumed")
        eventbus.on(ButtonDownEvent, self._handle_buttondown, self)
        eventbus.on(ButtonUpEvent, self._handle_buttonup, self)

    def on_pause(self):
        print("paused")
        eventbus.remove(ButtonDownEvent, self._handle_buttondown, self)
        eventbus.remove(ButtonUpEvent, self._handle_buttonup, self)

    def _handle_buttondown(self, event: ButtonDownEvent):
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

    def _handle_buttonup(self, event: ButtonUpEvent):
        if BUTTON_TYPES["LEFT"] in event.button:
            print("Left Button Up")
            self.button_states.clear()

        if BUTTON_TYPES["RIGHT"] in event.button:
            print("Right Button Up")
            self.button_states.clear()

    def update(self, delta):
        pass

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