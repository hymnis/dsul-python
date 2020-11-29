"""DSUL - Disturb State USB Light : Test DSUL IPC."""

import inspect
import logging
import os
import re
import socket
import sys
import threading
import time
import unittest

current_dir = os.path.dirname(
    os.path.abspath(inspect.getfile(inspect.currentframe()))
)
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

import dsul.ipc as ipc  # noqa


def socket_open(socket_path: str) -> bool:
    """Check if socket exists."""
    result_of_check = os.path.exists(socket_path)

    if result_of_check:
        return True

    return False


def port_open(host: str, port: int) -> bool:
    """Check if a port is open on given host."""
    a_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    location = (host, port)
    result_of_check = a_socket.connect_ex(location)
    a_socket.close()

    if result_of_check == 0:
        return True

    return False


class DsulIpcTest(unittest.TestCase):
    """Test class for DSUL IPC."""

    def setUp(self):
        """Prepare for test."""
        logging.disable(logging.CRITICAL)  # disable most logging during test
        self.server_pid = None
        self.socket = "/tmp/dsul-test.sock"
        self.host = "localhost"
        self.port = 5796
        self.message_key = "OK"
        self.message_value = "Loud and clear"

    def process_server_request(self, objects):
        """Process incoming data and return response."""
        print(f"IPCs object : {objects}")
        response = [ipc.Response(f"{self.message_key}, {self.message_value}")]
        return response

    def process_client_response(self, objects):
        """Process client response and return status."""
        print(f"IPCc object : {objects}")

        objects = objects[0].text[0]
        key, value = re.split(r",", objects, 1)
        key = key.strip()
        value = value.strip()

        if key == self.message_key and value == self.message_value:
            return True

        return False

    def test_ipc_socket(self):
        """Test IPC socket server started."""
        server = ipc.Server(
            address=self.socket, callback=self.process_server_request
        )
        ipc_thread = threading.Thread(target=server.run, daemon=False)
        ipc_thread.start()
        time.sleep(1)  # let server start properly

        # Verify the IPC server works in this mode
        is_open = socket_open(self.socket)
        user_input = [
            {
                "class": "Event",
                "args": "test",
                "kwargs": {"key": "socket", "value": "true"},
            }
        ]
        objects = ipc.Message.deserialize(user_input)
        with ipc.Client(self.socket) as client:
            response = client.send(objects)
        is_active = self.process_client_response(response)

        server.shutdown()
        ipc_thread.join()

        self.assertEqual(True, is_open)
        self.assertEqual(True, is_active)

    def test_ipc_tcp(self):
        """Test IPC TCP server started."""
        server = ipc.Server(
            address=(self.host, self.port),
            callback=self.process_server_request,
        )
        ipc_thread = threading.Thread(target=server.run, daemon=False)
        ipc_thread.start()
        time.sleep(1)  # let server start properly

        # Verify the IPC server works in this mode
        is_open = port_open(self.host, self.port)
        user_input = [
            {
                "class": "Event",
                "args": "test",
                "kwargs": {"key": "socket", "value": "true"},
            }
        ]
        objects = ipc.Message.deserialize(user_input)
        with ipc.Client((self.host, self.port)) as client:
            response = client.send(objects)
        is_active = self.process_client_response(response)

        server.shutdown()
        ipc_thread.join()

        self.assertEqual(True, is_open)
        self.assertEqual(True, is_active)

    def tearDown(self):
        """Shut down processes and clean up after test."""
        logging.disable(logging.NOTSET)  # enable logging again


if __name__ == "__main__":
    unittest.main(buffer=True)
