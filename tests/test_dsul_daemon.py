"""DSUL - Disturb State USB Light : Test DSUL Daemon."""

import inspect
import logging
import os
import socket
import sys
import threading
import time
import unittest
from unittest.mock import patch

from . import mockserial

orig_import = __import__
serial_mock = mockserial


def import_serial(name, *args):
    """Mock for 'serial' module, used for testing."""
    if name == "serial":
        return serial_mock
    return orig_import(name, *args)


current_dir = os.path.dirname(
    os.path.abspath(inspect.getfile(inspect.currentframe()))
)
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

with patch("builtins.__import__", side_effect=import_serial):
    import dsul.daemon as dd


def port_open(host: str, port: int) -> bool:
    """Check if a port is open on given host."""
    a_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    location = (host, port)
    result_of_check = a_socket.connect_ex(location)
    a_socket.close()

    if result_of_check == 0:
        return True
    else:
        return False


class DsulDaemonTest(unittest.TestCase):
    """Test class for DSUL Daemon."""

    def setUp(self):
        """Initialize the DSUL Daemon before test."""
        logging.disable(logging.CRITICAL)  # disable most logging during test
        self.ipc_host = "localhost"
        self.ipc_port = 5796
        self.dd = dd.DsulDaemon([])  # use default setttings

    def test_ipc_tcp_started(self):
        """Test IPC server started."""
        self.dd.settings["ipc"]["host"] = self.ipc_host
        self.dd.settings["ipc"]["port"] = self.ipc_port
        self.dd.ipc_active = True

        # Start IPC server in a thread
        ipc_stop = threading.Event()
        ipc_thread = threading.Thread(
            target=self.dd.ipc_process, daemon=True, args=(ipc_stop,)
        )
        ipc_thread.start()
        time.sleep(2)  # wait for server to start properly

        # Verify the IPC server starts
        is_open = port_open(self.ipc_host, self.ipc_port)

        ipc_stop.set()
        ipc_thread.join()

        self.assertEqual(True, self.dd.ipc_active)
        self.assertEqual(True, is_open)

    def test_ipc_stopped(self):
        """Test IPC server stopped."""
        # Verify that IPC server doesn't run unless started
        self.dd.ipc_active = False
        is_open = port_open(self.ipc_host, self.ipc_port)
        self.assertEqual(False, is_open)

    def test_serial_init(self):
        """Test serial connection initializion."""
        # Verify that serial port is open and serial marked as active
        self.dd.init_serial()
        self.assertEqual(True, self.dd.serial_active)
        self.assertEqual(True, self.dd.ser.is_open)

    def test_serial_deinit(self):
        """Test serial connection de-initializion."""
        # Verify that serial port is closed
        self.dd.deinit_serial()
        self.assertEqual(False, self.dd.ser.is_open)

    def test_serial_read(self):
        """Test serial read."""
        # Verify that reading data from serial port works
        self.dd.ser.set_in_data(b"-?#")  # ping from device
        result = self.dd.read_serial()
        self.assertEqual("-?#", result)

    def test_serial_write(self):
        """Test serial write."""
        # Verify that writing data to serial port works
        self.dd.write_serial("-?#")  # send ping to device
        result = self.dd.ser.get_out_data()
        self.assertEqual(b"-?#", result)

    def tearDown(self):
        """Shut down processes and clean up after test."""
        logging.disable(logging.NOTSET)  # enable logging again


if __name__ == "__main__":
    unittest.main(buffer=True)
