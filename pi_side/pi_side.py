import json
import socket
import sys
from gpiozero import LED, PWMLED
from time import sleep
from random import randint
from threading import Thread
import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    "-d",
    "--debug_display",
    help="Enables a debug display on a 20x4 LCD display on the I2C bus.\n"
         "This will take over control of pins 3 & 5 (GPIO 2 & 3).",
    action="store_true"
)
args = parser.parse_args()

DEBUG_DISPLAY = args.debug_display

if DEBUG_DISPLAY:
    from RPi_GPIO_i2c_LCD import lcd
    LCD_ADDR = 0x27
    DISPLAY = lcd.HD44780(LCD_ADDR)
    DISPLAY.backlight("on")
    DISPLAY.clear()

RUN = True


class DynamicLights:
    def __init__(self, lights, mode="random", parent=None):
        self.parent = parent
        self.lights = lights
        self.is_active = False
        self.run_thread = None
        self.__mode = ""
        self.__keep_running = True
        if mode == "random":
            self.set_random()
        else:
            self.set_static()

    @property
    def is_lit(self):
        return self.is_active

    def on(self):
        self.is_active = True
        for led in self.lights:
            if self.__mode == "static" or randint(0, 1):  # Turn on all lights if mode is static, else random.
                led.on()

    def off(self):
        self.is_active = False
        for led in self.lights:
            led.off()

    def __run(self):
        while self.__keep_running:
            if self.is_active:
                while self.is_active and self.__keep_running:
                    self.lights[randint(0, len(self.lights) - 1)].toggle()
                    if self.parent is not None:
                        self.parent.update_screen()
                    sleep(randint(0, 50) / 10)
            else:
                sleep(1)

    def set_random(self):
        self.__mode = "random"
        self.__keep_running = True
        self.run_thread = Thread(target=self.__run)
        self.run_thread.daemon = True
        self.run_thread.start()

    def set_static(self):
        self.__mode = "static"
        self.__keep_running = False
        if self.is_lit:
            self.on()

    @property
    def mode(self):
        return self.__mode


class CustomPWMLED(PWMLED):
    def __init__(self, *args):
        super().__init__(*args)
        self.pulsing = False

    def custom_pulse(self, fade_in_time=1.0, fade_out_time=1.0, lower_limit=0.0, upper_limit=1.0, background=True):
        if background:
            t = Thread(
                target=self.custom_pulse,
                args=(
                    fade_in_time,
                    fade_out_time,
                    lower_limit,
                    upper_limit,
                    False
                )
            )
            t.daemon = True
            t.start()
            return
        self.pulsing = True
        increasing = True
        difference = float(upper_limit - lower_limit)
        step_up_size = difference / (fade_in_time / 0.05)
        step_down_size = difference / (fade_out_time / 0.05)
        self.value = lower_limit
        while self.pulsing:
            v = self.value
            if increasing:
                v += step_up_size
                if v >= upper_limit:
                    self.value = upper_limit
                    increasing = False
                else:
                    self.value = v
            else:
                v -= step_down_size
                if v <= lower_limit:
                    self.value = lower_limit
                    increasing = True
                else:
                    self.value = v
            sleep(0.05)

    def custom_stop(self):
        self.pulsing = False
        self.off()


