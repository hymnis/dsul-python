# DSUL - Disturb State USB Light

[![Build Status](https://travis-ci.org/hymnis/dsul-python.svg?branch=master)](https://travis-ci.org/hymnis/dsul-python)
[![Maintainability](https://api.codeclimate.com/v1/badges/0a360f196a019278c3eb/maintainability)](https://codeclimate.com/github/hymnis/dsul-python/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/0a360f196a019278c3eb/test_coverage)](https://codeclimate.com/github/hymnis/dsul-python/test_coverage)
[![License MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)

The goal of the project is to have a USB connected light, that can be be set to different colors, with adjustable brightness and different modes, which can communicate the users current preference regarding being disturbed.

This implementation used Python 3.x for both daemon/server and client. It should work on most platforms as it uses as few and standard libraries as possible. Using sockets is currently not supported on Windows though.


## Hardware

The hardware used is an Arduino connected to a NeoPixel module. The project was developed using an Arduino Nano, but should work on most models as long as the firmware fit and it has enough RAM for the number of LED's used in the module.

The firmware project is available at [hymnis/dsul-arduino](https://github.com/hymnis/dsul-arduino).


## Firmware

As both FW (firmware) and SW (software) needs to talk to each other, not all combinations of versions work. Make sure that the FW and SW versions are compatible with each other. The latest (stable) versions usually has the best support. For more information about compatibility, see the [Firmware](https://github.com/hymnis/dsul-python/wiki/Firmware) wiki page.


## Installation

If the package isn't available from package archive, build it from source. DSUL is a proper python project and can be built into package using PEP517.

Build artifacts, found in the `dist` directory, include a .tar.gz and a .whl package.

### Build package(s)

```
python -m pep517.build .
```

### Install package

```
pip install dist/dsul-<version>-py3-none-any.whl
```


## Configuration

Both daemon and client calls the same method to get configuration settings. All settings have a default fallback but if a file named `.dsul.cfg` exists in the users home directory, it will be read and used. This is a simple ini style configuration that contains the different colors, modes and COM port etc. Some of the settings can be overridden by arguments (as settings are read before the application arguments).


## Daemon
This part handles communication with the hardware (serial connection) and allows clients to send commands (via IPC connection).

As module: `python -m dsul.daemon [arguments]`  
As package: `dsul-daemon [arguments]`

### Options

    --help                    Show help and usage information.
    --save                    Save (non-default) settings to config file.
    --update                  Update config file with new settings.
    --version                 Show current version.
    -h, --host <host>         The hostname/address to expose IPC server on. [default: localhost]
    -p, --port <port>         The port number used for the IPC server. [default: 5795]
    -s, --socket <socket>     The socket to use for IPC server (disables TCP, -h and -p aren't needed or used).
    -c, --comport <comport>   The COM port to use. [default: /dev/ttyUSB0]
    -b, --baudrate <baudrate> The baudrate to use with the COM port. [default: 38400]
    -t, --timeout <timeout>   The connection timeout to use for COM port (in seconds). [default: 1]
    -v, --verbose             Show more detailed output.


## CLI client
Used to communicate with the daemon through IPC. TCP/IP or Unix domain socket can be used (TCP/IP is default).

As module: `python -m dsul.cli [arguments]`  
As package: `dsul-cli [arguments]`

### Options

    --help                         Show help and usage information.
    --save                         Save (non-default) settings to config file.
    --update                       Update config file with new settings.
    --version                      Show current version.
    -l, --list                     List acceptable values for color, brightness and mode.
    -c, --color <color>            Set color to given value (must be one of the predefined colors).
    -b, --brightness <brightness>  Set brightness to given value.
    -m, --mode <mode>              Set mode to given value (must be on of the predefined modes).
    -d, --dim                      Turn on color dimming.
    -u, --undim                    Turn off color dimming.
    -h, --host <host>              The hostname/address of the IPC server. [default: localhost]
    -p, --port <port>              The port number used to connect to the IPC server. [default: 5795]
    -s, --socket <socket>          The socket to use for IPC server (disables TCP, -h and -p aren't needed or used).
    -v, --verbose                  Show more detailed output.


## Demo
Starting the daemon and receiving a command from CLI application via IPC (TCP/IP), in verbose mode.
![daemon_verbose](assets/daemon_verbose.gif)

Sending a command to the daemon via IPC (TCP/IP) and getting response in verbose mode.
![cli_verbose](assets/cli_verbose.gif)


## Development
This is the basic flow for development on the project. Step 1-2 should only have to be run once, while 3-8 is the continuous development cycle.

1. Install python requirements (`pip install -r requirements.development.txt`)
0. Initialize pre-commit (`pre-commit install`)
0. Create feature branch
0. Develop stuff
0. Format and lint
0. Test
0. Commit changes
0. Push changes

### Requirements
As this repo uses [pre-commit](https://pre-commit.com/) that does linting and format checking, requirements in `requirements.development.txt`). [pre-commit](https://pre-commit.com/) is also one of the requirements and must be installed prior to commit, for it to work.

### Formatting
All python code should be formatted by `black`. If it's not it will be caught by the pre-commit hook. Includes must be sorted by `isort`.

### Linting and checks
To check the code itself we use `flake8`, `pylint` and `mypy`.

### Testing
Tests are located in the _tests_ directory. They should be named according to format: `test_<module name>.py`

To run all tests (with coverage report), use: `pytest` or if you only want to test a specific unittest module: `python -m unittest tests.test_<module name>`.

### pre-commit
Current configuration will lint and format check, mostly python, code, as well as check files for strings (like "TODO" and "DEBUG") and missed git merge markings.
Look in `.pre-commig-config.yaml` for exact order of tasks and their settings.


## Acknowledgements

- `ipc` module is based on the work of Dan Krause.  
   Check it out at: [https://gist.github.com/dankrause/9607475](https://gist.github.com/dankrause/9607475)
- `mockserial` module is based on the work of D. Thiebaut.  
  Check it out at: [http://www.science.smith.edu/dftwiki/index.php/PySerial_Simulator](http://www.science.smith.edu/dftwiki/index.php/PySerial_Simulator)
