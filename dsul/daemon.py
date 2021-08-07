#!/usr/bin/env python
"""DSUL - Disturb State USB Light : Daemon application."""

import argparse
import logging
import re
import sys
import threading
import time
from typing import Any, Dict, List, no_type_check

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


def main():
    """Run the program."""
    application = DsulDaemon()
    application.run()


class DsulDaemon:  # pylint: disable=R0902
    """DSUL Daemon application class."""

    logger: Any = None
    device: Dict[str, Any] = {}
    ser: Any = None
    serial_active = False
    serial_verified = False
    serial_input_buffer = bytearray()
    send_commands: List[Dict[str, object]] = []
    ipc_active = False
    pinger_active = False
    current_mode = 0
    current_color = ""
    current_brightness = ""
    current_dim = 0

    @no_type_check
    def __init__(self) -> None:
        """Initialize the class."""
        if DEBUG:
            logformat = (
                "[%(asctime)s] %(levelname)-8s {%(pathname)s:%(lineno)d} "
                "- %(message)s"
            )
            loglevel = logging.DEBUG
            logfile = None
        else:
            logformat = "[%(asctime)s] %(levelname)-8s %(message)s"
            loglevel = logging.WARNING
            logfile = "daemon.log"

        logging.basicConfig(
            level=loglevel,
            filename=logfile,
            format=logformat,
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info("DsulDaemon initializing.")

        self.settings: Dict[str, Any] = settings.get_settings("daemon")
        self.__read_arguments()

        self.ser = serial.Serial()
        self.init_serial()

    def __missing__(self, key) -> str:
        """Log and return missing key information."""
        message = f"{key} not present in the dictionary!"
        self.logger.warning(message)
        return message

    def __str__(self) -> str:
        """Return a string representation of the class."""
        message = (
            "DsulDaemon<>(ser=val, serial_active=val, "
            "serial_verified=val, ipc_active=val, pinger_active=val"
            "send_commands=val, device=val, logger=val, settings=val, "
            "current_mode=val, current_color=val, current_brightness=val, "
            "current_dim=val)"
        )
        return message

    # SETTING #

    def __read_arguments(self) -> None:  # noqa
        """Parse command line arguments."""
        parser = argparse.ArgumentParser(prog="dsul-daemon")
        ipc_group = parser.add_mutually_exclusive_group()
        config_group = parser.add_mutually_exclusive_group()

        # IPC
        ipc_group.add_argument(
            "-a",
            "--address",
            nargs="?",
            help="the address/hostname to expose IPC server on",
        )
        ipc_group.add_argument(
            "-s",
            "--socket",
            nargs="?",
            help="the socket to use for IPC server",
        )
        parser.add_argument(
            "-p",
            "--port",
            type=int,
            nargs="?",
            help="the port number to use for IPC server",
        )

        # Config
        config_group.add_argument(
            "--save",
            action="store_true",
            help="create/overwrite config file with given settings",
        )
        config_group.add_argument(
            "--update",
            action="store_true",
            help="update config file with given settings",
        )

        # Serial
        parser.add_argument(
            "-c", "--comport", nargs="?", help="the COM port to use"
        )
        parser.add_argument(
            "-b",
            "--baudrate",
            type=int,
            nargs="?",
            help="the baudrate to use for the COM port",
        )
        parser.add_argument(
            "-t",
            "--timeout",
            type=int,
            nargs="?",
            help="the connection timeout to use for COM port (in seconds)",
        )

        # Output
        parser.add_argument(
            "--version",
            action="version",
            version=f"%(prog)s {VERSION}",
            help="show version",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            action="count",
            default=0,
            help="show more verbose output",
        )

        args = parser.parse_args()
        self.__handle_arguments(args)

    def __handle_arguments(self, args) -> None:
        """Parse setting arguments and options."""
        if args.verbose > 0:
            if self.logger.level != logging.DEBUG:
                self.logger.setLevel(logging.INFO)
                verbose = logging.StreamHandler()
                formatter = logging.Formatter("%(levelname)-8s %(message)s")
                verbose.setLevel(logging.INFO)
                verbose.setFormatter(formatter)
                self.logger.addHandler(verbose)
        if args.address:
            self.settings["ipc"]["host"] = args.address
        if args.port:
            self.settings["ipc"]["port"] = args.port
        if args.socket:
            self.settings["ipc"]["socket"] = args.socket
        if args.comport:
            self.settings["serial"]["port"] = args.comport
        if args.baudrate:
            self.settings["serial"]["baudrate"] = args.baudrate
        if args.timeout:
            self.settings["serial"]["timeout"] = args.timeout
        if args.save:
            self.logger.info("Saving settings to config file")
            settings.write_settings(self.settings, "daemon", update=False)
            sys.exit()
        if args.update:
            self.logger.info("Updating settings in config file")
            settings.write_settings(self.settings, "daemon", update=True)
            sys.exit()

    def __update_settings(self) -> None:
        """Update setttings if needed."""
        if self.device["brightness_min"]:
            self.settings["brightness_min"] = self.device["brightness_min"]
        if self.device["brightness_max"]:
            self.settings["brightness_max"] = self.device["brightness_max"]
        if self.device["current_color"]:
            self.current_color = self.device["current_color"]
        if self.device["current_brightness"]:
            self.current_brightness = self.device["current_brightness"]
        if self.device["current_mode"]:
            self.current_mode = self.device["current_mode"]
        if self.device["current_dim"]:
            self.current_dim = self.device["current_dim"]

    def run(self) -> None:
        """Run the main loop of the application."""
        try:
            self.ipc_active = True
            ipc_stop = threading.Event()
            ipc_thread = threading.Thread(
                target=self.ipc_process, daemon=True, args=(ipc_stop,)
            )
            ipc_thread.start()

            self.pinger_active = True
            pinger_stop = threading.Event()
            pinger_thread = threading.Thread(
                target=self.pinger_process, daemon=True, args=(pinger_stop,)
            )
            pinger_thread.start()

            self.__send_information_request()

            while self.ipc_active:
                self.__process_commands()
                time.sleep(0.5)  # NOTE: find better way of handling this

            ipc_stop.set()
            pinger_stop.set()
            ipc_thread.join()
            pinger_thread.join()

        except (KeyboardInterrupt, SystemExit):
            self.logger.info("DsulDaemon exiting.")

            self.serial_active = False
            self.ipc_active = False
            ipc_stop.set()
            self.pinger_active = False
            pinger_stop.set()

            self.deinit_serial()
            self.logger.debug("Serial shut down.")
            pinger_thread.join()
            self.logger.debug("Pinger thread joined")
            ipc_thread.join()
            self.logger.debug("IPC thread joined")
            sys.exit()

    # THREAD PROCESSES #

    def ipc_process(self, stop_event) -> None:
        """Handle IPC communication."""
        if self.settings["ipc"]["socket"]:
            if self.settings["ipc"]["socket"] == "":
                sys.exit(20)
            server_address = self.settings["ipc"]["socket"]
        else:
            server_address = (
                self.settings["ipc"]["host"],
                int(self.settings["ipc"]["port"]),
            )
        self.logger.info("IPC server starting (%s)", server_address)

        ipc_server = ipc.Server(
            address=server_address,
            callback=self.__process_server_request,
        )
        ipc_server_thread = threading.Thread(
            target=ipc_server.run, daemon=False
        )
        ipc_server_thread.start()

        while not stop_event.is_set():
            stop_event.wait(timeout=1)  # just keep looping

        ipc_server.shutdown()
        ipc_server_thread.join()
        self.logger.info("IPC server stopped")

    def pinger_process(self, stop_event) -> None:
        """Send pings to device, to keep communication open."""
        self.logger.info("Pinger starting")

        while self.pinger_active and self.serial_active:
            starttime = time.time()

            while not stop_event.is_set():
                self.__send_ping()
                stop_event.wait(
                    timeout=30.0 - ((time.time() - starttime) % 30.0)
                )

        self.logger.info("Pinger stopped")

    # SERIAL #

    def init_serial(self) -> None:
        """Initilize serial communication."""
        try:
            if not self.ser.is_open:
                self.logger.info(
                    "Opening serial port " "(%s)",
                    self.settings["serial"]["port"],
                )
                self.ser.port = self.settings["serial"]["port"]
                self.ser.baudrate = int(self.settings["serial"]["baudrate"])
                self.ser.timeout = self.settings["serial"]["timeout"]
                self.ser.open()
                self.serial_active = True
                self.serial_verified = False
                time.sleep(2)  # wait until device is out of boot state
                self.__set_current_states()
        except serial.serialutil.SerialException:
            self.logger.error(
                "Failed to open serial port " "(%s)",
                self.settings["serial"]["port"],
            )
            self.serial_verified = False
            self.serial_active = False
        except IOError:
            self.logger.error(
                "Serial port does not exist. " "(%s)",
                self.settings["serial"]["port"],
            )
            self.serial_verified = False
            self.serial_active = False

    def deinit_serial(self) -> None:
        """De-initialize serial communication."""
        try:
            if self.ser is not None and self.ser.is_open:
                self.ser.close()
        except serial.serialutil.SerialException:
            self.logger.error(
                "An error occured when de-initializing serial port."
            )

    def read_serial(self) -> str:
        """Read and return data from serial port."""
        # read from buffer first
        i = self.serial_input_buffer.find(b"#")
        if i >= 0:
            # fmt: off
            read = self.serial_input_buffer[:i + 1]
            self.serial_input_buffer = self.serial_input_buffer[i + 1:]
            # fmt: on
            return str(read.decode())

        # if buffer was empty we read from serial
        try:
            while True:
                i = max(1, min(2048, self.ser.in_waiting))
                data = self.ser.read(i)
                i = data.find(b"#")

                if i >= 0:
                    # fmt: off
                    read = self.serial_input_buffer + data[:i + 1]
                    self.serial_input_buffer[0:] = data[i + 1:]
                    # fmt: on
                    self.serial_input_buffer = bytearray()
                    return str(read.decode())

                self.serial_input_buffer.extend(data)
        except serial.serialutil.SerialException:
            return ""

    def write_serial(self, message: str) -> bool:
        """Write data to the serial port."""
        try:
            self.ser.write(message.encode())
            return True
        except serial.serialutil.SerialException:
            return False

    def __get_serial_input(self) -> None:
        """Get serial input and process it."""
        input_data = self.read_serial()

        if input_data is not None or input_data != "":
            self.logger.debug("<S : %s", input_data)
            input_length = len(input_data)

            if input_length == 3:
                self.__handle_serial_command(input_data)
            else:
                self.__handle_serial_data(input_data)

    def __handle_serial_command(self, command: str) -> None:
        """Handle serial command."""
        if command == "-!#":  # resend/request data
            self.logger.info("Serial Response: Resend/Request")
        elif command == "-?#":  # ping
            self.logger.info("Serial Response: Ping")
            self.__send_ok()
        elif command == "+!#":  # ok
            self.logger.info("Serial Response: OK")
        elif command == "+?#":  # unknown/error
            self.logger.info("Serial Response: Unknown/Error")

        self.serial_verified = True

    def __handle_serial_data(self, data: str) -> None:
        """Handle serial data."""
        v_match = re.search(r"v(\d{3})\.(\d{3}).(\d{3})", str(data))
        ll_match = re.search(r"ll(\d{3})", str(data))
        lb_match = re.search(r"lb(\d{3}):(\d{3})", str(data))
        cc_match = re.search(r"cc(\d{2})(\d{2})(\d{2})", str(data))
        cb_match = re.search(r"cb(\d{3})", str(data))
        cm_match = re.search(r"cm(\d{3})", str(data))
        cd_match = re.search(r"cd(\d{1})", str(data))

        self.device["version"] = (
            (f"{int(v_match[1])}." f"{int(v_match[2])}." f"{int(v_match[3])}")
            if v_match
            else None
        )
        self.device["leds"] = int(ll_match[1]) if ll_match else None
        self.device["brightness_min"] = int(lb_match[1]) if lb_match else None

        self.device["brightness_max"] = int(lb_match[2]) if lb_match else None
        self.device["current_color"] = (
            (
                f"{int(cc_match[1])}:"
                f"{int(cc_match[2])}:"
                f"{int(cc_match[3])}"
            )
            if cc_match
            else None
        )
        self.device["current_brightness"] = (
            int(cb_match[1]) if cb_match else None
        )
        self.device["current_mode"] = int(cm_match[1]) if cm_match else None
        self.device["current_dim"] = int(cd_match[1]) if cd_match else None

        self.__update_settings()
        self.serial_verified = True

    # COMMAND HANDLING #

    def __process_commands(self) -> None:
        """Process the command queue."""
        retries = 0
        queue_count = len(self.send_commands)

        while queue_count > 0:
            command_item = self.send_commands.pop(0)
            queue_count -= 1
            self.init_serial()  # make sure serial connection is setup

            if self.serial_active:
                self.logger.debug("S> : %s", command_item["command"])

                try:
                    while not self.write_serial(str(command_item["command"])):
                        retries += 1

                        if retries >= 5:
                            retries = 0
                            raise Exception("Could not send serial command.")

                        time.sleep(1)

                    if command_item["want_reply"]:
                        self.__get_serial_input()
                except Exception as err:  # pylint: disable=W0703
                    self.logger.error("Sending serial command failed.")
                    self.logger.debug(
                        "Failed serial command: %s, error: %s",
                        command_item["command"],
                        err,
                    )
                    # sys.exit(1)  # don't exit on a send error
            else:
                self.logger.error(
                    "Serial connection not active. Can't send commands."
                )

    def __process_server_request(self, objects: Any) -> List:
        """Handle request sent to the IPC server."""
        self.logger.debug("<I : %s", objects)

        if self.serial_verified:
            for message_object in objects:
                if message_object.type[0] == "command":
                    action = "ACK"

                    if message_object.properties["key"] == "color":
                        valid = self.__send_color_command(
                            message_object.properties["value"]
                        )
                    elif message_object.properties["key"] == "brightness":
                        valid = self.__send_brightness_command(
                            message_object.properties["value"]
                        )
                    elif message_object.properties["key"] == "mode":
                        valid = self.__send_mode_command(
                            message_object.properties["value"]
                        )
                    elif message_object.properties["key"] == "dim":
                        valid = self.__send_dim_command(
                            int(message_object.properties["value"])
                        )

                    message = (
                        f"{message_object.properties['key']}="
                        f"{message_object.properties['value']}"
                    )

                    if not valid:
                        message = "Invalid command/argument"

                elif message_object.type[0] == "request":
                    result = self.__get_request_results(message_object)
                    action = result["action"]
                    message = result["message"]
                else:
                    action = "ACK"
                    message = "Unknown event type"

            response = [ipc.Response(f"{action}, {message}")]
        else:
            response = [ipc.Response("ACK, No serial connection")]

        self.logger.debug("I> : %s", response)

        return response

    def __set_current_states(self) -> None:
        """Set current states, if any."""
        if self.current_mode:
            self.__send_mode_command(str(self.current_mode))
        elif self.current_color:
            self.__send_color_command(self.current_color)
        elif self.current_brightness:
            self.__send_brightness_command(self.current_brightness)
        elif self.current_dim:
            self.__send_dim_command(int(self.current_dim))

    # SEND ACTIONS #

    def __send_color_command(self, value: str) -> bool:
        """Send command to set color."""
        try:
            red, green, blue = value.split(":")
            self.logger.info("Setting color: '%s,%s,%s'", red, green, blue)
            self.current_color = value
            self.send_commands.append(
                {
                    "command": "+l{:03d}{:03d}{:03d}#".format(
                        int(red), int(green), int(blue)
                    ),
                    "want_reply": True,
                }
            )

            return True
        except ValueError:
            self.logger.warning("Invalid argument: '%s'", value)

        return False

    def __send_brightness_command(self, value: str) -> bool:
        """Send command to set brightness."""
        if (
            int(value) >= self.settings["brightness_min"]
            and int(value) <= self.settings["brightness_max"]
        ):
            self.logger.info("Setting brightness: '%s'", value)
            self.current_brightness = value
            self.send_commands.append(
                {"command": "+b{:03d}#".format(int(value)), "want_reply": True}
            )

            return True

        self.logger.warning("Invalid argument: '%s'", value)
        return False

    def __send_mode_command(self, value: str) -> bool:
        """Send command to set the mode."""
        if value in self.settings["modes"]:
            self.logger.info("Setting mode: '%s'", value)
            self.current_mode = int(self.settings["modes"][value])
            self.send_commands.append(
                {
                    "command": "+m{:03d}#".format(self.current_mode),
                    "want_reply": True,
                }
            )

            return True

        self.logger.warning("Invalid argument: '%s'", value)
        return False

    def __send_dim_command(self, value: int) -> bool:
        """Send command to set the dim mode."""
        if value >= 0 or value <= 1:
            self.logger.info("Setting dim mode: '%s'", value)
            self.current_dim = int(value)
            self.send_commands.append(
                {
                    "command": "+d{:01d}#".format(self.current_dim),
                    "want_reply": True,
                }
            )

            return True

        self.logger.warning("Invalid argument: '%s'", value)
        return False

    def __send_information_request(self) -> None:
        """Send request to device for information."""
        self.logger.info("Asking device for information")
        self.send_commands.append({"command": "-!#", "want_reply": True})

    def __send_ping(self) -> None:
        """Send ping to device."""
        self.logger.info("Sending ping to device")
        self.send_commands.append({"command": "-?#", "want_reply": True})

    def __send_ok(self) -> None:
        """Send OK to device."""
        self.logger.info("Sending OK to device")
        self.send_commands.append({"command": "+!#", "want_reply": False})

    # GET ACTIONS #

    def __get_request_results(self, message_object: Any) -> Dict[str, str]:
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
                message = str(self.current_mode)
            elif message_object.properties["value"] == "dim":
                message = str(self.current_dim)
        elif message_object.properties["key"] == "information":
            action = "OK"
            message = self.give_information()

        return {"action": action, "message": message}

    def give_information(self) -> str:
        """Give server information to the client."""
        return (
            f"daemon={VERSION};"
            f"fw={self.device['version']};"
            f"modes={self.settings['modes']};"
            f"brightness_min={self.settings['brightness_min']};"
            f"brightness_max={self.settings['brightness_max']};"
            f"current_mode={self.current_mode};"
            f"current_brightness={self.current_brightness};"
            f"current_color={self.current_color};"
            f"current_dim={self.current_dim};"
        )


if __name__ == "__main__":
    sys.exit(main())
