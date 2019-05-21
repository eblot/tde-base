PyTerm
======

``pyterm.py`` is a simple serial terminal client, with special filtering
capabilities to enhance the rendering of log traces from remote target.

Usage
-----

::

  usage: pyterm.py [-h] [-f] [-p DEVICE] [-b BAUDRATE] [-w] [-P PDELAY] [-e]
                   [-r] [-l] [-g] [-c] [-s] [-v] [-d]

  Simple Python serial terminal

  optional arguments:
    -h, --help            show this help message and exit
    -f, --fullmode        use full terminal mode, exit with [Ctrl]+B
    -p DEVICE, --device DEVICE
                          serial port device name (default: first UART port)
    -b BAUDRATE, --baudrate BAUDRATE
                          serial port baudrate (default: 115200)
    -w, --hwflow          hardware flow control
    -P PDELAY, --pdelay PDELAY
                          pulse DTR at start-up (delay in seconds)
    -e, --localecho       local echo mode (print all typed chars)
    -r, --crlf            prefix LF with CR char, use twice to replace all LF
                          with CR chars
    -l, --loopback        loopback mode (send back all received chars)
    -g, --filterlog       Enable filter log feature, flip-flop with [Ctrl]+G
    -c, --color           Show available colors and exit
    -s, --silent          silent mode
    -v, --verbose         increase verbosity
    -d, --debug           enable debug mode


FTDI support
------------

``pyterm.py`` can also be used to list all FTDI devices connected to the host,
and report the URLs to use to access those devices.

Use the following syntax:

.. code-block:: shell

  host/bin/pyterm.py -p ftdi:///?

