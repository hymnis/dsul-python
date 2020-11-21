#!/usr/bin/env python
"""DSUL - Disturb State USB Light : CLI application."""

import getopt
import logging
import re
import sys
from typing import Any, Dict, List, Union, no_type_check

from . import DEBUG, VERSION, ipc, settings


class DsulCli:
    """DSUL CLI application class."""

    retries: int = 0
    colors: Dict[str, List[str]] = {}
    modes: List[str] = []
    ipc: Dict[str, Union[int, str]] = {}
    command_queue: List[Dict[str, str]] = []
    waiting_for_reply: bool = False

    @no_type_check
    def __init__(self, argv) -> None:
        """Initialize the class."""
        print("[] DSUL: CLI")

        if DEBUG:
            logformat = (
                "[%(asctime)s] {%(pathname)s:%(lineno)d} "
                "%(levelname)s - %(message)s"
            )
            loglevel = logging.DEBUG
        else:
            logformat = (
                "[%(asctime)s] {%(pathname)s} " "%(levelname)s - %(message)s"
            )
            loglevel = logging.INFO

        logging.basicConfig(
            level=loglevel,
            format=logformat,
            datefmt="%H:%M:%S",
        )

        self.settings: Dict[str, Any] = settings.get_settings("cli")
        self.read_argument(argv)
        self.requst_server_information()
        self.perform_actions()

    def __missing__(self, key) -> str:
        """Log and return missing key information."""
        message = f"{key} not present in the dictionary!"
        logging.warning(message)
        return message

    def __str__(self) -> str:
        """Return a string value representing the object."""
        message = "DsuCli"
        return message

    def read_argument(self, argv) -> None:  # noqa
        """Parse command line arguments."""
        ready = {}
        help_string = (
            "dsul-cli --help -l -c <color> -m <mode> "
            "-b <brightness> -h <host> -p <port> --version"
        )
        version_string = f"Version {VERSION}"

        try:
            opts, args = getopt.getopt(  # pylint: disable=W0612
                argv,
                "lh:p:c:m:b:",
                [
                    "help",
                    "list",
                    "host",
                    "port",
                    "color=",
                    "mode=",
                    "brightness=",
                    "version",
                ],
            )
        except getopt.GetoptError:
            print(help_string)
            sys.exit(2)

        for opt, arg in opts:
            if opt == "--help":
                print(help_string)
                sys.exit()
            elif opt in ("-l", "--list"):
                self.list_information()
                sys.exit()
            elif opt in ("-c", "--color"):
                ready["color"] = True
                self.set_color(arg)
            elif opt in ("-b", "--brightness"):
                ready["brigtness"] = True
                self.set_brightness(arg)
            elif opt in ("-m", "--mode"):
                ready["mode"] = True
                self.set_mode(arg)
            elif opt in ("-p", "--port"):
                self.settings["ipc"]["port"] = arg
            elif opt in ("-h", "--host"):
                self.settings["ipc"]["host"] = arg
            elif opt == "--version":
                print(version_string)
                sys.exit()

        if False in ready.values():
            logging.error("Missing commands and/or arguments")
            sys.exit(1)

    def set_color(self, color, index=0) -> None:
        """Send command to set color."""
        if color in self.settings["colors"]:
            color_values = self.settings["colors"][color]
            command_value = (
                f"{index}:{color_values[0]}:{color_values[1]}:"
                f"{color_values[2]}"
            )
            self.sequence_done = False
            self.command_queue.append(
                {"type": "command", "key": "color", "value": command_value}
            )
        else:
            logging.error("Specified color isn't supported (%s)" % color)
            sys.exit(1)

    def set_brightness(self, brightness) -> None:
        """Send command to set brightness."""
        if (
            int(brightness) >= self.settings["brightness_min"]
            and int(brightness) <= self.settings["brightness_max"]
        ):
            command_value = f"{brightness}"
            self.sequence_done = False
            self.command_queue.append(
                {
                    "type": "command",
                    "key": "brightness",
                    "value": command_value,
                }
            )
        else:
            logging.error(
                "Specified brightness isn't supported (%s)" % brightness
            )
            sys.exit(1)

    def set_mode(self, mode) -> None:
        """Send command to set mode."""
        if mode in self.settings["modes"]:
            self.sequence_done = False
            self.command_queue.append(
                {"type": "command", "key": "mode", "value": mode}
            )
        else:
            logging.error("Specified mode isn't supported (%s)" % mode)
            sys.exit(1)

    def perform_actions(self) -> None:
        """Perform the actions in the command queue."""
        for command in self.command_queue:
            self.ipc_send(command["type"], command["key"], command["value"])

    def ipc_send(self, type: str, key: str, value: str) -> None:
        """Send IPC call to daemon."""
        try:
            # Send command to daemon
            server_address = (
                self.settings["ipc"]["host"],
                self.settings["ipc"]["port"],
            )
            user_input = [
                {
                    "class": "Event",
                    "args": type,
                    "kwargs": {"key": key, "value": value},
                }
            ]
            objects = ipc.Message.deserialize(user_input)
            logging.debug(f"Sending objects: {objects}")
            with ipc.Client(server_address) as client:
                response = client.send(objects)
            logging.debug(f"Received objects: {response}")
            self.handle_response(response)
        except KeyError:
            logging.error("IPC: Key error")
            sys.exit(1)
        except ipc.UnknownMessage:
            logging.error("IPC: Unknown message")
            sys.exit(1)
        except ipc.ConnectionRefused:
            logging.error("IPC: Connection was refused")
            sys.exit(2)

    def handle_response(self, response) -> None:
        """Handle the reponse from daemon."""
        response = response[0].text[0]

        key, value = re.split(r",", response, 1)
        key = key.strip()
        value = value.strip()

        if key == "OK":
            logging.info("Success")
            self.parse_response_value(value)
            self.sequence_done = True
        elif key == "NOK":
            logging.info("Not OK")
            self.parse_response_value(value)
            self.sequence_done = True
        elif key == "ACK":
            if value == "No serial connection":
                logging.info("Daemon can't connect to device")
            elif value == "Invalid command/argument":
                logging.info("Invalid command or argument sent")
            elif value == "Unknown event type":
                logging.info("Unknown type of event sent")
            else:
                command, argument = re.split(r"=", value, 1)
                command = command.strip()
                argument = argument.strip()

                logging.info(
                    "Command sent. " f"Setting {command} to {argument}"
                )
                self.ipc_send("request", "status", command)
                self.waiting_for_reply = True

            self.sequence_done = True

    def parse_response_value(self, value: str):
        """Parse the response value."""
        if self.waiting_for_reply:
            response = value.split(";")
            self.waiting_for_reply = False
            if "version" in response:
                print("got server information")
                for setting in response:
                    print(f"setting: {setting}")

    def requst_server_information(self) -> None:
        """Request information from server; settings, limits etc."""
        self.ipc_send("request", "information", "all")
        self.sequence_done = False
        self.waiting_for_reply = True

    def list_information(self) -> None:
        """Print out all modes and colors."""
        print("\n[modes]")
        for mode in self.settings["modes"]:
            print(f"- {mode}")

        print("\n[colors]")
        for color in self.settings["colors"]:
            print(f"- {color}")

        print("\n[brigtness]")
        print(f"- min = {self.settings['brightness_min']}")
        print(f"- max = {self.settings['brightness_max']}")


if __name__ == "__main__":
    APP = DsulCli(sys.argv[1:])
