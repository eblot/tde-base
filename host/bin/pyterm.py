#!/usr/bin/env python3

"""Simple Python serial terminal
"""

# Copyright (c) 2010-2018, Emmanuel Blot <emmanuel.blot@free.fr>
# Copyright (c) 2016, Emmanuel Bouaziz <ebouaziz@free.fr>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the Neotion nor the names of its contributors may
#       be used to endorse or promote products derived from this software
#       without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL NEOTION BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA,
# OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from argparse import ArgumentParser, FileType
from array import array
from atexit import register
from collections import deque
from io import TextIOBase
from logging import Formatter, DEBUG, ERROR, FATAL
from logging.handlers import SysLogHandler, WatchedFileHandler, SYSLOG_UDP_PORT
from os import devnull, fstat, isatty, linesep, name as osname, stat, uname
from os.path import abspath
from socket import gethostbyname
from sys import exit, modules, platform, stderr, stdin, stdout, __stdout__
from time import sleep
from threading import Event, Thread
from traceback import format_exc
from _thread import interrupt_main
mswin = platform == 'win32'
if not mswin:
    from termios import TCSANOW, tcgetattr, tcsetattr
import local
from tde.filterlog import get_term_formatter
from tde.misc import get_time_logger, to_int
from tde.term import getkey, is_term


# pylint: disable-msg=broad-except
# pylint: disable-msg=too-many-instance-attributes,too-many-arguments
# pylint: disable-msg=too-few-public-methods,too-many-branches
# pylint: disable-msg=too-many-nested-blocks


