# Basic GPS hexpansion application
# * allows universal slot usage using device and pin detection

# Experimental software for integrating with the GPS hexpansion module.
# Heavily butchered (almost unrecognisably) from the original reference software by
# John Lawrence the board's creator

# author: Gulraj Rijhwani (aka Camopants/ChocChip)
# This source released for free non-paid, strictly non-commercial use only

# Issues:
# Ideally, there should be board verification code during the selection process.
# Currently assumes the first EEPROM found is the right one, because the GPS module
# has no registered ID.
#
# Minimise pushes to background.  To be developed: there needs to be an complete exit
# action chain using the emit mechanism, and state-tracking to allow minimise to
# background or exit with confirmation.

import app

from events.input import Buttons, BUTTON_TYPES, ButtonDownEvent, ButtonUpEvent

from system.eventbus import eventbus
from system.hexpansion.events import HexpansionRemovalEvent, HexpansionInsertionEvent
from system.hexpansion.config import HexpansionConfig
from system.hexpansion.util import read_hexpansion_header, detect_eeprom_addr

from tildagonos import tildagonos

from machine import UART, Pin, I2C

import time

DEBUG = False

class NMEAreader():
    def __init__(self):
        self.__lat = 0
        self.__lon = 0
        self.__track = 0
        self.__speed = 0
        self.__satcount = None
        self.__is_valid = False
        self.__time = None
        self.__date = None
        self.__fix_was_valid = False

    @property
    def fix_valid(self):
        return self.__is_valid

    @property
    def last_fix(self):
        return {
            "valid": self.valid_fix,
            "lat": self.__lat,
            "lon": self.__lon,
            }

    @property
    def current_fix(self):
        if self.__is_valid:
            return {
                "lat": self.__lat,
                "lon": self.__lon,
                }
        else:
            return None

    @property
    def satcount(self):
        if self.__satcount is None:
            return None
        return self.__satcount

    @property
    def date(self):
        return str(self.__date)

    @property
    def time(self):
        return str(self.__time)

    @property
    def state(self):
        return {
            "valid": self.valid_fix,
            "lat": self.__lat,
            "lon": self.__lon,
            "sat": self.__satcount,
            "trk": self.__track,
            "spd": self.__speed,
            "time": self.__time,
            "date": self.__date
            }

    def parse_nmea(self, sentence):

        def validate_nmea(sentence):

            if sentence[0] != "$":
                raise ValueError(f'Invalid start char ("{sentence[0]}")')

            data, cksum = sentence.strip('\n').split('*', 1)
            d_cksum = int(cksum, 16)

            s_cksum = 0
            for c in data[1:]:
                s_cksum ^= ord(c)

            if d_cksum!=s_cksum:
                raise ValueError('Checksum failed')

            return data.split(',')

        def set_fix_valid(validity):
            self.__is_valid = bool(validity)
            if self.__is_valid:
                if not self.__fix_was_valid:
                    print('fix gained')
                    self.__fix_was_valid = True
            else:
                if self.__fix_was_valid:
                    print('fix lost')
                    self.__fix_was_valid = False

        def set_location(lat_raw, lat_dir, lon_raw, lon_dir):
            if lat_raw and lon_raw and lat_dir and lon_dir:
                self.__lat = float(lat_raw[:2]) + float(lat_raw[2:]) / 60
                self.__lon = float(lon_raw[:3]) + float(lon_raw[3:]) / 60

                if lat_dir == "S":
                    self.__lat = -self.__lat
                if lon_dir == "W":
                    self.__lon = -self.__lon

        # main parser
        if DEBUG:
            print(sentence)

        # validate checksum and deconstruct
        try:
            parts = validate_nmea(sentence)
        except:
            print(sentence)
            raise

        # needs to be a valid data source
        if not (sentence[1]=='G' and sentence[2] in ('P', 'L', 'A', 'N')):
            print(sentence)
            raise ValueError(f"Invalid talker ID ({sentence[1:3]})")

        # interpret
        tag = parts[0][3:]

        if DEBUG:
            print(f'\n{parts[1:]}')

        if tag == "RMC":
            self.__time = parts[1]
            self.__date = parts[9]
            set_fix_valid(parts[2] == "A")  # A = valid, V = invalid
            if self.fix_valid:
                set_location(parts[3], parts[4], parts[5], parts[6])
                print(f'  lat: {self.__lat}; lon: {self.__lon}')
            else:
                print(sentence)
        elif tag == "GSV":
            self.__satcount = int(parts[3])
        elif tag == "VTG":
            self.__track = parts[1]
            self.__speed = parts[7]
            if self.__is_valid:
                print(f'  trk: {self.__track}; sp: {self.__speed}')
        elif tag == "GGA":
            self.__time = parts[1]
            set_fix_valid(parts[6] == "1" or parts[6] == "2")  # 1 = GPS, 2 = DGPS
            if self.fix_valid:
                set_location(parts[2], parts[3], parts[4], parts[5])
                print(f'  lat: {self.__lat}; lon: {self.__lon}')
        elif tag == "GLL":
            self.__time = parts[5]
            set_fix_valid(parts[6] == "A")  # A = valid, V = invalid
            if self.fix_valid:
                set_location(parts[1], parts[2], parts[3], parts[4])
                print(f'  lat: {self.__lat}; lon: {self.__lon}')
        else:
            pass

        return



