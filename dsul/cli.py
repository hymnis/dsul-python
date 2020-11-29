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

    @no_type_check
    def __init__(self, argv) -> None:
        """Initialize the class."""
        print("[] DSUL: CLI")

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
            "current_color=val, current_brightness=val)"
        )
        return message

    def read_argument(self, argv) -> None:  # noqa
        """Parse command line arguments."""
        ready = {}
        color = ""
        mode = ""
        brightness = ""
        index = 0
        help_string = (
            "dsul-cli --help -l -c <color> -i <index> -m <mode> "
            "-b <brightness> -h <host> -p <port> -s <socket> --version "
            "--verbose"
        )
        version_string = f"Version {VERSION}"

        try:
            opts, args = getopt.getopt(  # pylint: disable=W0612
                argv,
                "lh:p:c:i:m:b:s:v",
                [
                    "help",
                    "list",
                    "host=",
                    "port=",
                    "color=",
                    "index=",
                    "mode=",
                    "brightness=",
                    "socket=",
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
                    self.requst_server_information()
                    self.perform_actions()
                except Exception:
                    pass
                self.list_information()
                sys.exit()
            elif opt in ("-c", "--color"):
                color = arg
                ready["color"] = True
            elif opt in ("-i", "--index"):
                if int(arg) <= self.settings["leds"]:
                    index = int(arg)
                else:
                    self.logger.error(
                        "Specified LED index is outside supported range (%s)"
                        % arg
                    )
                    sys.exit(1)
            elif opt in ("-b", "--brightness"):
                brightness = arg
                ready["brightness"] = True
            elif opt in ("-m", "--mode"):
                mode = arg
                ready["mode"] = True
            elif opt in ("-p", "--port"):
                self.settings["ipc"]["port"] = arg
            elif opt in ("-h", "--host"):
                self.settings["ipc"]["host"] = arg
            elif opt in ("-s", "--socket"):
                self.settings["socket"] = arg
            elif opt == "--version":
                print(version_string)
                sys.exit()
            elif opt in ("-v", "--verbose"):
                self.logger.setLevel(logging.INFO)

        if True not in ready.values():
            self.logger.error("Missing commands and/or arguments")
            sys.exit(1)
        else:
            for key in ready.keys():
                if key == "color":
                    self.set_color(color, index)
                if key == "brightness":
                    self.set_brightness(brightness)
                if key == "mode":
                    self.set_mode(mode)

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

    def perform_actions(self) -> None:
        """Perform the actions in the command queue."""
        for command in self.command_queue:
            self.ipc_send(command["type"], command["key"], command["value"])

    def ipc_send(self, type: str, key: str, value: str) -> None:
        """Send IPC call to daemon."""
        try:
            # Send command to daemon
            if self.settings["socket"]:
                server_address = self.settings["socket"]
            else:
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
            self.logger.info("Success")
            self.parse_response_value(value)
            self.sequence_done = True
        elif key == "NOK":
            self.logger.info("Not OK")
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
                    elif key == "brightness_min":
                        self.settings["brightness_min"] = int(val)
                    elif key == "brightness_max":
                        self.settings["brightness_max"] = int(val)
                    elif key == "leds":
                        self.settings["leds"] = int(val)
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


if __name__ == "__main__":
    sys.exit(main())