class MiniTerm:
    """A mini serial terminal to demonstrate pyserial extensions"""

    DEFAULT_BAUDRATE = 115200

    def __init__(self, device, baudrate=None, parity=None, rtscts=False,
                 logfilter=False, logfile=None, filelog=None, syslog=None,
                 debug=False):
        self._termstates = []
        self._out = stdout
        if not mswin and self._out.isatty():
            fds = [fd.fileno() for fd in (stdin, stdout, stderr)]
            self._termstates = [(fd, tcgetattr(fd) if isatty(fd) else None)
                                for fd in fds]
        self._device = device
        self._baudrate = baudrate or self.DEFAULT_BAUDRATE
        self._resume = False
        self._silent = False
        self._rxq = deque()
        self._rxe = Event()
        self._debug = debug
        self._log = self._get_logger(filelog, syslog)
        self._logfile = (None, None)
        self._logfilter = logfilter
        self._filterbuf = bytearray()
        self._port = self._open_port(self._device, self._baudrate, parity,
                                     rtscts, debug)
        if logfile:
            self._logfile_init(logfile)
        register(self._cleanup)

    def run(self, fullmode=False, loopback=False, silent=False,
            localecho=False, autocr=False):
        """Switch to a pure serial terminal application"""

        # wait forever, although Windows is stupid and does not signal Ctrl+C,
        # so wait use a 1/2-second timeout that gives some time to check for a
        # Ctrl+C break then polls again...
        print('Entering minicom mode')
        self._out.flush()
        self._set_silent(silent)
        self._port.timeout = 0.5
        self._resume = True
        # start the reader (target to host direction) within a dedicated thread
        args = [loopback]
        if self._device.startswith('ftdi://'):
            # with pyftdi/pyusb/libusb stack, there is no kernel buffering
            # which means that a UART source with data burst may overflow the
            # FTDI HW buffer while the SW stack is dealing with formatting
            # and console output. Use an intermediate thread to pop out data
            # out from the HW as soon as it is made available, and use a deque
            # to serve the actual reader thread
            args.append(self._get_from_source)
            sourcer = Thread(target=self._sourcer)
            sourcer.setDaemon(1)
            sourcer.start()
        else:
            # regular kernel buffered device
            args.append(self._get_from_port)
        reader = Thread(target=self._reader, args=tuple(args))
        reader.setDaemon(1)
        reader.start()
        # start the writer (host to target direction)
        self._writer(fullmode, silent, localecho, autocr)

    def pulse_dtr(self, delay):
        """Generate a pulse on DTR, which may be associated w/ HW reset."""
        if self._port:
            self._port.dtr = True
            sleep(delay)
            self._port.dtr = False

    def _sourcer(self):
        try:
            while self._resume:
                data = self._port.read(4096)
                if not data:
                    continue
                self._rxq.append(data)
                self._rxe.set()
        except Exception as ex:
            self._resume = False
            print(str(ex), file=stderr)
            interrupt_main()

    def _get_from_source(self):
        while not self._rxq and self._resume:
            if self._rxe.wait(0.1):
                self._rxe.clear()
                break
        if not self._rxq:
            return array('B')
        return self._rxq.popleft()

    def _get_from_port(self):
        try:
            return self._port.read(4096)
        except OSError as ex:
            self._resume = False
            print(str(ex), file=stderr)
            interrupt_main()
        except Exception as ex:
            print(str(ex), file=stderr)
            return array('B')

    def _reader(self, loopback, getfunc):
        """Loop forever, processing received serial data in terminal mode"""
        if self._logfilter:
            self._logfilter.start()
        try:
            # Try to read as many bytes as possible at once, and use a short
            # timeout to avoid blocking for more data
            self._port.timeout = 0.050
            while self._resume:
                data = getfunc()
                if data:
                    if self._logfile[0]:
                        self._logfile_reopen_if_needed()
                        self._logfile[0].write(data)
                        if b'\n' in data:
                            self._logfile[0].flush()
                    if self._logfilter:
                        start = 0
                        while True:
                            pos = data[start:].find(b'\n')
                            if pos != -1:
                                pos += start
                                self._filterbuf += data[start:pos]
                                try:
                                    self._logfilter.inject(self._filterbuf,
                                                           self._log)
                                except AttributeError:
                                    # Special case: on abort, _logfilter is
                                    # reset; stop injection in this case
                                    if self._logfilter:
                                        raise
                                    break
                                except Exception as ex:
                                    print('[INTERNAL] Filtering error with '
                                          'string: %s' % ex, file=stderr)
                                    print('  ', self._filterbuf.decode(
                                        'utf8', errors='ignore'), file=stderr)
                                    if self._debug:
                                        print(format_exc(), file=stderr)
                                self._filterbuf = bytearray()
                                start = pos+1
                            else:
                                self._filterbuf += data[start:]
                                break
                        continue
                    logstr = data.decode('utf8', errors='replace')
                    self._out.write(logstr)
                    self._out.flush()
                    if self._log:
                        self._log.info(logstr.rstrip())
                if loopback:
                    self._port.write(data)
        except KeyboardInterrupt:
            return
        except Exception as exc:
            print("Exception: %s" % exc)
            if self._debug:
                print(format_exc(chain=False), file=stderr)
            interrupt_main()

    def _writer(self, fullmode, silent, localecho, crlf=0):
        """Loop and copy console->serial until EOF character is found"""
        while self._resume:
            try:
                inc = getkey(fullmode)
                if not inc:
                    sleep(0.1)
                    continue
                if mswin:
                    if ord(inc) == 0x3:
                        raise KeyboardInterrupt()
                if fullmode and ord(inc) == 0x2:  # Ctrl+B
                    self._cleanup()
                    return
                if silent:
                    if ord(inc) == 0x6:  # Ctrl+F
                        self._set_silent(True)
                        print('Silent\n')
                        continue
                    if ord(inc) == 0x7:  # Ctrl+G
                        self._set_silent(False)
                        print('Reg\n')
                        continue
                else:
                    if localecho:
                        self._out.write(inc.decode('utf8', errors='replace'))
                        self._out.flush()
                    if crlf:
                        if inc == b'\n':
                            self._port.write(b'\r')
                            if crlf > 1:
                                continue
                    self._port.write(inc)
            except KeyboardInterrupt:
                if fullmode:
                    continue
                print('%sAborting...' % linesep)
                self._cleanup()
                return

    def _cleanup(self):
        """Cleanup resource before exiting"""
        try:
            self._resume = False
            if self._logfilter:
                self._logfilter.stop()
            if self._port:
                # wait till the other thread completes
                sleep(0.5)
                try:
                    rem = self._port.inWaiting()
                except IOError:
                    # maybe a bug in underlying wrapper...
                    rem = 0
                # consumes all the received bytes
                for _ in range(rem):
                    self._port.read()
                self._port.close()
                self._port = None
                print('Bye.')
            for tfd, att in self._termstates:
                if att is not None:
                    tcsetattr(tfd, TCSANOW, att)
        except Exception as ex:
            print(str(ex), file=stderr)

    def _set_silent(self, enable):
        if bool(self._silent) == bool(enable):
            return
        if enable:
            null = open(devnull, 'w')
            self._out = null
        elif self._out != __stdout__:
            self._out.close()
            self._out = __stdout__
        if self._logfilter:
            self._logfilter.set_output(self._out)

    def _get_logger(self, filelog, syslog):
        logger = get_time_logger('tde.pyterm')
        loglevel = FATAL
        if filelog and filelog[0]:
            logfile, formatter, level = filelog
            handler = WatchedFileHandler(logfile)
            handler.setFormatter(formatter)
            handler.setLevel(level)
            logger.addHandler(handler)
            loglevel = min(loglevel, level)
        if syslog and syslog[0]:
            sysdesc, level = syslog
            handler, formatter = self._create_syslog(sysdesc)
            # not sure why this character is needed as a start of message
            handler.ident = ':'
            handler.setFormatter(formatter)
            handler.setLevel(level)
            logger.addHandler(handler)
            loglevel = min(loglevel, level)
        logger.setLevel(loglevel)
        return logger

    @staticmethod
    def _create_syslog(syslog):
        logargs = syslog.split(':')
        try:
            facility = getattr(SysLogHandler, 'LOG_%s' % logargs[0].upper())
        except AttributeError:
            raise RuntimeError('Invalid facility: %s' % logargs[0])
        host = logargs[1] if len(logargs) > 1 else 'localhost'
        try:
            if len(logargs) > 2 and logargs[2]:
                port = int(logargs[2])
            else:
                port = SYSLOG_UDP_PORT
        except (ValueError, TypeError):
            raise RuntimeError('Invalid syslog port')
        try:
            addr = gethostbyname(host)
        except OSError:
            raise RuntimeError('Invalid syslog host')
        if len(logargs) > 3 and logargs[3]:
            remotefmt = logargs[3].strip("'")
        else:
            remotefmt = r'%(message)s'

        return (SysLogHandler(address=(addr, port), facility=facility),
                Formatter(remotefmt))

    @staticmethod
    def _open_port(device, baudrate, parity, rtscts, debug=False):
        """Open the serial communication port"""
        try:
            from serial.serialutil import SerialException
            from serial import PARITY_NONE
        except ImportError:
            raise ImportError("Python serial module not installed")
        try:
            from serial import serial_for_url, VERSION as serialver
            version = tuple([int(x) for x in serialver.split('.')])
            if version < (2, 6):
                raise ValueError
        except (ValueError, IndexError, ImportError):
            raise ImportError("pyserial 2.6+ is required")
        # the following import enables serial protocol extensions
        if device.startswith('ftdi:'):
            try:
                from pyftdi import serialext
                serialext.touch()
            except ImportError:
                raise ImportError("PyFTDI module not installed")
        try:
            port = serial_for_url(device,
                                  baudrate=baudrate,
                                  parity=parity or PARITY_NONE,
                                  rtscts=rtscts,
                                  timeout=0)
            if not port.is_open:
                port.open()
            if not port.is_open:
                raise IOError('Cannot open port "%s"' % device)
            if debug:
                backend = port.BACKEND if hasattr(port, 'BACKEND') else '?'
                print("Using serial backend '%s'" % backend)
            return port
        except SerialException as exc:
            raise IOError(str(exc))

    def _logfile_init(self, logfile):
        filepath = abspath(logfile.name)
        self._logfile = (logfile, filepath)
        self._logfile_statstream()

    def _logfile_statstream(self):
        fst = self._logfile[0]
        if fst:
            sres = fstat(fst.fileno())
            self._logfile = (fst, self._logfile[1], sres.st_dev, sres.st_ino)

    def _logfile_reopen_if_needed(self):
        """
        Reopen log file if needed.

        Checks if the underlying file has changed, and if it
        has, close the old stream and reopen the file to get the
        current stream.
        """
        stream = self._logfile[0]
        if not stream:
            return
        try:
            # stat the file by path, checking for existence
            sres = stat(self._logfile[1])
        except FileNotFoundError:
            sres = None
        # compare file system stat with that of our stream file handle
        fdev, fino = self._logfile[2:]
        if not sres or sres.st_dev != fdev or sres.st_ino != fino:
            if stream is not None:
                mode = 'wt' if isinstance(stream, TextIOBase) else 'wb'
                stream.flush()
                stream.close()
                stream = None
                filepath = self._logfile[1]
                stream = open(filepath, mode)
                self._logfile = (stream, filepath)
                self._logfile_statstream()


