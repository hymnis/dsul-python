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
    colors: Dict[str, List[str]] = {}
    modes: List[str] = []
    ipc: Dict[str, Union[int, str]] = {}
    command_queue: List[Dict[str, str]] = []
    waiting_for_reply: bool = False
    current_color = "n/a"
    current_mode = "n/a"
    current_brightness = "n/a"
    current_dim = "n/a"

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

        self.settings: Dict[str, Any] = settings.get_settings("cli")
        self.read_argument(argv)
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
            "DsulCli<>(logger=val, settings=val, sequence_done=val, "
            "command_queue=val, waiting_for_reply=val, current_mode=val, "
            "current_color=val, current_brightness=val, current_dim=val)"
        )
        return message

    def read_argument(self, argv) -> None:  # noqa
        """Parse command line arguments."""
        ready = {}
        color = ""
        mode = ""
        brightness = ""
        dim = ""
        help_string = (
            "dsul-cli --help -l -c <color> -m <mode> "
            "-b <brightness> -d -u -h <host> -p <port> -s <socket> --save "
            "--update --version --verbose"
        )
        version_string = f"Version {VERSION}"

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
            print(help_string)
            sys.exit(2)

        for opt, arg in opts:
            if opt == "--help":
                print(help_string)
                sys.exit()
            elif opt in ("-l", "--list"):
                try:
                    self.logger.info("Requesting server information")
                    self.requst_server_information()
                    self.perform_actions()
                except Exception:
                    pass
                self.list_information()
                sys.exit()
            elif opt in ("-c", "--color"):
                color = arg
                ready["color"] = True
            elif opt in ("-b", "--brightness"):
                brightness = arg
                ready["brightness"] = True
            elif opt in ("-m", "--mode"):
                mode = arg
                ready["mode"] = True
            elif opt in ("-d", "--dim"):
                dim = "1"
                ready["dim"] = True
            elif opt in ("-u", "--undim"):
                dim = "0"
                ready["dim"] = True
            elif opt in ("-p", "--port"):
                self.settings["ipc"]["port"] = arg
            elif opt in ("-h", "--host"):
                self.settings["ipc"]["host"] = arg
            elif opt in ("-s", "--socket"):
                self.settings["ipc"]["socket"] = arg
            elif opt == "--save":
                ready["save"] = True
            elif opt == "--update":
                ready["update"] = True
            elif opt == "--version":
                print(version_string)
                sys.exit()
            elif opt in ("-v", "--verbose"):
                if self.logger.level != logging.DEBUG:
                    self.logger.setLevel(logging.INFO)

        if True not in ready.values():
            self.logger.error("Missing commands and/or arguments")
            sys.exit(1)
        else:
            for key in ready.keys():
                if key == "color":
                    self.set_color(color)
                if key == "brightness":
                    self.set_brightness(brightness)
                if key == "mode":
                    self.set_mode(mode)
                if key == "dim":
                    self.set_dim(dim)
                if key == "save":
                    self.logger.info("Saving settings to config file")
                    settings.write_settings(self.settings, "cli", update=False)
                    sys.exit()
                if key == "update":
                    self.logger.info("Updating settings in config file")
                    settings.write_settings(self.settings, "cli", update=True)
                    sys.exit()

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
            self.logger.error("Specified color isn't supported (%s)" % color)
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
            self.logger.error("Specified mode isn't supported (%s)" % mode)
            sys.exit(1)

    def set_dim(self, dim) -> None:
        """Send command to toggle dim mode."""
        if dim >= 0 or dim <= 1:
            self.sequence_done = False
            self.command_queue.append(
                {"type": "command", "key": "dim", "value": dim}
            )
        else:
            self.logger.error("Specified dim mode isn't supported (%s)" % dim)
            sys.exit(1)

    def perform_actions(self) -> None:
        """Perform the actions in the command queue."""
        for command in self.command_queue:
            self.ipc_send(command["type"], command["key"], command["value"])

    def ipc_send(self, type: str, key: str, value: str) -> None:
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
                    "args": type,
                    "kwargs": {"key": key, "value": value},
                }
            ]
            objects = ipc.Message.deserialize(user_input)
            self.logger.debug(f"Sending objects: {objects}")
            with ipc.Client(server_address) as client:
                response = client.send(objects)
            self.logger.debug(f"Received objects: {response}")
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
        """Handle the reponse from daemon."""
        response = response[0].text[0]

        key, value = re.split(r",", response, 1)
        key = key.strip()
        value = value.strip()

        if key == "OK":
            self.logger.info("Reply: OK")
            self.parse_response_value(value)
            self.sequence_done = True
        elif key == "NOK":
            self.logger.info("Reply: Not OK")
            self.parse_response_value(value)
            self.sequence_done = True
        elif key == "ACK":
            if value == "No serial connection":
                self.logger.warning("Daemon can't connect to device")
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

    def parse_response_value(self, value: str):  # noqa
        """Parse the response value."""
        if self.waiting_for_reply:
            self.waiting_for_reply = False

            for item in value.split(";"):
                try:
                    key, val = item.split("=")

                    if key == "modes":
                        self.settings["modes"] = eval(val)
                    elif key == "current_color":
                        self.current_color = val
                    elif key == "current_mode":
                        self.current_mode = val
                    elif key == "current_brightness":
                        self.current_brightness = val
                    elif key == "current_dim":
                        self.current_dim = val
                    elif key == "brightness_min":
                        self.settings["brightness_min"] = int(val)
                    elif key == "brightness_max":
                        self.settings["brightness_max"] = int(val)
                except ValueError:
                    pass

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
        print(f"- color = {self.current_color}")
        print(f"- mode = {self.current_mode}")
        print(f"- brightness = {self.current_brightness}")
        print(f"- dim = {self.current_dim}")


if __name__ == "__main__":
    sys.exit(main())
