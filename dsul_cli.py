#!/usr/bin/env python
"""DSUL - Disturb State USB Light : CLI application."""

import sys
import getopt
import configparser
import logging
import serial
import ipc


class DsulCli:
    """DSUL CLI application class."""

    debug = None
    command = {}
    retries = 0
    colors = {}
    modes = []
    ipc = {}

    def __init__(self, argv):
        """Initialize the class."""
        self.get_settings()
        self.read_argument(argv)

    def get_settings(self):
        """Get settings from config file."""
        config = configparser.RawConfigParser()
        config.read('dsul.cfg')

        self.debug = config.getint('DSUL', 'debug', fallback=False)
        if self.debug:
            logging.basicConfig(level=logging.DEBUG)

        self.ipc['host'] = config.get('IPC', 'host', fallback='localhost')
        self.ipc['port'] = config.getint('IPC', 'port', fallback=5795)

        self.modes = config.get('Modes', 'types').split(',')

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

    def read_argument(self, argv):
        """Parse command line arguments."""
        ready = False
        help_string = 'dsul_cli.py --help -l -c <color> -m <mode> ' \
            '-b <brightness> -h <host> -p <port>'

        try:
            opts, args = getopt.getopt(  # pylint: disable=W0612
                argv,
                'lh:p:c:m:b:',
                [
                    'help', 'list', 'host', 'port',
                    'color=', 'mode=', 'brightness='])
        except getopt.GetoptError:
            print(help_string)
            sys.exit(2)

        for opt, arg in opts:
            if opt == '--help':
                print(help_string)
                sys.exit()
            elif opt in ('-l', '--list'):
                self.list_information()
                sys.exit()
            elif opt in ('-c', '--color'):
                # TODO: validate arg before using the value
                self.command['key'] = 'color'
                self.command['value'] = arg
                self.send_command()
                ready = True
            elif opt in ('-b', '--brightness'):
                # TODO: validate arg before using the value
                self.command['key'] = 'brightness'
                self.command['value'] = arg
                self.send_command()
                ready = True
            elif opt in ('-m', '--mode'):
                # TODO: validate arg before using the value
                self.command['key'] = 'mode'
                self.command['value'] = arg
                self.send_command()
                ready = True

        if not ready:
            logging.error('Missing commands and/or arguments')
            sys.exit(1)

    def send_command(self):
        """Send command to the daemon."""
        try:
            # Send command to daemon
            server_address = (self.ipc['host'], self.ipc['port'])
            user_input = [
                {'class': 'Event',
                 'args': 'command',
                 'kwargs': {
                     'key': self.command['key'],
                     'value': self.command['value']}}]
            objects = ipc.Message.deserialize(user_input)
            logging.debug(f'Sending objects: {objects}')
            with ipc.Client(server_address) as client:
                response = client.send(objects)
            logging.debug(f'Received objects: {response}')
        except KeyError:
            logging.error('Key error')
            sys.exit(1)
        except ipc.UnknownMessage:
            logging.error('Unknown message')
            sys.exit(1)
        except ipc.ConnectionRefused:
            logging.error('Connection was refused')
            sys.exit(2)

    def list_information(self):
        """Print out all modes and colors."""
        print('[modes]')
        for mode in self.modes:
            print('- {}'.format(mode))

        print('\n[colors]')
        for color in self.colors:
            print('- {}'.format(color))


if __name__ == "__main__":
    APP = DsulCli(sys.argv[1:])
