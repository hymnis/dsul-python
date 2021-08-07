# Run DSUL daemon with systemd and udev

Using systemd and udev together let's us automatically start the daemon when the
usb device is plugged in.

1. Edit `99-dsul.rules` so that the vendor and product id's match the device you
are using.
0. Place the file in `/etc/udev/rules.d/` and run `udevadm control --reload-rules`.
0. Edit `dsul.service` so it uses the appropriate ExecStart format for your setup
(with or without virtual environment).
0. Place the file in `/etc/systemd/system/dsul.service` and run `systemctl daemon-reload`.


## How it works

When the usb device is plugged in, it's detected by udev and our rule is matched
against the id's and the tty device created gets a symlink (`/dev/dsul`) and we
also tag it with `systemd` to make sure systemd knows to handle it. We also tell
systemd which service is wanted by our newly created device. Once the device is
available to systemd the service is started. If the usb device is removed, udev
will remove all devices and once the systemd device no longer exists, systemd
then stops the service.
