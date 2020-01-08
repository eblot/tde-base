"""FTDI command-line interface management"""

from binascii import hexlify, unhexlify
from logging import getLogger
from importlib import import_module
from re import compile as recompile
from tde.cmdshell import CmdShellError, CmdShellProvider
from tde.misc import classproperty, to_bool, to_int, to_frequency

#pylint: disable-msg=inconsistent-return-statements
#pylint: disable-msg=no-self-argument
#pylint: disable-msg=missing-docstring
#pylint: disable-msg=invalid-name
#pylint: disable-msg=too-many-locals


class FtdiCommandProvider(CmdShellProvider):
    """PyFTDI command line interface

       :param url: FTDI url to access the device (ftdi://[VID]:[PID][:SN]/PORT)
       :param mode: FTDI feature mode: gpio, spi, i2c
    """

    @classproperty
    def domains(cls):
        return 'ft', 'Ftdi'

    @classproperty
    def containers(cls):
        return cls.enumerate_containers(FtdiCommand, __name__)

    @property
    def context(self):
        return {'controller': self._ctrl}

    def finalize(self):
        if self._ctrl:
            self._ctrl.terminate()
            self._ctrl = None

    def __init__(self, url, mode, **kwargs):
        self._ctrl = None
        try:
            module = import_module('.%s' % mode,
                                   '.'.join(__name__.split('.')[1:-1]))
            ctrl_cls = getattr(module, '%sController' % mode.title())
            ctrl = ctrl_cls()
            try:
                if 'frequency' in kwargs:
                    kwargs['frequency'] = to_frequency(kwargs['frequency'])
            except ValueError:
                raise CmdShellError('Invalid bus frequency: %s' %
                                    kwargs['frequency'])
            ctrl.configure(url, **kwargs)
        except ImportError as ex:
            raise CmdShellError('Unsupported FTDI mode: %s' % ex)
        except AttributeError as ex:
            raise CmdShellError('Unsupported FTDI mode: %s' % ex)
        except Exception as ex:
            raise CmdShellError('Cannot configure FTDI: %s' % ex)
        self._ctrl = ctrl


