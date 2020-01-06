from tde.misc import to_bool
from logging import getLogger


class GpioError(Exception):
    """Base class exception for all GPIO errors"""


class GpioValueError(ValueError, GpioError):
    """Invalid value for GPIO"""


class GpioDevice:
    """An abstract device that gather one or more GPIO pins"""

    def __init__(self, name, width, master=None):
        if not name:
            raise GpioError('GpioDevice w/o name')
        if not width:
            raise GpioError('GpioDevice w/o width')
        self.log = getLogger('tde.hw.gpio.%s' % name)
        self._master = master
        # width (reachable pin count) of the GPIO device
        self._width = width
        # mask of reachable pins
        self._io_mask = (1 << width) - 1
        # current GPIO value
        self._value = 0
        # pins configured as GPIO
        self._pins = 0
        # pins configured as GPO (output)
        self._dirs = 0
        # whether the device has been configured
        self._configured = False
        self._strfmt = '%%0%dx' % (width//4)
        # groups of pins
        self._groups = set()

    def hxs(self, value):
        return self._strfmt % value

    @property
    def width(self):
        return self._width

    @property
    def is_configured(self):
        return self._configured

    @property
    def groups(self):
        return set(self._groups)

    def get_group(self, name):
        for group in self._groups:
            if group.name == name:
                return group
        raise GpioValueError('No such group: %s' % name)

    def __iter__(self):
        for group in self._groups:
            yield group

    def __getattr__(self, name):
        try:
            return self.get_group(name)
        except GpioValueError as exc:
            raise AttributeError(str(exc))

    def initialize(self):
        self._configure_io()
        self._configured = True

    def create_group(self, name, offset, width, output=None,
                     direction=None, inverted=False, readback=False,
                     vmap=None):
        if (offset+width > self._width) or (offset < 0):
            msg = 'Group of pins %s cannot fit within device' % name
            self.log.critical(msg)
            raise GpioValueError(msg)
        if direction is not None:
            direction = self._parse_direction(direction)
            if not direction:
                if output is not None and output:
                    raise ValueError('Group %s direction redefined (output, '
                                     'input)' % name)
                output = False
            else:
                if output is not None and not output:
                    raise ValueError('Group %s direction redefined (input, '
                                     'output)' % name)
                output = True
        elif output is None:
            output = False
        bits = (1 << width) - 1
        dirs = bits if output else 0
        bits <<= offset
        if ~self._io_mask & bits:
            raise ValueError('Group %s mapped to invalid device pins' % name)
        if bits & self._pins:
            raise ValueError('Group %s override assigned pins' % name)
        group = GpioPinGroup(self, name, offset, width, dirs, inverted,
                             readback, vmap)
        self._dirs |= dirs << offset
        self._pins |= bits
        if inverted:
            self._value = (~0) & group.mask
        self._groups.add(group)
        return group

    def create_pin(self, name, offset, output=None, direction=None,
                   inverted=False, readback=False):
        if offset >= self._width:
            msg = 'Pin %s cannot fit within device' % name
            self.log.critical(msg)
            raise GpioValueError(msg)
        if direction is not None:
            direction = self._parse_direction(direction)
            if not direction:
                if output is not None and output:
                    raise ValueError('Pin %s direction redefined (output, '
                                     'input)' % name)
                output = False
            else:
                if output is not None and not output:
                    raise ValueError('Pin %s direction redefined (output, '
                                     'input)' % name)
                output = True
        elif output is None:
            output = False
        bits = 1 << offset
        if ~self._io_mask & bits:
            raise ValueError('Pin %s mapped to invalid device pin' % name)
        if bits & self._pins:
            raise ValueError('Group %s override assigned pins' % name)
        group = GpioPin(self, name, offset, output, inverted, readback)
        if output:
            self._dirs |= bits
        self._pins |= bits
        self._groups.add(group)
        if inverted:
            self._value = (~0) & group.mask
        return group

    @classmethod
    def _parse_direction(cls, direction):
        if isinstance(direction, str):
            direction = direction.lower()
            if direction == 'in':
                return False
            elif direction == 'out':
                return True
            else:
                raise ValueError('Unknown direction: %s' % direction)
        return to_bool(direction, permissive=False)

    def _update(self, group, value):
        mask = group.mask
        devvalue = self._value & ~mask
        bits = value << group.offset
        devvalue |= bits & mask
        if self.is_configured:
            if self._master:
                self._master.select_slave(self)
            self._write_port(self._filter_output(devvalue))
        else:
            self.log.warning('Cannot update a GPIO device not yet configured')
        self._value = devvalue

    def _retrieve(self, group):
        mask = group.mask
        devvalue = self._value & ~mask
        if not self.is_configured:
            self.log.warning('Cannot retrieve from a GPIO device not yet '
                             'configured')
        if self._master:
            self._master.select_slave(self)
        readvalue = self._filter_input(self._read_port())
        readvalue &= mask
        devvalue |= readvalue
        self._value = devvalue
        readvalue >>= group.offset
        return readvalue

    def _configure_io(self):
        """Configure the IO ports"""
        raise NotImplementedError('Implementation is missing: %s' %
                                  self.__class__.__name__)

    def _write_port(self, value):
        """Concrete class should implement this method"""
        raise NotImplementedError('Implementation is missing: %s' %
                                  self.__class__.__name__)

    def _read_port(self):
        """Concrete class should implement this method"""
        raise NotImplementedError('Implementation is missing: %s' %
                                  self.__class__.__name__)

    def _filter_output(self, value):
        """Concrete class may override this method to filter the output value
           before it is actually written to the HW
        """
        return value

    def _filter_input(self, value):
        """Concrete class may override this method to filter the input value
           right after it has been read out from the HW
        """
        return value


class GpioPinGroup:
    """An abstract group of consecutive GPIO pins managed by an underlying
       device
    """

    def __init__(self, gpiodev, name, offset, width, direction,
                 inverted=False, readback=False, vmap=None):
        comps = __name__.split('.')[:-1]
        comps.append(name)
        self.log = getLogger('.'.join(comps))
        self._name = name
        self._dev = gpiodev
        self._offset = offset
        self._width = width
        self._bitmask = (1 << self.width) - 1
        self._dir = direction
        self._inverted = inverted
        self._vmap = vmap
        self._out = 0
        self._read_back = readback

    @property
    def name(self):
        return self._name

    @property
    def width(self):
        return self._width

    @property
    def output(self):
        return self._dir != 0

    @property
    def offset(self):
        return self._offset

    @property
    def mask(self):
        return self._bitmask << self.offset

    def set(self, value):
        self.log.debug('Set %x', value)
        if self._vmap:
            try:
                value = self._vmap[value]
            except KeyError:
                raise GpioValueError('Unmapped value: %d' % value)
        if value >= (1 << self._width):
            msg = 'Value %d cannot be coded on %d bits' % (value, self._width)
            self.log.error(msg)
            raise GpioValueError(msg)
        if self._inverted:
            value = (~value) & self._bitmask
        self._dev._update(self, value)
        self._out = value

    def get(self):
        if self._dir and self._read_back:
            value = self._out
            self.log.debug('GetO %x', value)
        else:
            value = self._dev._retrieve(self)
            self.log.debug('GetI %x', value)
        if self._inverted:
            value = (~value) & self._bitmask
        if self._vmap:
            try:
                value = self._vmap[value]
            except KeyError:
                raise GpioValueError('Unmapped value: %d' % value)
        return value


class GpioPin(GpioPinGroup):
    """A simple pin which is part of a larger device
    """

    def __init__(self, gpiodev, name, position, output, inverted=False,
                 readback=False):
        direction = int(to_bool(output))
        super(GpioPin, self).__init__(gpiodev, name, position, 1, direction,
                                      inverted, readback)

    def set(self, value):
        value = to_bool(value)
        super(GpioPin, self).set(int(value))

    def get(self):
        value = super(GpioPin, self).get()
        return bool(value)
