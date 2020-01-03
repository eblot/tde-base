import os


def serial_device(devname, baudrate, parity='', timeout=0, logfile=None):
    """Open the serial communication port"""
    if not devname:
        if os.name == 'nt':
            devname = 'COM1'
        elif os.name == 'posix':
            (system, _, _, _, _) = os.uname()
            if system.lower() == 'darwin':
                from glob import glob
                try:
                    devname = glob('/dev/tty.usbserial*')[0]
                except IndexError:
                    pass
            else:
                devname = '/dev/ttyS0'
    if not devname:
        raise ValueError('Serial port unknown')
    try:
        from serial.serialutil import SerialException
        from serial import PARITY_NONE
    except ImportError:
        raise ImportError("Python serial module not installed")
    try:
        # the following import enables serial protocol extensions
        from serial import serial_for_url, VERSION as serialver
        version = tuple([int(x) for x in serialver.split('.')])
        if version < (2, 6):
            raise ValueError
    except (ValueError, IndexError, ImportError):
        raise ImportError("pyserial 2.6+ is required")
    logger = None
    if devname.startswith('ftdi://'):
        # the following import enables serial protocol extensions
        from pyftdi import serialext
        serialext.touch()
    try:
        port = serial_for_url(devname,
                              baudrate=baudrate,
                              parity=parity or PARITY_NONE,
                              timeout=timeout)
        if logger:
            logger.spy(port)
        if not port.isOpen():
            port.open()
        if not port.isOpen():
            raise IOError('Cannot open port "%s"' % devname)
        return port
    except SerialException as e:
        raise IOError(str(e))
