"""IPC module for both server and client."""

#   Copyright 2017 Dan Krause
#   Modified and updated 2020 by hymnis
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
import os
import socket
import socketserver
import struct


class IPCError(Exception):
    """Error class for IPC errors."""


class UnknownMessage(IPCError):
    """Error class for unknown messages."""


class InvalidSerialization(IPCError):
    """Error class for invalid serilization."""


class ConnectionClosed(IPCError):
    """Error class for closed connection."""


class ConnectionRefused(IPCError):
    """Error class for refused connection."""


class SocketRefused(IPCError):
    """Error class for refusal to open socket."""


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Handle each request in a separate thread."""


class ThreadedUnixStreamServer(
    socketserver.ThreadingMixIn, socketserver.UnixStreamServer
):
    """Handle each request in a separate thread."""


def create_request_handler(server=None):
    """Create request handler with given message handler."""

    class ThreadedRequestHandler(socketserver.BaseRequestHandler):
        """Request handler class for threaded servers."""

        def handle(self):
            """Handle received message and send back response."""
            sock = self.request
            response = ""

            while True:
                try:
                    objects = _read_objects(sock)
                    response = server._callback(objects)
                except ConnectionClosed:
                    return
                except ConnectionResetError:
                    sock.close()
                except Exception:
                    sock.close()

                _write_objects(sock, response)

    return ThreadedRequestHandler


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
                    raise UnknownMessage(err) from err
                except TypeError as err:
                    raise InvalidSerialization(err) from err

        return serialized

    def serialize(self):
        """Serialize object."""
        args, kwargs = self._get_args()
        return {"class": type(self).__name__, "args": args, "kwargs": kwargs}

    @staticmethod
    def _get_args():
        """Return an empty tuple of list and dictionary."""
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

        if isinstance(self.addr, str):
            address_family = socket.AF_UNIX
        else:
            address_family = socket.AF_INET

        self.sock = socket.socket(address_family, socket.SOCK_STREAM)

    def connect(self):
        """Connect to the server."""
        try:
            self.sock.connect(self.addr)
        except ConnectionRefusedError as err:
            raise ConnectionRefused from err

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

    def __init__(self, *, address, callback, bind_and_activate=True):
        """Initialize the server."""
        super(Server, self).__init__()
        self._address = address
        self._bind_and_activate = bind_and_activate
        if not callable(callback):
            self._callback = lambda x: []

        self._callback = callback
        self._server = None

    def run(self):
        """Start the IPC server."""
        ipc_handler = create_request_handler(self)

        if isinstance(self._address, str):
            try:
                os.unlink(self._address)
            except OSError:
                if os.path.exists(self._address):
                    raise

            with ThreadedUnixStreamServer(
                server_address=self._address,
                RequestHandlerClass=ipc_handler,
                bind_and_activate=self._bind_and_activate,
            ) as server_instance:
                self._server = server_instance
                self._server.socket.settimeout(0.0)
                self._server.serve_forever()
        else:
            with ThreadedTCPServer(
                server_address=self._address,
                RequestHandlerClass=ipc_handler,
                bind_and_activate=self._bind_and_activate,
            ) as server_instance:
                self._server = server_instance
                self._server.socket.settimeout(0.0)
                self._server.serve_forever()

    def shutdown(self):
        """Stop and shut down the server."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
