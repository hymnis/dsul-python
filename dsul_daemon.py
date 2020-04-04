#!/usr/bin/env python
"""DSUL - Disturb State USB Light : Daemon application."""

import sys
import os
import getopt
import configparser
import logging
import time
import threading
import serial
import ipc


class DsulDaemon:
    """DSUL Daemon application class."""

    debug = None
    ser = None
    serial_active = None
    ipc_active = None
    read_command = True
    read_data = False
    send_commands = []
    current_command = ''
    retries = 0
    colors = {}
    modes = []
    serial = {}
    ipc = {}

    def __init__(self, argv):
        """Initialize the class."""
        self.get_settings()
        self.read_arguments(argv)

        self.ser = serial.Serial()
        self.init_serial()
        self.ipc_active = True

    def get_settings(self):
        """Get settings from config file."""
        config = configparser.RawConfigParser()
        config.read('dsul.cfg')

        self.debug = config.getint('DSUL', 'debug', fallback=False)
        if self.debug:
            logging.basicConfig(level=logging.DEBUG)

        self.ipc['host'] = config.get('IPC', 'host', fallback='localhost')
        self.ipc['port'] = config.getint('IPC', 'port', fallback=5795)

        self.serial['port'] = config.get(
            'Serial', 'port', fallback='/dev/ttyUSB0')
        self.serial['baudrate'] = config.getint(
            'Serial', 'baudrate', fallback=9600)
        self.serial['timeout'] = config.getint(
            'Serial', 'timeout', fallback=1)

        self.modes = config.get('Modes', 'types').split(',')

        self.brightness_min = config.getint('Brightness', 'min', fallback=0)
        self.brightness_max = config.getint('Brightness', 'max', fallback=150)

        self.colors['red'] = config.get('Colors', 'red').split(",")
        self.colors['green'] = config.get('Colors', 'green').split(",")
        self.colors['blue'] = config.get('Colors', 'blue').split(",")
        self.colors['cyan'] = config.get('Colors', 'cyan').split(",")
        self.colors['white'] = config.get('Colors', 'white').split(",")
        self.colors['warmwhite'] = config.get('Colors', 'warmwhite').split(",")
        self.colors['purple'] = config.get('Colors', 'purple').split(",")
        self.colors['magenta'] = config.get('Colors', 'magenta').split(",")
        self.colors['yellow'] = config.get('Colors', 'yellow').split(",")
        self.colors['orange'] = config.get('Colors', 'orange').split(",")
        self.colors['black'] = config.get('Colors', 'black').split(",")

    def read_arguments(self, argv):
        """Parse command line arguments."""
        help_string = 'dsul_daemon.py --help -h <host> -p <port>'

        # read (overriding) settings from command arguments
        try:
            opts, args = getopt.getopt(  # pylint: disable=W0612
                argv, 'p:h:c:b:', [
                    'help', 'port=', 'host=', 'comport=', 'baudrate='])
        except getopt.GetoptError:
            print(help_string)
            sys.exit(2)

        for opt, arg in opts:
            if opt == '--help':
                print(help_string)
                sys.exit()
            elif opt in ('-h', '--host'):
                self.ipc['host'] = arg
            elif opt in ('-p', '--port'):
                self.ipc['port'] = int(arg)
            elif opt in ('-c', '--comport'):
                self.serial['port'] = arg
            elif opt in ('-b', '--baudrate'):
                self.serial['baudrate'] = int(arg)

    def run(self):
        """Run the main loop of the application."""
        try:
            serial_thread = threading.Thread(
                target=self.serial_process, daemon=True)
            serial_thread.start()

            ipc_thread = threading.Thread(target=self.ipc_process, daemon=True)
            ipc_thread.start()

            while ipc_thread.is_alive() or serial_thread.is_alive():
                if not serial_thread.is_alive():
                    # Try to reconnect the serial connection
                    logging.info('Trying to re-establish serial connection')
                    time.sleep(5)
                    self.ser.close()
                    self.init_serial()
                    serial_thread = threading.Thread(
                        target=self.serial_process, daemon=True)
                    serial_thread.start()
        except (KeyboardInterrupt, SystemExit):
            self.serial_active = False
            self.ipc_active = False

            if self.ser is not None and self.ser.is_open:
                self.ser.close()

    def serial_process(self):
        """Handle serial connection."""
        while self.serial_active:
            # Make sure port is actually still there before using it
            if not os.path.exists(self.serial['port']):
                self.ser.close()
                self.serial_active = False
                return

            in_data = self.read_serial()
            if in_data is not None:
                self.handle_input(in_data)

            self.process_commands()

    def ipc_process(self):
        """Handle IPC communication."""
        server_address = (self.ipc['host'], self.ipc['port'])
        logging.info(
            f"Starting IPC server ({self.ipc['host']}:{self.ipc['port']})")

        while self.ipc_active:
            ipc.Server(
                address=server_address, callback=self.process_server_request)

    def init_serial(self):
        """Initilize serial communication."""
        try:
            logging.info('Opening serial port')
            self.ser.port = self.serial['port']
            self.ser.baudrate = self.serial['baudrate']
            self.ser.timeout = self.serial['timeout']
            self.ser.open()
            self.serial_active = True
        except serial.serialutil.SerialException:
            logging.error('Failed to open serial port')
            self.serial_active = False

    def read_serial(self):
        """Read data from serial connection."""
        try:
            if self.read_command:
                read_length = 3
            elif self.read_data:
                read_length = 10
            incoming = self.ser.read(read_length)
            if incoming != b'':
                logging.debug(f'Received: {incoming}')
                incoming = incoming.decode()
            else:
                incoming = None
        except serial.serialutil.SerialException:
            incoming = None

        return incoming

    def write_serial(self, message):
        """Write data to the serial connection."""
        try:
            self.ser.write(message.encode())
            return True
        except serial.serialutil.SerialException:
            return False

    def handle_input(self, input_data):
        """Handle commands and input data."""
        if self.read_command:
            if input_data == '-!#':  # resend/request data
                pass
            elif input_data == '-?#':  # ping
                self.write_serial('+!#')  # ok/pong
            elif input_data == '+!#':  # ok
                pass
            elif input_data == '+?#':  # unknown/error
                pass
        elif self.read_data:
            logging.debug(f'serial data: {input_data}')

    def queue_command(self, key, value):
        """Add command to the queue."""
        if key == 'color':
            self.send_color_command(value)
        elif key == 'brightness':
            self.send_brightness_command(value)
        elif key == 'mode':
            self.send_mode_command(value)

    def send_color_command(self, value):
        """Send command to set color."""
        if value in self.colors:
            logging.info(f'Setting color: "{value}"')
            self.send_commands.append(
                '+l{:03d}{:03d}{:03d}#'.format(
                    int(self.colors[value][0]),
                    int(self.colors[value][1]),
                    int(self.colors[value][2])))
        else:
            logging.warning(f'Invalid argument: "{value}"')

    def send_brightness_command(self, value):
        """Send command to set brightness."""
        if (int(value) >= self.brightness_min and
                int(value) <= self.brightness_max):
            logging.info(f'Setting brightness: "{value}"')
            self.send_commands.append('+b{:03d}#'.format(int(value)))
        else:
            logging.warning(f'Invalid argument: "{value}"')

    def send_mode_command(self, value):
        """Send command to set the mode."""
        if value in self.modes:
            logging.info(f'Setting mode: "{value}"')
            self.send_commands.append('+m{}#'.format(value))
        else:
            logging.warning(f'Invalid argument: "{value}"')

    def process_commands(self):
        """Process the command queue."""
        if self.current_command != '':
            logging.debug(f'Command: {self.current_command}')
            if not self.write_serial(self.current_command):
                self.retries += 1
            else:
                self.current_command = ''

            if self.retries >= 5:
                self.retries = 0
                self.current_command = ''
                logging.error('Sending command failed (5 retries)')

        # add command(s) to queue
        if self.send_commands != [] and self.current_command == '':
            self.current_command = self.send_commands.pop()

    def process_server_request(self, objects):
        """Handle request sent to the IPC server."""
        logging.debug(f'Received objects: {objects}')

        if self.serial_active:
            for message_object in objects:
                if message_object.type[0] == 'command':
                    message = f"{message_object.properties['key']}=" \
                        f"{message_object.properties['value']}"
                    self.queue_command(
                        message_object.properties['key'],
                        message_object.properties['value'])
            # TODO: get return data from arduino and adjust response message
            response = [ipc.Response(f'OK, {message}')]
        else:
            response = [ipc.Response('NOK, no serial connection')]

        logging.debug(f'Sent response: {response}')

        return response


if __name__ == '__main__':
    APP = DsulDaemon(sys.argv[1:])
    APP.run()
