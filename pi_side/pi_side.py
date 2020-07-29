import json
import socket
import sys
from gpiozero import LED, PWMLED
from time import sleep
from random import randint
from threading import Thread


RUN = True


class DynamicLights:
    def __init__(self, lights, mode="random"):
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
                while self.is_active:
                    self.lights[randint(0, len(self.lights) - 1)].toggle()
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
        sleep(1.2)
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
    def __init__(self):
        self.__cabins_mode = "random"  # "static" / "random"
        self.__nacelles_mode = "pulse"  # "static" / "pulse"

        self.lights = {
            "static_cabins": LED(11),
            "dynamic_cabins": DynamicLights(
                [
                    LED(9),
                    LED(10),
                    LED(22),
                    LED(27),
                    LED(17)
                ]
            ),
            "dynamic_nacelles": CustomPWMLED(14),
            "static_nacelles": LED(15),
            "port_lights": LED(25),
            "starboard_lights": LED(24),
            "top_lights_1": LED(23),
            "top_lights_2": LED(18),
            "top_lights_3": LED(19)
        }

        self.receiver_socket = socket.socket()
        self.connected = False
        self.current_connection = None
        self.run = True
        self.network_thread = Thread(
            target=self.network_control
        )
        self.network_thread.start()

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

    def blinkers_off(self):
        self.lights["port_lights"].off()
        self.lights["starboard_lights"].off()
        self.lights["top_lights_1"].off()
        self.lights["top_lights_2"].off()
        self.lights["top_lights_3"].off()

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
        if self.lights["dynamic_cabins"].is_active:
            self.lights["dynamic_cabins"].off()
            self.lights["dynamic_cabins"].on()

    def process_command(self, command):
        global RUN
        commands = []
        if type(command) is str:
            commands = command.split(" ")
        elif type(command) in (tuple, list):
            commands = command
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
            elif commands[1] == "random":
                if commands[2] == "on":
                    self.set_cabins_mode("random")
                    print("<System> Cabins mode set to random.")
                elif commands[2] == "off":
                    self.set_cabins_mode("static")
                    print("<System> Cabins mode set to static.")
        elif commands[0] in ("engines", "nacelles"):
            if commands[1] == "on":
                self.nacelles_on()
                print("<System> Nacelles on.")
            elif commands[1] == "off":
                self.nacelles_off()
                print("<System> Nacelles off.")
            elif commands[1] == "pulse":
                if commands[2] == "on":
                    self.set_nacelles_mode("pulse")
                    print("<System> Nacelles mode set to pulse.")
                elif commands[2] == "off":
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
            if not self.connected:
                s = socket.create_connection(("localhost", 3141))
                s.close()
            sys.exit(0)
        elif commands[0] == "get_state":
            print("<System> Getting state.")
            return self.get_state()

    def get_state(self):
        data = {
            "cabins": self.lights["static_cabins"].is_lit,
            "cabins_mode": self.__cabins_mode,
            "nacelles": self.lights["static_nacelles"].is_lit,
            "nacelles_mode": self.__nacelles_mode,

        }
        return data

    def network_control(self):
        self.receiver_socket.bind(("0.0.0.0", 3141))
        self.receiver_socket.listen(1)
        while self.run:
            self.connected = False
            self.current_connection,  addr = self.receiver_socket.accept()
            self.connected = True
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


def run_cl():
    controller.nacelles_on()
    controller.cabins_on()
    controller.blinkers_on()

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
        lights[pos-1].toggle()


def chip_test():
    chip1 = [14, 15, 18, 23, 24, 25, 8, 7]
    chip2 = [12, 16, 20, 21, 26, 19, 13, 6]
    chip3 = [9, 10, 22, 27, 17, 4, 3, 2]
    test(chip3)


controller = ShipController()
run_cl()
