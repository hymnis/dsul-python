# DSUL - Disturb State USB Light

The goal of the project is to have a USB connected light, that can be be set to different colors, with adjustable brightness and different modes, which can communicate the users current preference regarding being disturbed.

This implementation used Python 3.x for both daemon/server and client. It should work on most platforms as it uses as few and standard libraries as possible.


## Hardware

The hardware used is an Arduino connected to a Neopixel module. The project was developed using an Arduino Nano, but should work on most models as long as the firmware fit and it has enough RAM for the number of LED's used in the module.

The firmware project is available at [hymnis/dsul-arduino](https://github.com/hymnis/dsul-arduino).


## Configuration

Both daemon and client use the same configuration file, `dsul.cfg`. This is a simple ini style configuration that contains the different colors, modes and brightness limits. It can also be used to define default settings for serial and IPC communication (these can be overridden using the command line arguments).

If daemon and client are run on different machines, make sure the use the same definitions and limits for colors, brightness and modes.


## Daemon
This part handles communication with the hardware (serial connection) and allows clients to send commands (TCP IPC connection).

### Options

    --help                    Show help and usage information
    -h, --host=<host>         The hostname/address to expose server on [default: localhost]
    -p, --port=<port>         The port number used for the server [default: 5795]
    -c, --comport=<comport>   The com port [default: /dev/ttyUSB0]
    -b, --baudrate=<baudrate> The baudrate to use with the com port [default: 9600]
    -t, --timeout=<timeout>   The connection timeout to use for com port (in seconds) [default: 1]


## CLI client
Used to communicate with the daemon through TCP IPC.

### Options

    --help                         Show help and usage information
    -l, --list                     List acceptable values for color, brightness and mode
    -c, --color=<color>            Set color to given value (must be one of the predefined colors)
    -b, --brightness=<brightness>  Set brightness to given value
    -m, --mode=<mode>              Set mode to given value (must be on of the predefined modes)
    -h, --host=<host>              The hostname/address of the server [default: localhost]
    -p, --port=<port>              The port number used to connect to the server [default: 5795]
