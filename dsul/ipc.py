"""IPC module for both server and client."""

#   Copyright 2017 Dan Krause
#   Modified and updated by hymnis, 2020
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import json
import socket
import socketserver
import struct


class IPCError(Exception):
    """Error class for IPC errors."""

    pass


class UnknownMessage(IPCError):
    """Error class for unknown messages."""

    pass


class InvalidSerialization(IPCError):
    """Error class for invalid serilization."""

    pass


class ConnectionClosed(IPCError):
    """Error class for closed connection."""

    pass


class ConnectionRefused(IPCError):
    """Error class for refused connection."""

    pass


class SocketRefused(IPCError):
    """Error class for refusal to open socket."""

    pass


def _read_objects(sock):
    header = sock.recv(4)

    if not header:
        raise ConnectionClosed()
    size = struct.unpack("!i", header)[0]
    data = sock.recv(size - 4)

    if not data:
        raise ConnectionClosed()

    return Message.deserialize(json.loads(data))


def _write_objects(sock, objects):
    data = json.dumps([o.serialize() for o in objects])
    sock.sendall(struct.pack("!i", len(data) + 4))
    sock.sendall(data.encode())


def _recursive_subclasses(cls):
    classmap = {}

    for subcls in cls.__subclasses__():
        classmap[subcls.__name__] = subcls
        classmap.update(_recursive_subclasses(subcls))

    return classmap


class Message:
    """IPC message class."""

    @classmethod
    def deserialize(cls, objects):
        """Deserialize given object."""
        classmap = _recursive_subclasses(cls)
        serialized = []

        for obj in objects:
            if isinstance(obj, Message):
                serialized.append(obj)
            else:
                try:
                    serialized.append(
                        classmap[obj["class"]](obj["args"], **obj["kwargs"])
                    )
                except KeyError as err:
                    raise UnknownMessage(err)
                except TypeError as err:
                    raise InvalidSerialization(err)

        return serialized

    def serialize(self):
        """Serialize object."""
        args, kwargs = self._get_args()
        return {"class": type(self).__name__, "args": args, "kwargs": kwargs}

    @staticmethod
    def _get_args():
        """Retrurn and empty tuple of list and dictionary."""
        return [], {}

    def __repr__(self):
        """Return name and args."""
        rep_r = self.serialize()
        args = ", ".join([repr(arg) for arg in rep_r["args"]])
        kwargs = "".join(
            [", {}={}".format(k, repr(v)) for k, v in rep_r["kwargs"].items()]
        )
        name = rep_r["class"]

        return "{}({}{})".format(name, args, kwargs)


class Response(Message):
    """Class for IPC response messages."""

    def __init__(self, text):
        """Set text from input."""
        self.text = text

    def _get_args(self):
        return [self.text], {}


class Event(Message):
    """Class for IPC event messages."""

    def __init__(self, event_type, **properties):
        """Set type and properties."""
        self.type = event_type
        self.properties = properties

    def _get_args(self):
        return [self.type], self.properties


class Client:
    """IPC client class."""

    def __init__(self, address):
        """Initilize the client class."""
        self.addr = address
        address_family = socket.AF_INET
        self.sock = socket.socket(address_family, socket.SOCK_STREAM)

    def connect(self):
        """Connect to the server."""
        try:
            self.sock.connect(self.addr)
        except ConnectionRefusedError:
            raise ConnectionRefused

    def close(self):
        """Close the connection to the server."""
        self.sock.close()

    def __enter__(self):
        """Connect and return the object."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Disconnect from server."""
        self.close()

    def send(self, objects):
        """Send given object."""
        _write_objects(self.sock, objects)
        return _read_objects(self.sock)


class Server:
    """IPC server class."""

    def __init__(self, address, callback, bind_and_activate=True):
        """Initialize the server."""
        if not callable(callback):

            def callback(x):
                return []  # pylint: disable=E0102,C0111,C0321

        class IPCHandler(socketserver.BaseRequestHandler):
            """Handler for IPC connections."""

            def handle(self):
                while True:
                    try:
                        results = _read_objects(self.request)
                    except ConnectionClosed:
                        return
                    _write_objects(self.request, callback(results))

        with socketserver.TCPServer(
            server_address=address,
            RequestHandlerClass=IPCHandler,
            bind_and_activate=bind_and_activate,
        ) as server_instance:
            server_instance.serve_forever()
