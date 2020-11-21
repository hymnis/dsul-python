#!/usr/bin/env python
"""DSUL - Disturb State USB Light : Daemon application."""

import getopt
import logging
import sys
import threading
import time
from typing import Any, Dict, List, Union, no_type_check

import serial  # type: ignore

from . import DEBUG, VERSION, ipc, settings


def exception_handler(
    exception_type, exception, traceback, debug_hook=sys.excepthook
):
    """Handle exception in a custom way."""
    if DEBUG:
        debug_hook(exception_type, exception, traceback)
    else:
        if exception:
            print("%s: %s" % (exception_type.__name__, exception))
        else:
            print("%s" % exception_type.__name__)


sys.excepthook = exception_handler


class DsulDaemon:
    """DSUL Daemon application class."""

    ser: Any = None
    send_commands: List[Dict[str, object]] = []
    current_mode = ""
    current_color = ""
    current_brightness = ""

    @no_type_check
    def __init__(self, argv) -> None:
        """Initialize the class."""
        print("[] DSUL: Daemon")

        if DEBUG:
            logformat = (
                "[%(asctime)s] {%(pathname)s:%(lineno)d} "
                "%(levelname)s - %(message)s"
            )
            loglevel = logging.DEBUG
            logfile = None
        else:
            logformat = (
                "[%(asctime)s] {%(pathname)s} " "%(levelname)s - %(message)s"
            )
            loglevel = logging.WARNING
            logfile = "daemon.log"

        logging.basicConfig(
            level=loglevel,
            filename=logfile,
            format=logformat,
            datefmt="%H:%M:%S",
        )

        logging.info("DsulDaemon initializing.")

        self.settings: Dict[str, Any] = settings.get_settings("daemon")
        self.read_arguments(argv)

        self.ser = serial.Serial()
        self.init_serial()

    def __missing__(self, key) -> str:
        """Log and return missing key information."""
        message = f"{key} not present in the dictionary!"
        logging.warning(message)
        return message

    def __str__(self) -> str:
        """Return a string representation of the class."""
        message = (
            "DsulDaemon<>(debug=val, ser=val, serial_active=val, "
            "serial_verified=val, ipc_active=val, pinger_active=val"
            "send_commands=val, "
            "current_mode=val, current_color=val, current_brightness=val)"
        )
        return message

    def read_arguments(self, argv) -> None:
        """Parse command line arguments."""
        help_string = (
            "dsul-daemon --help -h <host> -p <port> -c <com port> "
            "-b <baudrate> --version"
        )
        version_string = f"Version {VERSION}"

        # read (overriding) settings from command arguments
        try:
            opts, args = getopt.getopt(  # pylint: disable=W0612
                argv,
                "p:h:c:b:",
                ["help", "port=", "host=", "comport=", "baudrate=", "version"],
            )
        except getopt.GetoptError:
            print(help_string)
            sys.exit(2)

        for opt, arg in opts:
            if opt == "--help":
                print(help_string)
                sys.exit()
            elif opt in ("-h", "--host"):
                self.settings["ipc"]["host"] = arg
            elif opt in ("-p", "--port"):
                self.settings["ipc"]["port"] = int(arg)
            elif opt in ("-c", "--comport"):
                self.settings["serial"]["port"] = arg
            elif opt in ("-b", "--baudrate"):
                self.settings["serial"]["baudrate"] = int(arg)
            elif opt == "--version":
                print(version_string)
                sys.exit()

    def run(self) -> None:
        """Run the main loop of the application."""
        try:
            self.ipc_active = True
            ipc_thread = threading.Thread(target=self.ipc_process, daemon=True)
            ipc_thread.start()

            self.pinger_active = True
            pinger_thread = threading.Thread(
                target=self.pinger_process, daemon=True
            )
            pinger_thread.start()

            while ipc_thread.is_alive():
                self.process_commands()
                time.sleep(0.5)  # NOTE: find better way of handling this

            ipc_thread.join()
            pinger_thread.join()

        except (KeyboardInterrupt, SystemExit):
            logging.info("DsulDaemon exiting.")

            self.serial_active = False
            self.ipc_active = False
            self.pinger_active = False
            self.deinit_serial()
            sys.exit()

    def ipc_process(self) -> None:
        """Handle IPC communication."""
        server_address = (
            self.settings["ipc"]["host"],
            self.settings["ipc"]["port"],
        )
        logging.info(
            f"Starting IPC server ({self.settings['ipc']['host']}:"
            f"{self.settings['ipc']['port']})"
        )

        while self.ipc_active:
            ipc.Server(
                address=server_address, callback=self.process_server_request
            )
        logging.info("IPC server stopped")

    def pinger_process(self) -> None:
        """Send pings to device, to keep communication open."""
        logging.info("Starting pinger")

        while self.pinger_active and self.serial_active:
            starttime = time.time()

            while True:
                self.send_ping()
                time.sleep(60.0 - ((time.time() - starttime) % 60.0))

        logging.info("Pinger stopped")

    def init_serial(self) -> None:
        """Initilize serial communication."""
        try:
            if not self.ser.is_open:
                logging.info(
                    "Opening serial port "
                    f"({self.settings['serial']['port']})"
                )
                self.ser.port = self.settings["serial"]["port"]
                self.ser.baudrate = self.settings["serial"]["baudrate"]
                self.ser.timeout = self.settings["serial"]["timeout"]
                self.ser.open()
                self.serial_active = True
                self.serial_verified = False
                time.sleep(2)  # wait until device is out of boot state
                self.set_current_states()
        except serial.serialutil.SerialException:
            logging.error(
                "Failed to open serial port "
                f"({self.settings['serial']['port']})"
            )
            self.serial_verified = False
            self.serial_active = False
        except IOError:
            logging.error(
                "Serial port does not exist. "
                f"({self.settings['serial']['port']})"
            )
            self.serial_verified = False
            self.serial_active = False

    def deinit_serial(self) -> None:
        """De-initialize serial communication."""
        try:
            if self.ser is not None and self.ser.is_open:
                self.ser.close()
        except serial.serialutil.SerialException:
            logging.error("An error occured when de-initializing serial port.")

    def read_serial(self) -> Union[str, bool]:
        """Read data from serial connection."""
        try:
            incoming = bytearray()

            while True:
                i = max(1, min(2048, self.ser.in_waiting))
                data = self.ser.read(i)
                i = data.find(b"#")

                if i >= 0:
                    # fmt: off
                    r = incoming + data[:i + 1]
                    incoming[0:] = data[i + 1:]
                    # fmt: on
                    return str(r.decode())
                else:
                    incoming.extend(data)
        except serial.serialutil.SerialException:
            return False

    def write_serial(self, message: str) -> bool:
        """Write data to the serial connection."""
        try:
            self.ser.write(message.encode())
            return True
        except serial.serialutil.SerialException:
            return False

    def get_serial_data(self) -> None:
        """Get serial data and process the input."""
        in_data = self.read_serial()

        if in_data is not None:
            self.handle_serial_input(in_data)

    def handle_serial_input(self, input_data: Union[str, bool]) -> None:
        """Handle serial commands and input data."""
        if input_data:
            logging.debug(f"<S : {input_data}")

            if len(input_data) == 3:  # type: ignore
                read_command = True
                read_data = False
            else:
                read_command = False
                read_data = True

            if read_command:
                logging.debug("serial command received")

                if input_data == "-!#":  # resend/request data
                    logging.info("Serial Response: Resend/Request")
                elif input_data == "-?#":  # ping
                    logging.info("Serial Response: Ping")
                    self.send_ok()
                elif input_data == "+!#":  # ok
                    logging.info("Serial Response: OK")
                elif input_data == "+?#":  # unknown/error
                    logging.info("Serial Response: Unknown/Error")

                self.serial_verified = True
            elif read_data:
                logging.debug("serial data received")
                # TODO: eh.. process it?

    def set_current_states(self) -> None:
        """Set current states, if any."""
        if self.current_mode:
            self.queue_command("mode", self.current_mode)
        elif self.current_color:
            self.queue_command("color", self.current_color)
        elif self.current_brightness:
            self.queue_command("brightness", self.current_brightness)

    def queue_command(self, key, value: str):
        """Add command to the queue."""
        if key == "color":
            return self.send_color_command(value)
        elif key == "brightness":
            return self.send_brightness_command(value)
        elif key == "mode":
            return self.send_mode_command(value)

    def send_color_command(self, value: str) -> bool:
        """Send command to set color."""
        try:
            index, r, g, b = value.split(":")
            logging.info(f'Setting color: "{r},{g},{b}" for "{index}"')
            self.current_color = value
            self.send_commands.append(
                {
                    "command": "+l{:03d}{:03d}{:03d}{:03d}#".format(
                        int(index), int(r), int(g), int(b)
                    ),
                    "want_reply": True,
                }
            )

            return True
        except ValueError:
            logging.warning(f'Invalid argument: "{value}"')

        return False

    def send_brightness_command(self, value: str) -> bool:
        """Send command to set brightness."""
        if (
            int(value) >= self.settings["brightness_min"]
            and int(value) <= self.settings["brightness_max"]
        ):
            logging.info(f'Setting brightness: "{value}"')
            self.current_brightness = value
            self.send_commands.append(
                {"command": "+b{:03d}#".format(int(value)), "want_reply": True}
            )

            return True
        else:
            logging.warning(f'Invalid argument: "{value}"')

        return False

    def send_mode_command(self, value: str) -> bool:
        """Send command to set the mode."""
        if value in self.settings["modes"]:
            logging.info(f'Setting mode: "{value}"')
            self.current_mode = value

            if value == "solid":
                mode_value = 1
            elif value == "blink":
                mode_value = 2
            elif value == "flash":
                mode_value = 3

            self.send_commands.append(
                {"command": f"+m{mode_value}#", "want_reply": True}
            )

            return True
        else:
            logging.warning(f'Invalid argument: "{value}"')

        return False

    def send_ping(self) -> None:
        """Send ping to device."""
        logging.info("Sending ping to device")
        self.send_commands.append({"command": "-?#", "want_reply": True})

    def send_ok(self) -> None:
        """Send OK to device."""
        logging.info("Sending OK to device")
        self.send_commands.append({"command": "+!#", "want_reply": False})

    def process_commands(self) -> None:
        """Process the command queue."""
        retries = 0
        queue_count = len(self.send_commands)

        while queue_count > 0:
            command_item = self.send_commands.pop(0)
            queue_count -= 1
            self.init_serial()  # make sure serial connection is setup

            if self.serial_active:
                logging.debug(f"S> : {command_item['command']}")

                try:
                    while not self.write_serial(str(command_item["command"])):
                        retries += 1

                        if retries >= 5:
                            retries = 0
                            raise Exception("Could not send serial command.")

                        time.sleep(1)

                    if command_item["want_reply"]:
                        self.get_serial_data()
                except Exception:
                    logging.error("Sending serial command failed (5 retries).")
                    logging.debug(
                        f"Failed serial command: {command_item['command']}"
                    )
            else:
                logging.error(
                    "Serial connection not active. Can't send commands."
                )

    def get_request_results(self, message_object: Any) -> Dict[str, str]:
        """Return results after request handling."""
        action = "NOK"
        message = "Invalid request/argument"

        if message_object.properties["key"] == "status":
            action = "OK"
            if message_object.properties["value"] == "color":
                message = self.current_color
            elif message_object.properties["value"] == "brightness":
                message = self.current_brightness
            elif message_object.properties["value"] == "mode":
                message = self.current_mode
        elif message_object.properties["key"] == "information":
            action = "OK"
            message = self.get_information()

        return {"action": action, "message": message}

    def get_information(self) -> str:
        """Get server information to the client."""
        return (
            f"version={VERSION};"
            f"modes={self.settings['modes']};"
            f"leds={self.settings['leds']};"
            f"brightness_min={self.settings['brightness_min']};"
            f"brightness_max={self.settings['brightness_max']};"
            f"current_mode={self.current_mode};"
            f"current_brightness={self.current_brightness};"
            f"current_color={self.current_color};"
        )

    def process_server_request(self, objects: Any) -> List:
        """Handle request sent to the IPC server."""
        logging.debug(f"<I : {objects}")

        if self.serial_verified:
            for message_object in objects:
                if message_object.type[0] == "command":
                    action = "ACK"
                    valid = self.queue_command(
                        message_object.properties["key"],
                        message_object.properties["value"],
                    )
                    message = (
                        f"{message_object.properties['key']}="
                        f"{message_object.properties['value']}"
                    )

                    if not valid:
                        message = "Invalid command/argument"

                elif message_object.type[0] == "request":
                    result = self.get_request_results(message_object)
                    action = result["action"]
                    message = result["message"]
                else:
                    action = "ACK"
                    message = "Unknown event type"

            response = [ipc.Response(f"{action}, {message}")]
        else:
            response = [ipc.Response("ACK, No serial connection")]

        logging.debug(f"I> : {response}")

        return response


if __name__ == "__main__":
    APP = DsulDaemon(sys.argv[1:])
    APP.run()
