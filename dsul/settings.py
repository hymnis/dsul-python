"""DSUL - Disturb State USB Light : Application settings handling."""

import configparser
from pathlib import Path
from typing import Any, Dict

_config_file = Path(str(Path.home())) / ".dsul.cfg"


def get_settings(settings_type: str) -> Dict[str, Any]:
    """Get settings from config file or default values."""
    config = configparser.RawConfigParser()

    if _config_file.exists():
        config.read(_config_file)

    settings: Dict[str, Any] = {
        "ipc": {},
        "socket": "",
        "serial": {},
        "modes": {},
        "brightness_min": 0,
        "brightness_max": 0,
        "colors": {},
    }

    settings["ipc"]["host"] = config.get("IPC", "host", fallback="localhost")
    settings["ipc"]["port"] = config.get("IPC", "port", fallback="5795")
    settings["ipc"]["socket"] = config.get("IPC", "socket", fallback="")
    settings["modes"]["solid"] = config.getint("Modes", "solid", fallback=1)
    settings["modes"]["blink"] = config.getint("Modes", "blink", fallback=2)
    settings["modes"]["flash"] = config.getint("Modes", "flash", fallback=3)
    settings["modes"]["pulse"] = config.getint("Modes", "pulse", fallback=4)
    settings["brightness_min"] = config.getint("Brightness", "min", fallback=0)
    settings["brightness_max"] = config.getint(
        "Brightness", "max", fallback=150
    )

    if settings_type == "daemon":
        settings["serial"]["port"] = config.get(
            "Serial", "port", fallback="/dev/ttyUSB0"
        )
        settings["serial"]["baudrate"] = config.get(
            "Serial", "baudrate", fallback="38400"
        )
        settings["serial"]["timeout"] = config.get(
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


def write_settings(
    settings: Dict[str, Any], settings_type: str, update: bool
) -> None:
    """Write settings to config file, either updating or creating a new one."""
    default = get_settings(settings_type)
    config = configparser.RawConfigParser()

    if update and _config_file.exists():
        config.read(_config_file)

    ipc_diff = {
        k: settings["ipc"][k]
        for k, _ in set(settings["ipc"].items()) - set(default["ipc"].items())
    }
    if ipc_diff:
        if "IPC" not in config.sections():
            config.add_section("IPC")
        for diff_key, diff_value in ipc_diff.items():
            config.set("IPC", diff_key, diff_value)

    if settings_type == "daemon":
        serial_diff = {
            k: settings["serial"][k]
            for k, _ in set(settings["serial"].items())
            - set(default["serial"].items())
        }
        if serial_diff:
            if "Serial" not in config.sections():
                config.add_section("Serial")
            for diff_key, diff_value in serial_diff.items():
                config.set("Serial", diff_key, diff_value)

    with open(_config_file, "w") as file_handle:
        config.write(file_handle)
