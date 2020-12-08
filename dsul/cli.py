#!/usr/bin/env python
"""DSUL - Disturb State USB Light : CLI application."""

import getopt
import logging
import re
import sys
from typing import Any, Dict, List, Union, no_type_check

from . import DEBUG, VERSION, ipc, settings


def main():
    """Run the application."""
    DsulCli(sys.argv[1:])


class DsulCli:
    """DSUL CLI application class."""

    logger: Any = None
    retries: int = 0
    settings: Dict[str, Any] = {}
    colors: Dict[str, List[str]] = {}
    modes: List[str] = []
    ipc: Dict[str, Union[int, str]] = {}
    command_queue: List[Dict[str, str]] = []
    sequence_done = True
    waiting_for_reply: bool = False
    current: Dict[str, str] = {
        "color": "n/a",
        "mode": "n/a",
        "brightness": "n/a",
        "dim": "n/a",
    }

    @no_type_check
    def __init__(self, argv) -> None:
        """Initialize the class."""
        if DEBUG:
            logformat = (
                "[%(asctime)s] %(levelname)-8s {%(pathname)s:%(lineno)d} "
                "- %(message)s"
            )
            loglevel = logging.DEBUG
        else:
            logformat = "%(levelname)-8s %(message)s"
            loglevel = logging.WARNING

        logging.basicConfig(
            level=loglevel,
            format=logformat,
            datefmt="%H:%M:%S",
        )
        self.logger = logging.getLogger(__name__)

        self.settings = settings.get_settings("cli")
        self.read_arguments(argv)
        self.logger.info("Requesting server information")
        self.requst_server_information()
        self.perform_actions()

    def __missing__(self, key) -> str:
        """Log and return missing key information."""
        message = f"{key} not present in the dictionary!"
        self.logger.warning(message)
        return message

    def __str__(self) -> str:
        """Return a string value representing the object."""
        message = (
            "DsulCli<>(logger=val, retries=val, settings=val, colors=val, "
            "modes=val, ipc=val, command_queue=val, sequence_done=val, "
            "waiting_for_reply=val, current=val)"
        )
        return message

    def read_arguments(self, argv) -> None:
        """Get command line arguments and options."""
        try:
            opts, args = getopt.getopt(  # pylint: disable=W0612
                argv,
                "lh:p:c:m:b:dus:v",
                [
                    "help",
                    "list",
                    "host=",
                    "port=",
                    "color=",
                    "mode=",
                    "brightness=",
                    "dim",
                    "undim",
                    "socket=",
                    "save",
                    "update",
                    "version",
                    "verbose",
                ],
            )
        except getopt.GetoptError:
            opts = [
                ("--help", ""),
            ]

        # parse settings before taking action
        for item in opts:
            opts[:] = [
                item for item in opts if not self.parse_setting_argument(item)
            ]

        # parse print and action statements
        for opt, arg in opts:
            self.parse_print_argument(opt)
            self.parse_action_argument(opt, arg)

    def parse_setting_argument(self, item) -> bool:
        """Parse setting arguments and options."""
        (opt, arg) = item

        if opt in ("-v", "--verbose"):
            if self.logger.level != logging.DEBUG:
                self.logger.setLevel(logging.INFO)
            return True
        if opt in ("-p", "--port"):
            self.settings["ipc"]["port"] = arg
            return True
        if opt in ("-h", "--host"):
            self.settings["ipc"]["host"] = arg
            return True
        if opt in ("-s", "--socket"):
            self.settings["ipc"]["socket"] = arg
            return True

        return False

    def parse_print_argument(self, opt) -> None:
        """Parse print arguments and options."""
        help_string = (
            "Usage: \n\n"
            "dsul-cli <arguments>\n\n"
            "--help\t\t\tShow (this) help text.\n"
            "--save\t\t\tCreate/overwrite config file with given settings.\n"
            "--update\t\tUpdate config file with given settings.\n"
            "--version\t\tShow version.\n"
            "-l, --list\t\tList settings and limits.\n"
            "-c, --color <value>\tSet given color.\n"
            "-m, --mode <value>\tSet given mode.\n"
            "-b, brightness <value>\tSet given brightness.\n"
            "-d, --dim\t\tDim colors.\n"
            "-u, --undim\t\tUn-dim colors.\n"
            "-h, --host <host>\tUse given host when connecting to server.\n"
            "-p, --port <port>\tUse given port when connecting to server.\n"
            "-s, --socket <socket>\tUse given socket when connecting to "
            "server.\n"
            "-v, --verbose\t\tShow more output."
        )
        version_string = f"Version {VERSION}"

        if opt == "--help":
            print(help_string)
        elif opt == "--version":
            print(version_string)
        elif opt in ("-l", "--list"):
            self.requst_server_information()
            self.list_information()
        elif opt == "--save":
            self.logger.info("Saving settings to config file")
            settings.write_settings(self.settings, "cli", update=False)
        elif opt == "--update":
            self.logger.info("Updating settings in config file")
            settings.write_settings(self.settings, "cli", update=True)
        else:
            return

        sys.exit()

    def parse_action_argument(self, opt, arg) -> None:
        """Parse action arguments and options."""
        if opt in ("-c", "--color"):
            self.set_color(arg)
        elif opt in ("-b", "--brightness"):
            self.set_brightness(arg)
        elif opt in ("-m", "--mode"):
            self.set_mode(arg)
        elif opt in ("-d", "--dim"):
            self.set_dim("1")
        elif opt in ("-u", "--undim"):
            self.set_dim("0")

    def set_color(self, color) -> None:
        """Send command to set color."""
        if color in self.settings["colors"]:
            color_values = self.settings["colors"][color]
            command_value = (
                f"{color_values[0]}:{color_values[1]}:{color_values[2]}"
            )
            self.sequence_done = False
            self.command_queue.append(
                {"type": "command", "key": "color", "value": command_value}
            )
        else:
            self.logger.error("Specified color isn't supported (%s)", color)
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
            self.logger.error(
                "Specified brightness isn't supported (%s)", brightness
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
            self.logger.error("Specified mode isn't supported (%s)", mode)
            sys.exit(1)

    def set_dim(self, dim) -> None:
        """Send command to toggle dim mode."""
        if dim >= 0 or dim <= 1:
            self.sequence_done = False
            self.command_queue.append(
                {"type": "command", "key": "dim", "value": dim}
            )
        else:
            self.logger.error("Specified dim mode isn't supported (%s)", dim)
            sys.exit(1)

    def perform_actions(self) -> None:
        """Perform the actions in the command queue."""
        for command in self.command_queue:
            self.ipc_send(command["type"], command["key"], command["value"])

    def ipc_send(self, event_type: str, key: str, value: str) -> None:
        """Send IPC call to daemon."""
        try:
            # Send command to daemon
            if self.settings["ipc"]["socket"]:
                server_address = self.settings["ipc"]["socket"]
            else:
                server_address = (
                    self.settings["ipc"]["host"],
                    int(self.settings["ipc"]["port"]),
                )

            user_input = [
                {
                    "class": "Event",
                    "args": event_type,
                    "kwargs": {"key": key, "value": value},
                }
            ]
            objects = ipc.Message.deserialize(user_input)
            self.logger.debug("Sending objects: %s", objects)
            with ipc.Client(server_address) as client:
                response = client.send(objects)
            self.logger.debug("Received objects: %s", response)
            self.handle_response(response)
        except KeyError:
            self.logger.error("Key error")
            sys.exit(1)
        except ipc.UnknownMessage:
            self.logger.error("Unknown IPC message")
            sys.exit(1)
        except ipc.ConnectionRefused:
            self.logger.error("IPC connection was refused")
            sys.exit(2)

    def handle_response(self, response) -> None:
        """Handle the response from daemon."""
        response = response[0].text[0]
        key, value = re.split(r",", response, 1)
        key = key.strip()
        value = value.strip()

        if key in ("OK", "NOK"):
            self.logger.info("Reply: %s", key)
            self.parse_response_value(value)
            self.sequence_done = True
        elif key == "ACK":
            self.handle_response_ack(value)

    def handle_response_ack(self, value: str) -> None:
        """Handle ACK response."""
        if value == "No serial connection":
            self.logger.warning("Server can't connect to device")
        elif value == "Invalid command/argument":
            self.logger.warning("Invalid command or argument sent")
        elif value == "Unknown event type":
            self.logger.warning("Unknown type of event sent")
        else:
            command, argument = re.split(r"=", value, 1)
            command = command.strip()
            argument = argument.strip()

            self.logger.info(
                "Command sent. Setting %s to %s", command, argument
            )
            self.ipc_send("request", "status", command)
            self.waiting_for_reply = True

        self.sequence_done = True

    def parse_response_value(self, value: str) -> None:
        """Parse the response value."""
        if self.waiting_for_reply:
            self.waiting_for_reply = False

            for item in value.split(";"):
                self.update_values(item)
        else:
            self.logger.debug("Received unexpected data: %s", value)

    def update_values(self, item: str) -> None:
        """Update values based on response."""
        try:
            key, val = item.split("=")

            if key == "modes":
                self.settings["modes"] = eval(val)  # pylint: disable=W0123
            elif key == "current_color":
                self.current["color"] = val
            elif key == "current_mode":
                self.current["mode"] = val
            elif key == "current_brightness":
                self.current["brightness"] = val
            elif key == "current_dim":
                self.current["dim"] = val
            elif key == "brightness_min":
                self.settings["brightness_min"] = int(val)
            elif key == "brightness_max":
                self.settings["brightness_max"] = int(val)
        except ValueError as err:
            self.logger.debug("Error while updating values. (error: %s)", err)

    def requst_server_information(self) -> None:
        """Request information from server; settings, limits etc."""
        self.sequence_done = False
        self.waiting_for_reply = True
        self.ipc_send("request", "information", "all")

    def list_information(self) -> None:
        """Print out all modes and colors."""
        print("\n[modes]")
        for mode in self.settings["modes"]:
            print(f"- {mode}")

        print("\n[colors]")
        for color in self.settings["colors"]:
            print(f"- {color}")

        print("\n[brightness]")
        print(f"- min = {self.settings['brightness_min']}")
        print(f"- max = {self.settings['brightness_max']}")

        print("\n[current]")
        print(f"- color = {self.current['color']}")
        print(f"- mode = {self.current['mode']}")
        print(f"- brightness = {self.current['brightness']}")
        print(f"- dim = {self.current['dim']}")


if __name__ == "__main__":
    sys.exit(main())