class FtdiCommand:
    """Base class for all command handlers
    """

    GET_CRE = recompile(r'^([AB])([DC])([0-7])$')
    SET_CRE = recompile(r'^([AB])([DC])([0-7])[:=](\w+)$')

    def __init__(self):
        self.log = getLogger('tde.pyftdi.cli')
        self._ports = None

    @property
    def io_port(self):
        raise NotImplementedError('GPIO mode not implemented in this mode')

    @property
    def available_ports(self):
        raise NotImplementedError('GPIO mode not implemented in this mode')

    @property
    def mode(self):
        raise NotImplementedError('Base class')

    @property
    def port_format(self):
        return '%%0%dx' % ((self.io_port.pins & 0xFF00) and 4 or 2)

    @property
    def ports(self):
        if not self._ports:
            self._ports = {name: 1 << (8*pos) for pos, name
                           in enumerate(self.available_ports)}
        return self._ports

    def decode_port(self, value, on, off):
        pins = {'A%s%d' % (name, ix): value & (base << ix) and on or off
                for ix in range(8)
                for name, base in self.ports.items()}
        return pins

    def decode_direction(self, value):
        return self.decode_port(value, 'out', 'in')

    def decode_value(self, value):
        return self.decode_port(value, 'on', 'off')

    def encode_port(self, dirspecs, initial=0, inout=False, role=True):
        ports = self.ports
        cre = self.SET_CRE if role else self.GET_CRE
        for dirspec in dirspecs:
            mo = cre.match(dirspec)
            if not mo:
                self.log.error('Invalid port syntax')
                raise ValueError()
            port = 1 + int(mo.group(1) == 'B')
            group = mo.group(2)
            if group not in self.available_ports:
                self.log.error('No such pin on this device')
                raise ValueError()
            base = ports[group]
            if port != 1:
                # for now...
                self.log.error('Invalid port')
                raise ValueError()
            pin = int(mo.group(3))
            if role:
                val = mo.group(4)
                if inout and val[0].lower() == 'o':
                    value = 1
                elif inout and val[0].lower() == 'i':
                    value = 0
                else:
                    try:
                        value = to_bool(val, permissive=False)
                    except ValueError:
                        self.log.error('Not a boolean for pin %d', pin)
                        raise
            else:
                value = 1
            if not value:
                initial &= ~(base << pin)
            else:
                initial |= base << pin
        return initial

    def encode_direction(self, dirspecs, initial=0, role=True):
        return self.encode_port(dirspecs, initial, inout=True, role=role)

    def encode_value(self, dirspecs, initial=0, role=True):
        return self.encode_port(dirspecs, initial, role=role)

    def port_sort(self, pin):
        if isinstance(pin, tuple):
            pin = pin[0]
        return (pin[0], self.available_ports.index(pin[1]), pin[2:])

    def _do_get_direction(self, *args):
        mask = self.io_port.all_pins
        if args:
            try:
                new_mask = to_int(args[0])
                if len(args) > 1:
                    self.log.error('Too many arguments')
                    raise ValueError()
            except ValueError:
                arguments = list(args)
                try:
                    new_mask = self.encode_value(arguments, role=False)
                except ValueError:
                    raise CmdShellError('Invalid value: %s' %
                                        ' '.join(arguments))
            if new_mask > mask:
                raise CmdShellError('Invalid mask')
            mask = new_mask
        direction = self.io_port.direction
        decdir = self.decode_direction(direction)
        dir_fmt = 'Direction: 0x%s' % self.port_format
        print(dir_fmt % direction)
        namedir = {}
        decmask = self.decode_port(mask, True, False)
        for pin, direction in sorted(decdir.items(),
                                     key=self.port_sort):
            if decmask[pin]:
                namedir[pin] = to_bool(direction)
                pstr = '%s:' % pin
                print('  %-5s %s' % (pstr, direction))
        return namedir if args else direction

    def _do_set_direction(self, first, *args):
        arguments = [first] + list(args)
        direction = self.io_port.direction
        try:
            new_dir = to_int(first)
            if args:
                raise ValueError()
        except ValueError:
            try:
                new_dir = self.encode_direction(arguments, direction)
            except ValueError:
                raise CmdShellError('Invalid direction: %s' %
                                    ' '.join(arguments))
        try:
            change = (direction ^ new_dir) & self.io_port.all_pins
            self.io_port.set_direction(change, new_dir)
        except Exception as ex:
            raise CmdShellError('Cannot change direction: %s' % ex)

    def _do_get(self, *args):
        mask = self.io_port.pins
        if args:
            try:
                new_mask = to_int(args[0])
                if len(args) > 1:
                    self.log.error('Too many arguments')
                    raise ValueError()
            except ValueError:
                arguments = list(args)
                try:
                    new_mask = self.encode_value(arguments, role=False)
                except ValueError:
                    raise CmdShellError('Invalid value: %s' %
                                        ' '.join(arguments))
            if new_mask > mask:
                raise CmdShellError('Invalid IO pin(s)')
            mask = new_mask
        value = self.io_port.read()
        decval = self.decode_value(value)
        val_fmt = 'Value: 0x%s' % self.port_format
        print(val_fmt % value)
        decmask = self.decode_port(mask, True, False)
        outval = {}
        for pin, val in sorted(decval.items()):
            if decmask[pin]:
                outval[pin] = to_bool(val)
                pstr = '%s:' % pin
                print('  %-5s %s' % (pstr, val))
        return outval if args else value

    def _do_set(self, first, *args):
        mask = self.io_port.pins
        arguments = [first] + list(args)
        value = self.io_port.read()
        try:
            new_val = to_int(first)
            if args:
                self.log.error('Too many arguments')
                raise ValueError()
            new_mask = 1 << new_val
        except ValueError:
            try:
                new_val = self.encode_value(arguments, value)
                new_mask = self.encode_value(arguments, role=True)
            except ValueError:
                raise CmdShellError('Invalid value: %s' %
                                    ' '.join(arguments))
        if new_mask > mask:
            raise CmdShellError('Invalid IO pin(s)')
        try:
            self.io_port.write(new_val)
        except Exception as ex:
            raise CmdShellError('Cannot change value: %s' % ex)


