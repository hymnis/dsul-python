"""DSUL - Disturb State USB Light : Application settings handling."""

import configparser
from pathlib import Path
from typing import Any, Dict


def get_settings(settings_type: str) -> Dict[str, Any]:
    """Get settings from config file."""
    home = str(Path.home())
    config_file = Path(home) / ".dsul.cfg"

    config = configparser.RawConfigParser()

    if config_file.exists():
        config.read(config_file)

    settings: Dict[str, Any] = {
        "ipc": {},
        "serial": {},
        "modes": {},
        "leds": 0,
        "brightness_min": 0,
        "brightness_max": 0,
        "colors": {},
    }

    settings["ipc"]["host"] = config.get("IPC", "host", fallback="localhost")
    settings["ipc"]["port"] = config.getint("IPC", "port", fallback=5795)
    settings["modes"]["solid"] = config.getint("Modes", "solid", fallback=1)
    settings["modes"]["blink"] = config.getint("Modes", "blink", fallback=2)
    settings["modes"]["flash"] = config.getint("Modes", "flash", fallback=3)
    settings["brightness_min"] = config.getint("Brightness", "min", fallback=0)
    settings["brightness_max"] = config.getint(
        "Brightness", "max", fallback=150
    )
    settings["leds"] = config.getint("Leds", "number", fallback=1)

    if settings_type == "daemon":
        settings["serial"]["port"] = config.get(
            "Serial", "port", fallback="/dev/ttyUSB0"
        )
        settings["serial"]["baudrate"] = config.getint(
            "Serial", "baudrate", fallback=38400
        )
        settings["serial"]["timeout"] = config.getint(
            "Serial", "timeout", fallback=None
        )
    elif settings_type == "cli":
        settings["colors"]["red"] = config.get(
            "Colors", "red", fallback="255,0,0"
        ).split(",")
        settings["colors"]["green"] = config.get(
            "Colors", "green", fallback="0,255,0"
        ).split(",")
        settings["colors"]["blue"] = config.get(
            "Colors", "blue", fallback="0,0,255"
        ).split(",")
        settings["colors"]["cyan"] = config.get(
            "Colors", "cyan", fallback="0,255,255"
        ).split(",")
        settings["colors"]["white"] = config.get(
            "Colors", "white", fallback="255,255,200"
        ).split(",")
        settings["colors"]["warmwhite"] = config.get(
            "Colors", "warmwhite", fallback="255,230,200"
        ).split(",")
        settings["colors"]["purple"] = config.get(
            "Colors", "purple", fallback="255,0,200"
        ).split(",")
        settings["colors"]["magenta"] = config.get(
            "Colors", "magenta", fallback="255,0,50"
        ).split(",")
        settings["colors"]["yellow"] = config.get(
            "Colors", "yellow", fallback="255,90,0"
        ).split(",")
        settings["colors"]["orange"] = config.get(
            "Colors", "orange", fallback="255,20,0"
        ).split(",")
        settings["colors"]["black"] = config.get(
            "Colors", "black", fallback="0,0,0"
        ).split(",")

    return settings


def write_settings(settings: Dict[str, Any]) -> None:
    """Write settings to config file."""
    home = str(Path.home())
    config_file = Path(home) / ".dsul.cfg"

    config = configparser.RawConfigParser()

    if config_file.exists():
        config.read(config_file)

    # TODO: set values from 'settings' to config object

    with open(config_file, "w") as file_handle:
        config.write(file_handle)
