# DSUL - Disturb State USB Light

[![Build Status](https://travis-ci.org/hymnis/dsul-python.svg?branch=master)](https://travis-ci.org/hymnis/dsul-python)
[![Maintainability](https://api.codeclimate.com/v1/badges/0a360f196a019278c3eb/maintainability)](https://codeclimate.com/github/hymnis/dsul-python/maintainability)
[![Test Coverage](https://api.codeclimate.com/v1/badges/0a360f196a019278c3eb/test_coverage)](https://codeclimate.com/github/hymnis/dsul-python/test_coverage)

The goal of the project is to have a USB connected light, that can be be set to different colors, with adjustable brightness and different modes, which can communicate the users current preference regarding being disturbed.

This implementation used Python 3.x for both daemon/server and client. It should work on most platforms as it uses as few and standard libraries as possible.


## Hardware

The hardware used is an Arduino connected to a Neopixel module. The project was developed using an Arduino Nano, but should work on most models as long as the firmware fit and it has enough RAM for the number of LED's used in the module.

The firmware project is available at [hymnis/dsul-arduino](https://github.com/hymnis/dsul-arduino).


## Installation
The requirements for the daemon and CLI client are split into separate files, so only the needed libraries needs to be installed if only using one component.

- To install the daemon requirements, run: `pip install -r requirements.daemon.txt`
- To install the CLI client requirements, run: `pip install -r requirements.cli.txt`

If you are using a virtual environment, remember to activate it before running `pip install`.


## Configuration

Both daemon and client use the same configuration file, `dsul.cfg`. This is a simple ini style configuration that contains the different colors, modes and brightness limits. It can also be used to define default settings for serial and IPC communication (these can be overridden using the command line arguments).

If daemon and client are run on different machines, make sure the use the same definitions and limits for colors, brightness and modes.


## Daemon
This part handles communication with the hardware (serial connection) and allows clients to send commands (TCP IPC connection).

### Options

    --help                    Show help and usage information
    -h, --host <host>         The hostname/address to expose server on [default: localhost]
    -p, --port <port>         The port number used for the server [default: 5795]
    -c, --comport <comport>   The com port [default: /dev/ttyUSB0]
    -b, --baudrate <baudrate> The baudrate to use with the com port [default: 9600]
    -t, --timeout <timeout>   The connection timeout to use for com port (in seconds) [default: 1]


## CLI client
Used to communicate with the daemon through TCP IPC.

### Options

    --help                         Show help and usage information
    -l, --list                     List acceptable values for color, brightness and mode
    -c, --color <color>            Set color to given value (must be one of the predefined colors)
    -b, --brightness <brightness>  Set brightness to given value
    -m, --mode <mode>              Set mode to given value (must be on of the predefined modes)
    -h, --host <host>              The hostname/address of the server [default: localhost]
    -p, --port <port>              The port number used to connect to the server [default: 5795]


## Development
This is the basic flow for development on the project. Step 1-2 should only have to be run once, while 3-6 is the continuous development cycle.

1. Install python requirements (`pip install -r requirements.development.txt`)
0. Initialize pre-commit (`pre-commit install`)
0. Develop stuff
0. Test
0. Commit changes
0. Push changes

### Requirements
As this repo uses [pre-commit](https://pre-commit.com/) that does linting and formatting (of python code), we don't have to do that manually but the the tools are still added as requirements (in `requirements.development.txt`) so that linting etc. can be done manually or by IDE if so desired. [pre-commit](https://pre-commit.com/) is also one of the requirements and must be installed prior to commit, for it to work.

### Testing
Tests are located in the _tests_ directory. They should be named according to format: `test_<module name>.py`

To run all tests, use the `unittest` module like so: `python -m unittest` or if you only want to test a specific module: `python -m unittest tests.test_<module name>`.

## Acknowledgements

- `ipc` module is based on the work of Dan Krause.  
   Check it out at: [https://gist.github.com/dankrause/9607475](https://gist.github.com/dankrause/9607475)
- `mockserial` module is based on the work of D. Thiebaut.  
  Check it out at: [http://www.science.smith.edu/dftwiki/index.php/PySerial_Simulator](http://www.science.smith.edu/dftwiki/index.php/PySerial_Simulator)