class FtdiGpioCommand(FtdiCommand):
    """Drive FTDI GPIO pins.

       <specs> is a space separated list of one or more <spec> specifiers.
       <ports> is a space separated list of one or more <port> specifiers.

       <spec> should be specified as <port>:<level> or <port>=<level>

       <port> is a string that match a FTDI port, using the <bus><pin> syntax,
       where bus is among ``AD``, ``AC``, ``BD``, ``BC``. The supported ports
       depend on the actual FTDI device.

       * when a direction is specified, <level> should be specified as either:
         <in>, <out> or a boolean, output being True and input being False

       * when a GPIO value is specified, <level> should be specified as either:
         <off>, <on> or a boolean
    """

    def __init__(self, controller):
        super(FtdiGpioCommand, self).__init__()
        self._ctrl = controller

    @property
    def io_port(self):
        return self._ctrl

    @property
    def available_ports(self):
        return 'D'

    @property
    def mode(self):
        return self._ctrl.__class__.__name__[:-len('Controller')].lower()

    def get_commands(self):
        mode = self.mode
        if mode != 'gpio':
            return
        yield ('dir get', '[ports]',
               FtdiGpioCommand.build_doc('Get GPIO direction'),
               None, self._do_get_direction)
        yield ('dir set', '<value|specs>',
               FtdiGpioCommand.build_doc('Set GPIO direction'),
               None, self._do_set_direction)
        yield ('get', '[value|ports]',
               FtdiGpioCommand.build_doc('Get GPIO value'),
               None, self._do_get)
        yield ('set', '<value|specs>',
               FtdiGpioCommand.build_doc('Set GPIO value'),
               None, self._do_set)

    @classmethod
    def build_doc(cls, cmd):
        doc = '\n\n'.join((cmd, '\n'.join(cls.__doc__.split('\n')[2:])))
        return doc.replace("``", "'")


