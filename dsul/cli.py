#!/usr/bin/env python
"""DSUL - Disturb State USB Light : CLI application."""

import argparse
import logging
import re
import sys
from typing import Any, Dict, List, Union, no_type_check

from . import DEBUG, VERSION, ipc, settings


def main():
    """Run the application."""
    DsulCli()


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
    def __init__(self) -> None:
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
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.logger = logging.getLogger(__name__)

        self.settings = settings.get_settings("cli")
        self.__read_arguments()
        self.logger.info("Requesting server information")
        self.__requst_server_information()
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

    def __read_arguments(self) -> None:
        """Get command line arguments and options."""
        parser = argparse.ArgumentParser(prog="dsul-cli")
        ipc_group = parser.add_mutually_exclusive_group()
        config_group = parser.add_mutually_exclusive_group()
        dim_group = parser.add_mutually_exclusive_group()

        # IPC
        ipc_group.add_argument(
            "-a",
            "--address",
            nargs="?",
            help="use given host address when connecting to server",
        )
        ipc_group.add_argument(
            "-s",
            "--socket",
            nargs="?",
            help="use given socket when connecting to server",
        )
        parser.add_argument(
            "-p",
            "--port",
            type=int,
            nargs="?",
            help="use given port when connecting to server",
        )

        # LED's
        parser.add_argument(
            "-c",
            "--color",
            nargs="?",
            choices=self.settings["colors"],
            help="set given color",
        )
        parser.add_argument(
            "-m",
            "--mode",
            nargs="?",
            choices=self.settings["modes"],
            help="set given mode",
        )
        parser.add_argument(
            "-b",
            "--brightness",
            type=int,
            nargs="?",
            help="set given brightness",
        )
        dim_group.add_argument(
            "-d", "--dim", action="store_true", help="dim colors"
        )
        dim_group.add_argument(
            "-u", "--undim", action="store_true", help="un-dim colors"
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

        # Output
        parser.add_argument(
            "-l",
            "--list",
            action="store_true",
            help="list settings and limits",
        )
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
        actions = self.__handle_actions(args)

        if actions == 0:
            parser.print_help()

    def __handle_arguments(self, args) -> None:
        """Handle setting and print arguments and options."""
        if args.verbose > 0:
            if self.logger.level != logging.DEBUG:
                self.logger.setLevel(logging.INFO)
        if args.address:
            self.settings["ipc"]["host"] = args.address
        if args.port:
            self.settings["ipc"]["port"] = args.port
        if args.socket:
            self.settings["ipc"]["socket"] = args.socket
        if args.list:
            self.__requst_server_information()
            self.list_information()
            sys.exit()
        if args.save:
            self.logger.info("Saving settings to config file")
            settings.write_settings(self.settings, "cli", update=False)
            sys.exit()
        if args.update:
            self.logger.info("Updating settings in config file")
            settings.write_settings(self.settings, "cli", update=True)
            sys.exit()

    def __handle_actions(self, args) -> int:
        """Handle action arguments and options."""
        actions = 0

        if args.color:
            self.set_color(args.color)
            actions += 1
        if args.brightness:
            self.set_brightness(args.brightness)
            actions += 1
        if args.mode:
            self.set_mode(args.mode)
            actions += 1
        if args.dim:
            self.set_dim(1)
            actions += 1
        if args.undim:
            self.set_dim(0)
            actions += 1

        return actions

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
            self.__handle_response(response)
        except KeyError:
            self.logger.error("Key error")
            sys.exit(1)
        except ipc.UnknownMessage:
            self.logger.error("Unknown IPC message")
            sys.exit(1)
        except ipc.ConnectionRefused:
            self.logger.error("IPC connection was refused")
            sys.exit(2)

    def __handle_response(self, response) -> None:
        """Handle the response from daemon."""
        response = response[0].text[0]
        key, value = re.split(r",", response, 1)
        key = key.strip()
        value = value.strip()

        if key in ("OK", "NOK"):
            self.logger.info("Reply: %s", key)
            self.__parse_response_value(value)
            self.sequence_done = True
        elif key == "ACK":
            self.__handle_response_ack(value)

    def __handle_response_ack(self, value: str) -> None:
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

    def __parse_response_value(self, value: str) -> None:
        """Parse the response value."""
        if self.waiting_for_reply:
            self.waiting_for_reply = False

            for item in value.split(";"):
                self.__update_values(item)
        else:
            self.logger.debug("Received unexpected data: %s", value)

    def __update_values(self, item: str) -> None:
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

    def __requst_server_information(self) -> None:
        """Request information from server; settings, limits etc."""
        self.sequence_done = False
        self.waiting_for_reply = True
        self.ipc_send("request", "information", "all")

    def list_information(self) -> None:
        """Print out all modes and colors."""
        print("[modes]")
        for mode in self.settings["modes"]:
            print(f"- {mode}")

        print("\n[colors]")
        for color in self.settings["colors"]:
            print(f"- {color}")

        print("\n[brightness]")
        print(f"- min = {self.settings['brightness_min']}")
        print(f"- max = {self.settings['brightness_max']}")

        print("\n[current values]")
        print(f"- color = {self.current['color']}")
        print(f"- mode = {self.current['mode']}")
        print(f"- brightness = {self.current['brightness']}")
        print(f"- dim = {self.current['dim']}")


if __name__ == "__main__":
    sys.exit(main())