class TildagonGPS(app.App):
    def __init__(self):
        print('initial page')
        self.__page = 0

        print('capture button control')
        self.__button_states = Buttons(self)
        eventbus.on(ButtonDownEvent, self.__buttonhandler_down, self)
        eventbus.on(ButtonUpEvent, self.__buttonhandler_up, self)

        print('scan for hexpansion')
        msg, port, self.__hexpansion_config = self.__scan_for_hexpansion()
        print(msg)
        if self.__hexpansion_config is None:
            raise ValueError('Invalid configuration')
        print(self.__hexpansion_config)
        attrs = [l for l in dir(self.__hexpansion_config) if l[0]!='_']
        print(attrs)
        for l in attrs:
            print(f'{l}: {getattr(self.__hexpansion_config, l)}')

        self.__set_uart(speed=9600)

        print('init message buffer')
        self.__buffer = b''
        self.__tracker = NMEAreader()

        print('reset')
        self.__reset_gps()

        self.__led = 0
        print('init complete')

    def __scan_for_hexpansion(self):
        msg = "No hexpansion found"
        for port in range(1, 7):
            print(f'Searching for hexpansion on port: {port}')
            i2c = I2C(port)
            addr, addr_len = detect_eeprom_addr(i2c) # Firmware version 1.8 and upwards only!

            if addr is None:
                continue
            else:
                if DEBUG:
                    print("Found EEPROM at addr " + hex(addr))

            header = read_hexpansion_header(i2c, addr, addr_len=addr_len)
            if header is None:
                msg = "Hexpansion found.\nat port: {}\n(invalid header)".format(port)
            else:
                print("Read header: " + str(header))
                msg = "Hexpansion found.\nat port: {}\nvid: {}\npid: {}".format(port, hex(header.vid), hex(header.pid))
                # this is where the board discrimination code should be
            return msg, port, HexpansionConfig(port)
        return msg, port, None

    def on_resume(self):
        print("resumed")
        eventbus.on(ButtonDownEvent, self.__buttonhandler_down, self)
        eventbus.on(ButtonUpEvent, self.__buttonhandler_up, self)


    def on_pause(self):
        print("paused")
        eventbus.remove(ButtonDownEvent, self.__buttonhandler_down, self)
        eventbus.remove(ButtonUpEvent, self.__buttonhandler_up, self)

    #def __set_uart(self, port):
    def __set_uart(self, uart=1, speed=115200):

        print('UART config')
        tx_pin, rx_pin, rst_pin, pps_pin = self.__hexpansion_config.pin
        print(f'tx: {tx_pin}, rx: {rx_pin}, reset: {rst_pin}, pps: {pps_pin}')

        # serial configuration
        self.__uart = UART(uart, baudrate=speed, tx=Pin(tx_pin), rx = Pin(rx_pin))
        self.__reset = Pin(rst_pin, Pin.OUT)
        self.__pps = Pin(pps_pin, Pin.IN)

    def __reset_gps(self):
        self.__reset.value(1)
        time.sleep(0.1)
        self.__reset.value(0)
        time.sleep(0.1)

    # button handlers
    def __buttonhandler_down(self, event: ButtonDownEvent):

        if BUTTON_TYPES["CANCEL"] in event.button:
            print("CANCEL pressed - should exit")
            self.__button_states.clear()
            self.minimise()

        if BUTTON_TYPES["LEFT"] in event.button:
            print("Left button pressed - page left")
            self.__page = (self.__page - 1)%2

        if BUTTON_TYPES["RIGHT"] in event.button:
            print("Right button pressed - page right")
            self.__page = (self.__page + 1)%2

        if BUTTON_TYPES["UP"] in event.button:
            print("UP button pressed - reset GPS")
            self.__reset_gps()

        #if BUTTON_TYPES["DOWN"] in event.button:
        #    print("Down button pressed")

        #if BUTTON_TYPES["CONFIRM"] in event.button:
        #    print("CONFIRM button pressed")

        self.__button_states.clear()


    def __buttonhandler_up(self, event: ButtonUpEvent):
        if BUTTON_TYPES["CANCEL"] in event.button:
            print("CANCEL button released - how did we get here?")

        #if BUTTON_TYPES["LEFT"] in event.button:
        #    print("Left button released")

        #if BUTTON_TYPES["RIGHT"] in event.button:
        #    print("Right button released")

        #if BUTTON_TYPES["UP"] in event.button:
        #    print("UP button released")

        #if BUTTON_TYPES["DOWN"] in event.button:
        #    print("Down button released")

        #if BUTTON_TYPES["CONFIRM"] in event.button:
        #    print("CONFIRM button released")

        self.__button_states.clear()


    def update(self, delta):
        pass


    def background_update(self, delta):
        # This ensures messages get priority, but it interferes with wider
        # process scheduling.
        while True:
            #print(".", end='')
            # if there is input waiting buffer it
            try:
                self.__buffer += self.__uart.readline()
                #print("\b+", end='')
            except:
                pass

            # if we have a complete line, extract it and truncate the buffer
            # otherwise disregard
            try:
                i = self.__buffer.index(b'\n') + 1
                #print("m")
            except Exception as e:
                return

            # extract a processable message
            try:
                line = self.__buffer[:i].decode().strip()
                #print(f'line: {str(len(line))}')
            except Exception as e:
                print(e)
                #return
            self.__buffer = self.__buffer[i:]

            # parse and process it
            try:
                self.__tracker.parse_nmea(line)
            except Exception as e:
                print(e)


    def draw(self, ctx):
        ctx.save()
        f = self.__tracker.current_fix
        bg = (0, 0, 0)

        l = [None for i in range(4)]
        l[0] = f'Sats: {str(self.__tracker.satcount)}'
        if f:
            fg = (0, 1.0, 0)
            leds = (0, 127, 0)
            if self.__page==1:
                d = self.__tracker.date
                t = self.__tracker.time
                try:
                    if self.__lastt==t and self.__lastd==d and len(self.__buffer)==0:
                        return
                except:
                    pass
                l[1] = f'Date: {d[0:2]}-{d[2:4]}-{d[4:6]}'
                l[2] = f'Time: {t[0:2]}:{t[2:4]}:{t[4:6]}'
                self.__lastt=t
                self.__lastd=d
            else:
                l[1] = f'Lat: {round(f["lat"], 5)}'
                l[2] = f'Lon: {round(f["lon"], 5)}'
        else:
            fg = (1.0, 0, 0)
            leds = (127, 0, 0)
            l[1] = "Searching..."

            self.__led = (self.__led % 12) + 1
            tildagonos.leds[self.__led] = leds
            tildagonos.leds.write()

        l[3] = f'Buffer: {len(self.__buffer)}'

        #for i in range(1,13):
        #    tildagonos.leds[i] = leds

        ctx.rgb(*bg).rectangle(-120, -120, 240, 240).fill()
        y = -40
        for t in l:
            if t:
                ctx.move_to(-100, y).rgb(*fg).text(t)
            y += 30

        ctx.restore()


__app_export__ = TildagonGPS