class FtdiSpiCommand(FtdiCommand):

    def __init__(self, controller):
        super(FtdiSpiCommand, self).__init__()
        self._ctrl = controller
        self._slaves = {}
        self._io = None

    @property
    def io_port(self):
        if not self._io:
            self._io = self._ctrl.get_gpio()
        return self._io

    @property
    def available_ports(self):
        return 'DC' if self.io_port.all_pins & 0xFF00 else 'D'

    @property
    def mode(self):
        return self._ctrl.__class__.__name__[:-len('Controller')].lower()

    def get_commands(self):
        mode = self.mode
        if mode != 'spi':
            return
        yield ('dir get', '[ports]',
               FtdiGpioCommand.build_doc('Get GPIO direction'),
               None, self._do_get_direction)
        yield ('dir set', '<value|specs>',
               FtdiGpioCommand.build_doc('Set GPIO direction'),
               None, self._do_set_direction)
        yield ('get', '[value|ports]',
               FtdiGpioCommand.build_doc('Get GPIO value'),
               None, self._do_get)
        yield ('set', '<value|specs>',
               FtdiGpioCommand.build_doc('Set GPIO value'),
               None, self._do_set)
        yield ('configure', '<slave> <mode> [frequency]',
               'Configure a slave',
               self._complete_configure, self._do_configure)
        yield ('read', '[slave] <count>',
               'Read bytes from slave (half-duplex)',
               self._complete_read, self._do_read)
        yield ('write', '[slave] <data> (half-duplex)',
               'Write bytes to slave',
               self._complete_write, self._do_write)
        yield ('sequence', '[slave] <data> <count>',
               'Write then read bytes from/to slave (half-duplex)',
               self._complete_sequence, self._do_sequence)
        yield ('exchange', '[slave] <data> <count>',
               'Write and read bytes from/to slave (full-duplex)',
               self._complete_exchange, self._do_exchange)
        yield ('flush', '[slave]',
               'Force-flush HW FIFO',
               self._complete_flush, self._do_flush)

    def _complete_configure(self, args):
        if len(args) == 1:
            channels = {c for c in range(self._ctrl.channels)}
            channels -= self._ctrl.active_channels
            return [f'{port}' for port in channels]
        if len(args) == 2:
            return [f'{m}' for m in range(4)]

    def _do_configure(self, slave, mode, *args):
        try:
            islave = to_int(slave)
        except ValueError:
            raise CmdShellError(f'Invalid slave {slave}')
        if islave not in range(self._ctrl.channels):
            raise CmdShellError(f'No such CS line {islave}')
        if islave in self._ctrl.active_channels:
            raise CmdShellError(f'Slave {islave} already configured')
        try:
            imode = to_int(mode)
        except ValueError:
            raise CmdShellError(f'Invalid mode {mode}')
        if not 0 <= imode <= 3:
            raise CmdShellError(f'Invalid SPI mode {imode}')
        if args:
            try:
                frequency = to_frequency(args[0])
            except ValueError:
                raise CmdShellError(f'Invalid SPI freqency {args[0]}')
        else:
            frequency = None
        try:
            self._slaves[islave] = self._ctrl.get_port(islave, frequency,
                                                       imode)
        except Exception as exc:
            raise CmdShellError(f'Cannot configure slave {islave}: {exc}')

    def _complete_read(self, args):
        if len(args) == 1:
            return [f'{port}' for port in self._ctrl.active_channels]

    def _do_read(self, arg, *args):
        if args:
            try:
                islave = to_int(arg)
            except ValueError:
                raise CmdShellError(f'Invalid slave {arg}')
            count = args[0]
        else:
            islave = 0
            count = arg
        if islave not in self._slaves:
            raise CmdShellError(f'Slave {islave} is not configured')
        try:
            icount = to_int(count)
        except ValueError:
            raise CmdShellError(f'Invalid count of bytes')
        data = self._slaves[islave].read(icount)
        hstr = hexlify(data).decode()
        print(f' rx: {hstr} {len(data)}')
        return data

    def _complete_write(self, args):
        if len(args) == 1:
            return [f'{port}' for port in self._ctrl.active_channels]

    def _do_write(self, arg, *args):
        if args:
            try:
                islave = to_int(arg)
            except ValueError:
                raise CmdShellError(f'Invalid slave {arg}')
            data = ''.join(args)
        else:
            islave = 0
            data = arg
        if islave not in self._slaves:
            raise CmdShellError(f'Slave {islave} is not configured')
        try:
            buf = unhexlify(data)
        except (TypeError, ValueError):
            raise CmdShellError(f'Invalid data format')
        self._slaves[islave].write(buf)

    def _complete_sequence(self, args):
        if len(args) == 1:
            return [f'{port}' for port in self._ctrl.active_channels]

    def _complete_exchange(self, args):
        if len(args) == 1:
            return [f'{port}' for port in self._ctrl.active_channels]

    def _do_sequence(self, arg1, arg2, *args):
        return self._exchange(False, arg1, arg2, *args)

    def _do_exchange(self, arg1, arg2, *args):
        return self._exchange(True, arg1, arg2, *args)

    def _exchange(self, duplex, arg1, arg2, *args):
        if args:
            try:
                islave = to_int(arg1)
            except ValueError:
                raise CmdShellError(f'Invalid slave {arg1}')
            data = arg2
            count = args[0]
        else:
            islave = 0
            data = arg1
            count = arg2
        if islave not in self._slaves:
            raise CmdShellError(f'Slave {islave} is not configured')
        try:
            buf = unhexlify(data)
        except (TypeError, ValueError):
            raise CmdShellError(f'Invalid data format')
        if count in ('-', 'auto'):
            icount = len(buf)
        else:
            try:
                icount = to_int(count)
            except ValueError:
                raise CmdShellError(f'Invalid count of bytes')
        data = self._slaves[islave].exchange(buf, readlen=icount,
                                             duplex=duplex)
        hstr = hexlify(data).decode()
        print(f' rx: {hstr} {len(data)}')
        return data

    def _complete_flush(self, args):
        if len(args) == 1:
            return [f'{port}' for port in self._ctrl.active_channels]

    def _do_flush(self, arg):
        try:
            islave = to_int(arg)
        except ValueError:
            raise CmdShellError(f'Invalid slave {arg}')
        if islave not in self._slaves:
            raise CmdShellError(f'Slave {islave} is not configured')
        self._slaves[islave].flush()