class ShipController:
    def __init__(self, start_thread=False):
        """If start_thread is False, "network_control" will need to be called."""
        self.__cabins_mode = "random"  # "static" / "random"
        self.__nacelles_mode = "pulse"  # "static" / "pulse"

        dynamic_cabin_pins = (
                                 12,
                                 16,
                                 20,
                                 21,
                                 26,
                                 19,
                                 13,
                                 6,
                                 5,
                                 11,
                                 9,
                                 10,
                                 22,
                                 27,
                                 17,
                                 4,
        )

        self.lights = {
            "static_nacelles": LED(14),
            "dynamic_nacelles": CustomPWMLED(15),
            "port_lights": LED(18),
            "starboard_lights": LED(23),
            "top_lights_1": LED(24),
            "top_lights_2": LED(25),
            "top_lights_3": LED(8),
            "static_cabins": LED(7),
            "dynamic_cabins": DynamicLights(
                [
                    LED(n) for n in dynamic_cabin_pins
                ],
                parent=self
            ),
        }
        self.blinkers_lit = False
        self.receiver_socket = socket.socket()
        self.connected = False
        self.current_connection = None
        self.run = True

        if start_thread:
            self.network_thread = Thread(
                target=self.network_control
            )
            self.network_thread.daemon = True
            self.network_thread.start()

        self.nacelles_on()
        self.cabins_on()
        self.blinkers_on()

        self.update_screen()

    @property
    def cabins_mode(self):
        return self.__cabins_mode

    @property
    def nacelles_mode(self):
        return self.__nacelles_mode

    def cabins_on(self):
        self.lights["static_cabins"].on()
        self.lights["dynamic_cabins"].on()
        if self.__cabins_mode == "static":
            self.lights["dynamic_cabins"].set_static()
        elif self.__cabins_mode == "random":
            self.lights["dynamic_cabins"].set_random()

    def cabins_off(self):
        self.lights["static_cabins"].off()
        self.lights["dynamic_cabins"].off()

    def nacelles_on(self):
        self.lights["static_nacelles"].on()
        if self.__nacelles_mode == "static":
            self.lights["dynamic_nacelles"].on()
        elif self.__nacelles_mode == "pulse":
            self.lights["dynamic_nacelles"].custom_pulse(0.3, 0.9, 0.2, 0.3)

    def nacelles_off(self):
        self.lights["static_nacelles"].off()
        self.lights["dynamic_nacelles"].custom_stop()

    def blinkers_on(self):
        # Start Side Blinkers
        self.lights["port_lights"].blink(5, 0.1)
        sleep(0.1)
        self.lights["starboard_lights"].blink(5, 0.1)

        # Start top blinks.
        self.lights["top_lights_1"].blink(0.1, 2)
        sleep(0.1)
        self.lights["top_lights_3"].blink(0.1, 2)
        sleep(0.1)
        self.lights["top_lights_2"].blink(0.1, 2)
        self.blinkers_lit = True

    def blinkers_off(self):
        self.lights["port_lights"].off()
        self.lights["starboard_lights"].off()
        self.lights["top_lights_1"].off()
        self.lights["top_lights_2"].off()
        self.lights["top_lights_3"].off()
        self.blinkers_lit = False

    def set_nacelles_mode(self, mode):
        """
        Mode may be "static" or "pulse".
        :type mode: str
        """
        assert mode in ("static", "pulse")
        self.__nacelles_mode = mode
        if self.lights["dynamic_nacelles"].is_active:
            self.nacelles_off()
            self.nacelles_on()

    def set_cabins_mode(self, mode):
        """
        Mode may be "static" or "random".
        :type mode: str
        """
        assert mode in ("static", "random")
        self.__cabins_mode = mode
        if mode == "static":
            self.lights["dynamic_cabins"].set_static()
        else:
            self.lights["dynamic_cabins"].set_random()

    def process_command(self, command):
        global RUN
        if type(command) is str:
            commands = command.split(" ")
        elif type(command) in (tuple, list):
            commands = command
            if [type(c) for c in commands].count(str) != len(commands):
                raise TypeError("List of commands was not all strings.")
        else:
            raise TypeError("Invalid command type <{}>".format(type(command)))

        while len(commands) < 3:
            commands.append("")

        if commands[0] == "cabins":
            if commands[1] == "on":
                self.cabins_on()
                print("<System> Cabins on.")
            elif commands[1] == "off":
                self.cabins_off()
                print("<System> Cabins off.")
            elif commands[1] in ("random", "mode"):
                if commands[2] in ("on", "random"):
                    self.set_cabins_mode("random")
                    print("<System> Cabins mode set to random.")
                elif commands[2] in ("off", "static"):
                    self.set_cabins_mode("static")
                    print("<System> Cabins mode set to static.")
        elif commands[0] in ("engines", "nacelles"):
            if commands[1] == "on":
                self.nacelles_on()
                print("<System> Nacelles on.")
            elif commands[1] == "off":
                self.nacelles_off()
                print("<System> Nacelles off.")
            elif commands[1] in ("pulse", "mode"):
                if commands[2] in ("on", "pulse"):
                    self.set_nacelles_mode("pulse")
                    print("<System> Nacelles mode set to pulse.")
                elif commands[2] in ("off", "static"):
                    self.set_nacelles_mode("static")
                    print("<System> Nacelles mode set to static.")
        elif commands[0] == "blinkers":
            if commands[1] == "on":
                self.blinkers_on()
                print("<System> Blinkers on.")
            elif commands[1] == "off":
                self.blinkers_off()
                print("<System> Blinkers off.")
        elif commands[0] == "all":
            if commands[1] == "on":
                self.cabins_on()
                self.nacelles_on()
                self.blinkers_on()
                print("<System> All on.")
            elif commands[1] == "off":
                self.cabins_off()
                self.nacelles_off()
                self.blinkers_off()
                print("<System> All off.")
        elif commands[0] in ("stop", "exit", "halt"):
            self.cabins_off()
            self.nacelles_off()
            self.blinkers_off()
            print("<System> Stopping...")
            RUN = False
            self.run = False
            self.receiver_socket.close()
            self.run = False
            RUN = False
            Thread(target=self.stop).start()
        elif commands[0] == "get_state":
            #print("<System> Getting state.")
            return self.get_state()
        self.update_screen()

    def stop(self):
        sleep(1)
        DISPLAY.clear()
        DISPLAY.backlight("off")
        exit(0)

    def get_state(self):
        data = {
            "cabins": self.lights["static_cabins"].is_lit,
            "cabins_mode": self.__cabins_mode,
            "cabin_lights": "".join(["1" if led.is_lit else "0" for led in self.lights["dynamic_cabins"].lights]),
            "nacelles": self.lights["static_nacelles"].is_lit,
            "nacelles_mode": self.__nacelles_mode,
            "blinkers": self.blinkers_lit
        }
        return data

    def network_control(self):
        self.receiver_socket.bind(("0.0.0.0", 3141))
        self.receiver_socket.listen(1)
        print("<System> Socket open and listening.")
        self.connected = False
        while self.run:
            self.current_connection, addr = self.receiver_socket.accept()
            self.connected = True
            print(f"<System> Client connected from {addr}.")
            self.update_screen()
            data = b""
            while self.run:
                try:
                    rb = self.current_connection.recv(1)
                except (ConnectionError, OSError):
                    break

                if rb == b"":
                    try:
                        self.current_connection.close()
                    except (ConnectionError, OSError):
                        pass
                    break
                elif rb == b"\n":
                    command = data.decode()
                    try:
                        command = json.loads(command)
                        resp = controller.process_command(command)
                        self.current_connection.send(
                            json.dumps(resp).encode()
                        )
                        data = b""
                    except json.JSONDecodeError:
                        print("<System> JSONDecodeError: Bad data received.")
                else:
                    data += rb
            self.connected = False
            print(f"<System> Client {addr} disconnected.")
            self.update_screen()

    def update_screen(self):
        if not DEBUG_DISPLAY:
            return
        state = self.get_state()
        on = "ON "
        off = "OFF"
        lines = [
            "Nacelles:{} Mode:{}".format(
                on if state["nacelles"] else off,
                "Pu" if state["nacelles_mode"] == "pulse" else "St"
            ),
            "Blinkers:{}        ".format(
                on if state["blinkers"] else off
            ),
            "Cabins:{} Mode:{}".format(
                on if state["cabins"] else off,
                "Rand" if state["cabins_mode"] == "random" else "Stat"
            ),
            "{}{}".format(
                "".join(["*" if led.is_lit else "O" for led in self.lights["dynamic_cabins"].lights]).ljust(19),
                "C" if self.connected else " "
            )
        ]
        for i, line in enumerate(lines):
            DISPLAY.set(line, i + 1)


def run_cl():
    while RUN:
        command = input("}}} ")
        controller.process_command(command)


def test(pins):
    lights = [PWMLED(n) for n in pins]
    for light in lights:
        light.off()
    lights[0].on()
    pos = 0
    print(0)
    while True:
        sleep(2)
        pos += 1
        if pos == len(lights):
            pos = 0
        print(pos)
        lights[pos].toggle()
        lights[pos - 1].toggle()


def chip_test():
    chip1 = [14, 15, 18, 23, 24, 25, 8, 7]
    chip2 = [12, 16, 20, 21, 26, 19, 13, 6]
    chip3 = [9, 10, 22, 27, 17, 4, 3, 2]
    test(chip3)


controller = ShipController()
controller.network_control()
