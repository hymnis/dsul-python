#!/usr/bin/env python
"""DSUL - Disturb State USB Light : CLI application."""

import configparser
import getopt
import logging
import re
import sys
from typing import Dict, List, Union

import ipc


class DsulCli:
    """DSUL CLI application class."""

    retries = 0
    colors: Dict[str, List[str]] = {}
    modes: List[str] = []
    ipc: Dict[str, Union[int, str]] = {}

    def __init__(self, argv) -> None:
        """Initialize the class."""
        print("[] DSUL CLI")
        logformat = (
            "[%(asctime)s] {%(pathname)s} " "%(levelname)s - %(message)s"
        )
        logging.basicConfig(
            level=logging.WARNING,
            filename="cli.log",
            format=logformat,
            datefmt="%H:%M:%S",
        )
        # fmt: off
        logpath = (
            logging.getLoggerClass().
            root.handlers[0].baseFilename)  # type: ignore
        # fmt: on
        print(f"Log file at: {logpath}")

        self.get_settings()
        self.read_argument(argv)

    def __missing__(self, key):
        """Log and return missing key information."""
        message = f"{key} not present in the dictionary!"
        logging.warning(message)
        return message

    def __str__(self):
        """Return a string value representing the object."""
        message = "DsuCli"
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

        self.modes = config.get("Modes", "types").split(",")

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

    def read_argument(self, argv):
        """Parse command line arguments."""
        ready = False
        help_string = (
            "dsul_cli.py --help -l -c <color> -m <mode> "
            "-b <brightness> -h <host> -p <port>"
        )

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
                # TODO: validate arg before using the value
                self.sequence_done = False
                self.ipc_send("command", "color", arg)
                ready = True
            elif opt in ("-b", "--brightness"):
                # TODO: validate arg before using the value
                self.sequence_done = False
                self.ipc_send("command", "brightness", arg)
                ready = True
            elif opt in ("-m", "--mode"):
                # TODO: validate arg before using the value
                self.sequence_done = False
                self.ipc_send("command", "mode", arg)
                ready = True

        if not ready:
            logging.error("Missing commands and/or arguments")
            sys.exit(1)

    def ipc_send(self, type: str, key: str, value: str) -> None:
        """Send IPC call to daemon."""
        try:
            # Send command to daemon
            server_address = (self.ipc["host"], self.ipc["port"])
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
            logging.error("Key error")
            sys.exit(1)
        except ipc.UnknownMessage:
            logging.error("Unknown message")
            sys.exit(1)
        except ipc.ConnectionRefused:
            logging.error("Connection was refused")
            sys.exit(2)

    def handle_response(self, response):
        """Handle the reponse from daemon."""
        response = response[0].text[0]

        key, value = re.split(r",", response, 1)
        key = key.strip()
        value = value.strip()

        if key == "OK":
            logging.info("Success")
            self.sequence_done = True
        elif key == "NOK":
            logging.info("Not OK")
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

            self.sequence_done = True

    def list_information(self):
        """Print out all modes and colors."""
        print("[modes]")
        for mode in self.modes:
            print("- {}".format(mode))

        print("\n[colors]")
        for color in self.colors:
            print("- {}".format(color))


if __name__ == "__main__":
    APP = DsulCli(sys.argv[1:])