def get_default_device():
    """Get default serial port for the current host OS.
    """
    if osname == 'nt':
        device = 'COM1'
    elif osname == 'posix':
        (system, _, _, _, _) = uname()
        if system.lower() == 'darwin':
            device = '/dev/cu.usbserial'
        else:
            device = '/dev/ttyS0'
        try:
            stat(device)
        except OSError:
            device = 'ftdi:///1'
    else:
        device = None
    return device


def main():
    """Main routine"""
    debug = False
    try:
        default_device = get_default_device()
        argparser = ArgumentParser(description=modules[__name__].__doc__)
        if osname in ('posix', ):
            argparser.add_argument('-f', '--fullmode', dest='fullmode',
                                   action='store_true',
                                   help='use full terminal mode, exit with '
                                        '[Ctrl]+B')
        argparser.add_argument('-p', '--device', default=default_device,
                               help='serial port device name (default: %s)' %
                               default_device)
        argparser.add_argument('-b', '--baudrate',
                               help='serial port baudrate (default: %d)' %
                               MiniTerm.DEFAULT_BAUDRATE,
                               default='%s' % MiniTerm.DEFAULT_BAUDRATE)
        argparser.add_argument('-w', '--hwflow',
                               action='store_true',
                               help='hardware flow control')
        argparser.add_argument('-P', '--pdelay', type=float,
                               help='pulse DTR at start-up (delay in seconds)')
        argparser.add_argument('-e', '--localecho',
                               action='store_true',
                               help='local echo mode (print all typed chars)')
        argparser.add_argument('-r', '--crlf',
                               action='count', default=0,
                               help='prefix LF with CR char, use twice to '
                                    'replace all LF with CR chars')
        argparser.add_argument('-l', '--loopback',
                               action='store_true',
                               help='loopback mode (send back all received '
                                    'chars)')
        argparser.add_argument('-T', '--reltime', action='store_true',
                               help='show relative time, not host time')
        argparser.add_argument('-o', '--rawlog', type=FileType('wb'),
                               help='output (unformatted) log file')
        argparser.add_argument('-O', '--logfile',
                               help='output formatted, rotatable log file')
        argparser.add_argument('-y', '--syslog',
                               help='push log to syslog daemon '
                                    'facility:[host[:port[:format]]]')
        argparser.add_argument('-g', '--filterlog', action='store_true',
                               help='enable filter log feature, flip-flop with'
                                    ' [Ctrl]+G')
        argparser.add_argument('-c', '--color', action='store_true',
                               help='show available colors and exit')
        argparser.add_argument('-s', '--silent', action='store_true',
                               help='silent mode')
        argparser.add_argument('-v', '--verbose', action='count', default=0,
                               help='increase verbosity')
        argparser.add_argument('-d', '--debug', action='store_true',
                               help='enable debug mode')
        args = argparser.parse_args()
        debug = args.debug

        if args.color:
            fmtcls = get_term_formatter(not is_term())
            fmtcls(stdout, None).show_colors()
            exit(0)

        if not args.device:
            argparser.error('Serial device not specified')

        loglevel = max(DEBUG, ERROR - (10 * (args.verbose or 0)))
        loglevel = min(ERROR, loglevel)
        localfmt = Formatter('%(levelname)s %(asctime)s.%(msecs)03d '
                            '%(message)s', '%H:%M:%S')
        if args.device.startswith('ftdi://'):
            from pyftdi import FtdiLogger
            FtdiLogger.set_formatter(localfmt)
            FtdiLogger.set_level(loglevel if args.verbose > 3 else ERROR)

        if args.filterlog:
            fmtcls = get_term_formatter(not is_term())
            logfilter = fmtcls(stdout, None,
                               basetime=-1 if args.reltime else None)
        else:
            logfilter = None

        miniterm = MiniTerm(device=args.device,
                            baudrate=to_int(args.baudrate),
                            parity='N',
                            rtscts=args.hwflow,
                            logfilter=logfilter,
                            logfile=args.rawlog,
                            filelog=(args.logfile, localfmt, loglevel),
                            syslog=(args.syslog, loglevel),
                            debug=args.debug)
        if args.pdelay:
            miniterm.pulse_dtr(args.pdelay)
        miniterm.run(args.fullmode, args.loopback, args.silent, args.localecho,
                     args.crlf)

    except (IOError, ValueError) as exc:
        print('\nError: %s' % exc, file=stderr)
        if debug:
            print(format_exc(chain=False), file=stderr)
        exit(1)
    except KeyboardInterrupt:
        exit(2)


if __name__ == '__main__':
    main()
