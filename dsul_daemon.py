#!/usr/bin/env python
"""DSUL - Disturb State USB Light : Daemon application."""

import configparser
import getopt
import logging
import os
import sys
import threading
import time
from typing import Any, Dict, List, Union, no_type_check

import serial  # type: ignore

import ipc


class DsulDaemon:
    """DSUL Daemon application class."""

    read_command = True
    read_data = False
    ser: Any = None
    send_commands: List[str] = []
    current_command = ""
    retries = 0
    colors: Dict[str, List[str]] = {}
    modes: List[str] = []
    serial: Dict[str, Union[int, str]] = {}
    ipc: Dict[str, Union[int, str]] = {}

    @no_type_check
    def __init__(self, argv) -> None:
        """Initialize the class."""
        print("[] DSUL Daemon")
        logformat = (
            "[%(asctime)s] {%(pathname)s} " "%(levelname)s - %(message)s"
        )
        logging.basicConfig(
            level=logging.INFO,
            filename="daemon.log",
            format=logformat,
            datefmt="%H:%M:%S",
        )
        logpath = logging.getLoggerClass().root.handlers[0].baseFilename
        print(f"Log file at: {logpath}")
        logging.info("DsulDaemon initializing.")

        self.get_settings()
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
            "serial_wait=val, ipc_active=val, read_command=val, "
            "read_data=val, send_commands=val, current_command=val, "
            "retries=val, colors=val, mode=val, serial=val, ipc=val)"
        )
        return message

    def get_settings(self) -> None:
        """Get settings from config file."""
        config = configparser.RawConfigParser()
        config.read("dsul.cfg")

        self.debug = config.getint("DSUL", "debug", fallback=False)
        if self.debug:
            logformat = (
                "[%(asctime)s] {%(pathname)s:%(lineno)d} "
                "%(levelname)s - %(message)s"
            )
            logger = logging.getLogger()
            logger.setLevel(logging.DEBUG)
            formatter = logging.Formatter(logformat)
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        self.ipc["host"] = config.get("IPC", "host", fallback="localhost")
        self.ipc["port"] = config.getint("IPC", "port", fallback=5795)

        self.serial["port"] = config.get(
            "Serial", "port", fallback="/dev/ttyUSB0"
        )
        self.serial["baudrate"] = config.getint(
            "Serial", "baudrate", fallback=9600
        )
        self.serial["timeout"] = config.getint("Serial", "timeout", fallback=1)

        self.modes = config.get("Modes", "types").split(",")

        self.brightness_min = config.getint("Brightness", "min", fallback=0)
        self.brightness_max = config.getint("Brightness", "max", fallback=150)

        self.colors["red"] = config.get("Colors", "red").split(",")
        self.colors["green"] = config.get("Colors", "green").split(",")
        self.colors["blue"] = config.get("Colors", "blue").split(",")
        self.colors["cyan"] = config.get("Colors", "cyan").split(",")
        self.colors["white"] = config.get("Colors", "white").split(",")
        self.colors["warmwhite"] = config.get("Colors", "warmwhite").split(",")
        self.colors["purple"] = config.get("Colors", "purple").split(",")
        self.colors["magenta"] = config.get("Colors", "magenta").split(",")
        self.colors["yellow"] = config.get("Colors", "yellow").split(",")
        self.colors["orange"] = config.get("Colors", "orange").split(",")
        self.colors["black"] = config.get("Colors", "black").split(",")

    def read_arguments(self, argv) -> None:
        """Parse command line arguments."""
        help_string = "dsul_daemon.py --help -h <host> -p <port>"

        # read (overriding) settings from command arguments
        try:
            opts, args = getopt.getopt(  # pylint: disable=W0612
                argv,
                "p:h:c:b:",
                ["help", "port=", "host=", "comport=", "baudrate="],
            )
        except getopt.GetoptError:
            print(help_string)
            sys.exit(2)

        for opt, arg in opts:
            if opt == "--help":
                print(help_string)
                sys.exit()
            elif opt in ("-h", "--host"):
                self.ipc["host"] = arg
            elif opt in ("-p", "--port"):
                self.ipc["port"] = int(arg)
            elif opt in ("-c", "--comport"):
                self.serial["port"] = arg
            elif opt in ("-b", "--baudrate"):
                self.serial["baudrate"] = int(arg)

    def run(self) -> None:
        """Run the main loop of the application."""
        try:
            self.ipc_active = True
            ipc_thread = threading.Thread(target=self.ipc_process, daemon=True)
            ipc_thread.start()

            while ipc_thread.is_alive():
                self.process_commands()
                time.sleep(1)

        except (KeyboardInterrupt, SystemExit):
            logging.info("DsulDaemon exiting.")

            self.serial_active = False
            self.ipc_active = False
            self.deinit_serial()

    def ipc_process(self) -> None:
        """Handle IPC communication."""
        server_address = (self.ipc["host"], self.ipc["port"])
        logging.info(
            f"Starting IPC server ({self.ipc['host']}:{self.ipc['port']})"
        )

        while self.ipc_active:
            ipc.Server(
                address=server_address, callback=self.process_server_request
            )
        logging.info("IPC server stopped")

    def init_serial(self) -> None:
        """Initilize serial communication."""
        try:
            if not self.ser.is_open:
                logging.info(f"Opening serial port ({self.serial['port']})")
                self.ser.port = self.serial["port"]
                self.ser.baudrate = self.serial["baudrate"]
                self.ser.timeout = self.serial["timeout"]
                self.ser.open()
                self.serial_active = True
        except serial.serialutil.SerialException:
            logging.error(
                "Failed to open serial port " f"({self.serial['port']})"
            )
            self.serial_active = False
        except IOError:
            logging.error(
                "Serial port does not exist. " f"({self.serial['port']})"
            )
            self.serial_active = False

    def deinit_serial(self) -> None:
        """De-initialize serial communication."""
        try:
            if self.ser is not None and self.ser.is_open:
                self.ser.close()

            self.serial_active = False
        except serial.serialutil.SerialException:
            logging.error("An error occured when de-initializing serial port.")

    def read_serial(self) -> Union[str, bool]:
        """Read data from serial connection."""
        try:
            if self.read_command:
                read_length = 3
            elif self.read_data:
                read_length = 10
            incoming = self.ser.read(read_length)
            if incoming != b"":
                incoming = incoming.decode()
            else:
                incoming = None
        except serial.serialutil.SerialException:
            incoming = None

        return incoming

    def write_serial(self, message) -> bool:
        """Write data to the serial connection."""
        try:
            self.ser.write(message.encode())
            return True
        except serial.serialutil.SerialException:
            return False

    def handle_serial_input(self, input_data) -> None:
        """Handle serial commands and input data."""
        logging.debug(f"<S: {input_data}")

        if self.read_command:
            logging.debug("serial command received")

            if input_data == "-!#":  # resend/request data
                logging.info("Serial Response: Resend/Request")
            elif input_data == "-?#":  # ping
                logging.info("Serial Response: Ping")
                self.write_serial("+!#")  # ok/pong
            elif input_data == "+!#":  # ok
                logging.info("Serial Response: OK")
            elif input_data == "+?#":  # unknown/error
                logging.info("Serial Response: Unknown/Error")

            self.serial_wait = False
        elif self.read_data:
            logging.debug("serial data received")

    def queue_command(self, key, value):
        """Add command to the queue."""
        if key == "color":
            return self.send_color_command(value)
        elif key == "brightness":
            return self.send_brightness_command(value)
        elif key == "mode":
            return self.send_mode_command(value)
        elif key == "information":
            return self.get_informaion(value)

    def send_color_command(self, value) -> bool:
        """Send command to set color."""
        if value in self.colors:
            logging.info(f'Setting color: "{value}"')
            self.send_commands.append(
                "+l{:03d}{:03d}{:03d}#".format(
                    int(self.colors[value][0]),
                    int(self.colors[value][1]),
                    int(self.colors[value][2]),
                )
            )

            return True
        else:
            logging.warning(f'Invalid argument: "{value}"')
            return False

    def send_brightness_command(self, value) -> bool:
        """Send command to set brightness."""
        if (
            int(value) >= self.brightness_min
            and int(value) <= self.brightness_max
        ):
            logging.info(f'Setting brightness: "{value}"')
            self.send_commands.append("+b{:03d}#".format(int(value)))

            return True
        else:
            logging.warning(f'Invalid argument: "{value}"')
            return False

    def send_mode_command(self, value) -> bool:
        """Send command to set the mode."""
        if value in self.modes:
            logging.info(f'Setting mode: "{value}"')
            self.send_commands.append("+m{}#".format(value))

            return True
        else:
            logging.warning(f'Invalid argument: "{value}"')
            return False

    def get_information(self, value) -> str:
        """Get information to the client."""
        pass
        # TODO: write function that returns all relevant information
        # version
        # colors
        # modes
        # brightness min/max
        # current state

    def process_commands(self) -> None:
        """Process the command queue."""
        if self.current_command != "":
            self.init_serial()  # make sure serial connection is setup

            if self.serial_active:
                logging.debug(f"S> : {self.current_command}")
                if not self.write_serial(self.current_command):
                    self.retries += 1
                else:
                    self.current_command = ""
                    self.serial_wait = True

                    # Wait for serial response
                    while self.serial_wait:
                        in_data = self.read_serial()
                        if in_data is not None:
                            self.handle_serial_input(in_data)

                if self.retries >= 5:
                    logging.error("Sending serial command failed (5 retries)")
                    logging.debug(
                        f"Failed serial command: " f"{self.current_command}"
                    )
                    self.retries = 0
                    self.current_command = ""

        # add command(s) to queue
        if self.send_commands != [] and self.current_command == "":
            self.current_command = self.send_commands.pop()

    def process_server_request(self, objects) -> List:
        """Handle request sent to the IPC server."""
        logging.debug(f"<I : {objects}")

        if os.path.exists(self.serial["port"]):  # type: ignore
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
                    action = "OK"
                    message = ""
                    # TODO: handle requests properly (with a correct reply)

                    # what is the client requesting?
                    # key:
                    # - status : current status for value

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
