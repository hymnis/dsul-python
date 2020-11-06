"""
DSUL - Disturb State USB Light : Mock serial module.

Based on the work of D. Thiebaut.
"""


class Serial:
    """Mock serial class, for testing."""

    def __init__(
        self,
        port="/dev/ttyUSB0",
        baudrate=9600,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=1,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    ):
        """Initialize the the class."""
        self.name = port
        self.port = port
        self.parity = parity
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.stopbits = stopbits
        self.timeout = timeout
        self.xonxoff = xonxoff
        self.rtscts = rtscts
        self.dsrdtr = dsrdtr
        self.is_open = False
        self._out_data = ""
        self._in_data = ""

    def __str__(self):
        """Return a string representation of the class."""
        return (
            f"Serial<id=0xa81c10, open={str(self.is_open)}>("
            f"port='{self.port}', baudrate={self.baudrate}, "
            f"bytesize={self.bytesize}, parity='{self.parity}', "
            f"stopbits={self.stopbits}, timeout={self.timeout}, "
            f"xonxoff={self.xonxoff}, rtscts={self.rtscts}, "
            f"dsrdtr={self.dsrdtr})"
        )

    def is_open(self):
        """Return status for port."""
        return self.is_open

    def open(self):
        """Open the port."""
        self.is_open = True

    def close(self):
        """Close the port."""
        self.is_open = False

    def write(self, string):
        """Write characters."""
        print(f"Serial out: {string}")
        self._out_data += string

    def read(self, n=1):
        """
        Read n characters and return.

        The characters are read from the string _data.
        """
        s = self._data[0:n]
        self._in_data = self._in_data[n:]
        # print(f"Serial in: self._data = {self.data}")
        return s

    def readline(self):
        r"""Read characters until \n is found."""
        returnIndex = self._in_data.index("\n")
        if returnIndex != -1:
            s = self._in_data[0 : returnIndex + 1]
            self._in_data = self._in_data[returnIndex + 1 :]
            return s
        else:
            return ""

    def set_in_data(self, in_data):
        """Set the _in_data variable data (data read from "serial port")."""
        self._in_data = in_data

    def get_out_data(self):
        """Return the _out_data variable (data sent to "serial port")."""
        return self._out_data
