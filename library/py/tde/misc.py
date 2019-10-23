#!/usr/bin/python3

"""Miscelleanous helpers

"""

import logging
from array import array
from configparser import SafeConfigParser, InterpolationSyntaxError
from copy import deepcopy
from functools import wraps
from logging.handlers import SysLogHandler, SYSLOG_UDP_PORT
from os import makedirs, unlink
from os.path import basename, dirname, isdir
from re import match
from shutil import move
from socket import gethostbyname
from tempfile import NamedTemporaryFile
from threading import Lock
from types import MethodType
from typing import (Any, Iterable, Mapping, NewType, Optional, Sequence, Tuple,
                    Type, Union)


TRUE_BOOLEANS = ['on', 'high', 'true', 'enable', 'enabled', 'yes', '1']
"""String values evaluated as true boolean values"""

FALSE_BOOLEANS = ['off', 'low', 'false', 'disable', 'disabled', 'no', '0']
"""String values evaluated as false boolean values"""

ASCIIFILTER = ''.join([((len(repr(chr(_x))) == 3) or (_x == 0x5c)) and chr(_x)
                       or '.' for _x in range(128)]) + '.' * 128
ASCIIFILTER = bytearray(ASCIIFILTER.encode('ascii'))
"""ASCII or '.' filter"""


def hexdump(data, full=False, abbreviate=False):
    """Convert a binary buffer into a hexadecimal representation.

       Return a multi-line strings with hexadecimal values and ASCII
       representation of the buffer data.

       :param data: binary buffer to dump
       :type data: bytes or array or bytearray or list(int)
       :param bool full: use `hexdump -Cv` format
       :param bool abbreviate: replace identical lines with '*'
    """
    try:
        if isinstance(data, (bytes, array)):
            src = bytearray(data)
        elif not isinstance(data, bytearray):
            # data may be a list/tuple
            src = bytearray(b''.join(data))
        else:
            src = data
    except Exception:
        raise TypeError("Unsupported data type '%s'" % type(data))

    length = 16
    result = []
    last = b''
    abv = False
    for i in range(0, len(src), length):
        s = src[i:i+length]
        if abbreviate:
            if s == last:
                if not abv:
                    result.append('*\n')
                    abv = True
                continue
            else:
                abv = False
        hexa = ' '.join(["%02x" % x for x in s])
        printable = s.translate(ASCIIFILTER).decode('ascii')
        if full:
            hx1, hx2 = hexa[:3*8], hexa[3*8:]
            hl = length//2
            result.append("%08x  %-*s %-*s |%s|\n" %
                          (i, hl*3, hx1, hl*3, hx2, printable))
        else:
            result.append("%06x   %-*s  %s\n" %
                          (i, length*3, hexa, printable))
        last = s
    return ''.join(result)


def hexline(data, sep=' '):
    """Convert a binary buffer into a hexadecimal representation.

       Return a string with hexadecimal values and ASCII representation
       of the buffer data.

       :param data: binary buffer to dump
       :type data: bytes or array or bytearray or list(int)
    """
    try:
        if isinstance(data, (bytes, array)):
            src = bytearray(data)
        elif not isinstance(data, bytearray):
            # data may be a list/tuple
            src = bytearray(b''.join(data))
        else:
            src = data
    except Exception:
        raise TypeError("Unsupported data type '%s'" % type(data))

    hexa = sep.join(["%02x" % x for x in src])
    printable = src.translate(ASCIIFILTER).decode('ascii')
    return "(%d) %s : %s" % (len(data), hexa, printable)


def to_int(value):
    """Parse a value and convert it into an integer value if possible.

       Input value may be:
       - a string with an integer coded as a decimal value
       - a string with an integer coded as a hexadecimal value
       - a integral value
       - a integral value with a unit specifier (kilo or mega)

       :param value: input value to convert to an integer
       :type value: str or int
       :return: the value as an integer
       :rtype: int
       :raise ValueError: if the input value cannot be converted into an int
    """
    if not value:
        return 0
    if isinstance(value, int):
        return value
    mo = match(r'^\s*(\d+)\s*(?:([KMkm]i?)?B?)?\s*$', value)
    if mo:
        mult = {'K': (1000),
                'KI': (1 << 10),
                'M': (1000 * 1000),
                'MI': (1 << 20)}
        value = int(mo.group(1))
        if mo.group(2):
            value *= mult[mo.group(2).upper()]
        return value
    return int(value.strip(), value.startswith('0x') and 16 or 10)


def to_bool(value, permissive=True, prohibit_int=False):
    """Parse a string and convert it into a boolean value if possible.

       Input value may be:
       - a string with an integer value, if `prohibit_int` is not set
       - a boolean value
       - a string with a common boolean definition

       :param value: the value to parse and convert
       :type value: str or int or bool
       :param bool permissive: default to the False value if parsing fails
       :param bool prohibit_int: prohibit an integral type as the input value
       :rtype: bool
       :raise ValueError: if the input value cannot be converted into an bool
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if not prohibit_int:
            if permissive:
                return bool(value)
            if value in (0, 1):
                return bool(value)
        raise ValueError("Invalid boolean value: '%d'", value)
    if value.lower() in TRUE_BOOLEANS:
        return True
    if permissive or (value.lower() in FALSE_BOOLEANS):
        return False
    raise ValueError('"Invalid boolean value: "%s"' % value)


def xor(_a_, _b_):
    """XOR logical operation.

       :param _a_: first argument
       :param _b_: second argument
       :return: xor-ed value
       :rtype: bool
    """
    return bool((not(_a_) and _b_) or (_a_ and not(_b_)))


def is_iterable(obj):
    """Tells whether an instance is iterable or not.

       :param obj: the instance to test
       :type obj: object
       :return: True if the object is iterable
       :rtype: bool
    """
    try:
        iter(obj)
        return True
    except TypeError:
        return False


def pretty_size(size, sep=' ', lim_k=1 << 10, lim_m=10 << 20, plural=True,
                floor=True):
    """Convert a size into a more readable unit-indexed size (KiB, MiB)

       :param int size: integral value to convert
       :param str sep: the separator character between the integral value and
            the unit specifier
       :param int lim_k: any value above this limit is a candidate for KiB
            conversion.
       :param int lim_m: any value above this limit is a candidate for MiB
            conversion.
       :param bool plural: whether to append a final 's' to byte(s)
       :param bool floor: how to behave when exact conversion cannot be
            achieved: take the closest, smaller value or fallback to the next
            unit that allows the exact representation of the input value
       :return: the prettyfied size
       :rtype: str
    """
    size = int(size)
    if size > lim_m:
        ssize = size >> 20
        if floor or (ssize << 20) == size:
            return '%d%sMiB' % (ssize, sep)
    if size > lim_k:
        ssize = size >> 10
        if floor or (ssize << 10) == size:
            return '%d%sKiB' % (ssize, sep)
    return '%d%sbyte%s' % (size, sep, (plural and 's' or ''))


def pretty_period(value: Union[int, float],
                  units: Optional[str]=None,
                  sep: Optional[str]=None) -> str:
    """Convert a delay/period into a string.

       :param value: the period or delay in seconds
       :param units: optional units. Default to 'h m s'. Accept either "degree"
                     to select quote-based notation, or a free string which
                     should be at least 3 char long.
       :return: the formatted string
    """
    second = int(value)
    ms = 0 if isinstance(value, int) else int(1000*(value-second+0.0005))
    hour = second//3600
    second -= hour*3600
    minute = second//60
    second -= minute*60
    if not units:
        units = 'smh'
    elif fmt == 'degree':
        units = '"\'h'
    else:
        if not isinstance(units, str) or len(units) < 3:
            raise ValueError('Invalid format')
        units = ''.join([c for c in reversed(units)])
    values = list(zip([second, minute, hour], units))
    while not values[-1][0]:
        values.pop()
    if ms:
        values[0] = ('%d.%d' % (values[0][0], ms), values[0][1])
    return ' '.join(['%s%s' % v for v in reversed(values)])


def group(lst, count):
    """Group a list into consecutive count-tuples. Incomplete tuples are
    discarded.

    `group([0,3,4,10,2,3], 2) => [(0,3), (4,10), (2,3)]`

    From: http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/303060
    """
    return list(zip(*[lst[i::count] for i in range(count)]))


def flatten(lst):
    """Flatten a list. See http://stackoverflow.com/questions/952914/\
           making-a-flat-list-out-of-list-of-lists-in-python
    """
    return [item for sublist in lst for item in sublist]


def file_generator(path, action, *args):
    """Simple helper to build output files.

       Create the destination directory if it does not yet exist

       Remove the file if the builder fails

       Use a temporary file to avoid discarding a previous valid file,
       hence assuring its atomicity

       :param path: pathname of the file
       :param action: a callable that builds the output stream content
       :param args: a list of optional arguments to pass over to action
    """
    tmppath = None
    try:
        outdir = dirname(path)
        if outdir and not isdir(outdir):
            makedirs(outdir)
        with NamedTemporaryFile(mode='wb', prefix=basename(path),
                                delete=False) as out_:
            tmppath = out_.name
            action(out_, *args)
        if tmppath:
            move(tmppath, path)
    except Exception:
        try:
            if tmppath:
                unlink(tmppath)
        except OSError:
            pass
        raise


def configure_logging(verbosity, longfmt, logdest=None, loggers=None,
                      threadid=False, **kwargs):
    """Create a default configuration for logging, as the same logging idiom
       is used with many scripts.

       Note: the order of loggers does matter, as any logger which does not
       have at least a handler is assigned all the handlers of the first logger
       that does have one or more.

       :param verbosity: a verbosity level, usually args.verbose
       :param longfmt: a boolean value, to use a detailed format
       :param logtest: a log file for the output stream, defaults to stderr
       :param loggers: an iterable of loggers to reconfigure
       :param threadid: set to add the thread ID to the trace message
       :param kwargs: optional maximum level to cap log sources:

                      * key is the maximal loglevel defines as a string
                      * value is an iterable of source logger names

                      keyword starting with an underscore are used to tweak
                      the log format. Supported (boolean) option include:

                      * _notime: disable time in log messages
                      * _lineno: add line number in log messages

       :return: the loglevel, in logging enumerated value
    """
    loglevel = max(logging.DEBUG, logging.ERROR - (10 * (verbosity or 0)))
    loglevel = min(logging.ERROR, loglevel)
    notime = to_bool(kwargs.get('_notime', False))

    dsthandler = None
    syslog = False
    if logdest and isinstance(logdest, str):
        mo = match(r'^syslog://(?P<host>[^:]*)?(?::(?P<port>\d+))?'
                   r'(?:/(?P<facility>\w+))?$', logdest)
        if mo:
            host = mo.group('host') or 'localhost'
            port = mo.group('port')
            facname = mo.group('facility') or 'local5'
            try:
                facility = getattr(SysLogHandler,
                                   'LOG_%s' % facname.upper())
            except AttributeError as exc:
                print(exc)
                raise RuntimeError('Invalid syslog facility')
            try:
                if mo.group('port'):
                    port = int(mo.group('port'))
                else:
                    port = SYSLOG_UDP_PORT
            except (ValueError, TypeError):
                raise RuntimeError('Invalid syslog port')
            try:
                addr = gethostbyname(host)
            except OSError:
                raise RuntimeError('Invalid syslog host')
            syslog = True
            dsthandler = SysLogHandler(address=(addr, port),
                                       facility=facility)
        if not dsthandler:
            dsthandler = logging.FileHandler(logdest)

    if longfmt:
        if notime or syslog:
            fmts = []
        else:
            fmts = [r'%(asctime)s.%(msecs)03d']
        if not syslog:
            fmts.append(r'%(levelname)-8s %(name)-24s')
        else:
            fmts.append(r'%(name)s:')
        if to_bool(kwargs.get('_lineno', False)):
            fmts.append(r'[%(lineno)4d]')
        if threadid:
            fmts.append('%(thread)X')
        fmts.append('%(message)s')
        if notime:
            formatter = logging.Formatter(' '.join(fmts))
        else:
            formatter = logging.Formatter(' '.join(fmts), '%H:%M:%S')
    else:
        formatter = logging.Formatter('%(message)s')
    default_handlers = []

    def _need_handler(logcls):
        if not logcls.log.hasHandlers():
            return True
        return not any([handler for handler in logcls.log.handlers
                        if not isinstance(handler, logging.NullHandler)])

    for logger in loggers or []:
        # Do not propagate log message above this top-level logger
        logger.log.propagate = False
        # replicate the handlers of the first loggger to all other handlers
        # which have not been assigned one or more handlers yet
        if not default_handlers and logger.log.handlers:
            default_handlers = logger.log.handlers
        elif _need_handler(logger) and default_handlers:
            for handler in default_handlers:
                logger.log.addHandler(handler)
        if dsthandler:
            # create a copy of handlers, as we need to modify it
            handlers = list(logger.log.handlers)
            for handler in handlers:
                if isinstance(handler, logging.StreamHandler):
                    # remove all StreamHandlers
                    logger.log.removeHandler(handler)
            logger.log.addHandler(dsthandler)
        logger.set_formatter(formatter)
        logger.set_level(loglevel)
    for maxlevel, sources in kwargs.items():
        if maxlevel.startswith('_'):
            # not a level, but an logging option
            continue
        try:
            logging_level = getattr(logging, maxlevel.upper())
        except AttributeError:
            raise ValueError('No such log level: %s' % maxlevel)
        for src in sources:
            logging.getLogger(src).setLevel(max(logging_level, loglevel))
    return loglevel


def seq2ranges(seq: Sequence[int]) -> Sequence[Tuple[int, int]]:
    """Find continous ranges of integers in a list.isinstance

       :param seq: the sequence of integer to parse
       :return: a sequence of tuple of range of integers
    """
    ranges = []
    first = last = None
    for item in sorted(seq):
        if not isinstance(item, int):
            raise TypeError('Sequence contains non-integer values')
        if first is None:
            first = item
            last = item
            continue
        if item == last+1:
            last = item
            continue
        ranges.append((first, last))
        first = last = item
    if first is not None:
        ranges.append((first, last))
    return ranges


def _make_version(version: Union[str,int,Tuple[int]]) -> Tuple[int]:
    """Build a tuple-of-integer version from a string or a unique integer.

       :param version: the version to convert, if needed
       :return: the tuple-based version
    """
    try:
        if isinstance(version, str):
            version = tuple(int(x) for x in version.split('.'))
        elif isinstance(version, int):
            version = (version, )
        elif isinstance(version, tuple):
            if not all([isinstance(x, int) for x in version]):
                raise ValueError()
        else:
            raise ValueError()
        return version
    except ValueError:
        raise ValueError('Invalid version string')


def since(version: Union[str,int,Tuple[int]]):
    """This decorator defines the inclusive version since the function is
       supported.

       .. seealso:: :py:func:`version_match`

       :param version: the first supported version
    """
    version = _make_version(version)
    def _version_decorator_(func):
        func._tde_min_version = version
        @wraps(func)
        def _func_wrapper_(self, *args, **kwargs):
            return func(self, *args, **kwargs)
        return _func_wrapper_
    return _version_decorator_


def until(version: Union[str,int,Tuple[int]]):
    """This decorator defines the exclusive version until the function was
       supported.

       .. seealso:: :py:func:`version_match`

       :param version: the first non-supporting version
    """
    version = _make_version(version)
    def _version_decorator_(func):
        func._tde_max_version = version
        @wraps(func)
        def _func_wrapper_(self, *args, **kwargs):
            return func(self, *args, **kwargs)
        return _func_wrapper_
    return _version_decorator_


def version_match(obj: Any, version: Union[str,int,Tuple[int]]) -> bool:
    """Test if an object (likely a function or a method) supports the
       defined version.

       If the object does not define any version range, version is considered
       to always match.

       The object may define a lower (minimal) and an upper (maximal) version.

       .. seealso:: :py:func:`since`
       .. seealso:: :py:func:`until`

       :param obj: the object to test
       :param version: the version to test
       :return: True if version match, False otherwise
    """
    version = _make_version(version)
    if hasattr(obj, '_tde_min_version'):
        if version < obj._tde_min_version:
            return False
    if hasattr(obj, '_tde_max_version'):
        if version >= obj._tde_max_version:
            return False
    return True

def get_time_logger(name: Optional[str] = None):
    """Create a logger whose record time can be defined.

       :param name: name of the logger
       :return: logger
    """
    logger = logging.getLogger(name)
    def make_record(self, name, level, fn, lno, msg, args, exc_info,
                    func=None, extra=None, sinfo=None):
        # ack Logger.makeRecord to rewrite the record time
        rv = logging.LogRecord(name, level, fn, lno, msg, args, exc_info, func,
                               sinfo)
        if extra is not None:
            for exk, exv in extra.items():
                if exk != 'timestamp':
                    rv.__dict__[exk] = exv
                else:
                    rv.__dict__['created'] = exv
                    rv.__dict__['msecs'] = (exv - int(exv)) * 1000
                    # ignore relativeCreated for now
        return rv
    logger.makeRecord = MethodType(make_record, logger)
    return logger


def merge_dicts(dict_a: dict, dict_b: dict) -> dict:
    """Recursively merge dictionaries.

       from https://stackoverflow.com/questions/38987/\
               how-do-i-merge-two-dictionaries-in-a-single-expression
    """
    dict_c = {}
    try:
        overlapping_keys = dict_a.keys() & dict_b.keys()
    except AttributeError:
        def clsn(obj): return obj.__class__.__name__
        raise ValueError(f'Cannot merge {clsn(dict_a)} and {clsn(dict_b)}')
    for key in overlapping_keys:
        try:
            dict_c[key] = merge_dicts(dict_a[key], dict_b[key])
        except ValueError as exc:
            raise ValueError(f'{exc}: {key}')
    for key in dict_a.keys() - overlapping_keys:
        dict_c[key] = deepcopy(dict_a[key])
    for key in dict_b.keys() - overlapping_keys:
        dict_c[key] = deepcopy(dict_b[key])
    return dict_c


# ----------------------------------------------------------------------------

class classproperty(property):
    """Getter property decorator for a class"""
    def __get__(self, obj, objtype=None):
        return super(classproperty, self).__get__(objtype)


class EasyConfigParser(SafeConfigParser):
    """ConfigParser extension to support default config values and do not
       mess with multi-line option strings"""

    INDENT_SIZE = 8

    InterpolationSyntaxError = InterpolationSyntaxError

    def get(self, section, option, default=None, raw=True, vars=None,
            fallback=None):
        """Return the section:option value if it exists, or the default value
           if either the section or the option is missing"""
        if not self.has_section(section):
            return default
        if not self.has_option(section, option):
            return default
        return SafeConfigParser.get(self, section, option, raw=raw, vars=vars,
                                    fallback=fallback)

    def write(self, filep):
        """Write an .ini-format representation of the configuration state,
           with automatic line wrapping, using improved multi-line
           representation.
        """
        for section in self._sections:
            filep.write("[%s]\n" % section)
            for (key, value) in self._sections[section].items():
                if key != "__name__":
                    filep.write("%s = %s\n" %
                                (key, str(value).replace('\n', '\n' +
                                 ' ' * self.INDENT_SIZE)))
            filep.write("\n")

    def _interpolate(self, section, option, rawval, vars):
        # special overloading of SafeConfigParser._interpolate:
        # do not attempt to interpolate if the string is (double-)quoted
        if is_quoted(rawval):
            return rawval
        # cannot use 'super' here as ConfigParser is outdated
        return SafeConfigParser._interpolate(self, section, option,
                                             rawval, vars)


class EasyDict(dict):
    """Dictionary whose members can be accessed as instance members
    """

    def __init__(self, dictionary=None, **kwargs):
        if dictionary is not None:
            self.update(dictionary)
        self.update(kwargs)

    def __getattr__(self, name):
        try:
            return self.__getitem__(name)
        except KeyError:
            raise AttributeError("'%s' object has no attribute '%s'" %
                                 (self.__class__.__name__, name))

    def __setattr__(self, name, value):
        self.__setitem__(name, value)

    @classmethod
    def copy(cls, dictionary):

        def _deep_copy(obj):
            if isinstance(obj, list):
                return [_deep_copy(v) for v in obj]
            if isinstance(obj, dict):
                return EasyDict({k: _deep_copy(obj[k]) for k in obj})
            return deepcopy(obj)
        return cls(_deep_copy(dictionary))

    def mirror(self) -> 'EasyDict':
        """Instanciate a mirror EasyDict."""
        return EasyDict({v: k for k, v in self.items()})


class EasyEnum(EasyDict):
    """Enumeration as a dictionary

       :param args: one or more strings from which enumerated values are
                    extracted

       The input string is split on either comma or space characters
    """

    def __init__(self, *args, start=0):
        values = []
        for value in args:
            if ',' in value:
                values.extend([val.strip() for val in value.split(',')])
            else:
                values.extend(value.split())
        super(EasyEnum, self).__init__(
            {val: pos for pos, val in enumerate(values, start=start)})


#pylint: disable-msg=attribute-defined-outside-init

class EasyFloat(float):
    """Real number with explicit string formatter resolution.
    """

    DEFAULT_FORMAT = r'%.3g'

    @property
    def format(self):
        """Return formatter string, if any"""
        return self._fmt if hasattr(self, '_fmt') else self.DEFAULT_FORMAT

    @format.setter
    def format(self, fmt):
        if isinstance(fmt, int):
            self._fmt = '%%.%f' % fmt
        else:
            self._fmt = fmt

    def __repr__(self):
        if not hasattr(self, '_fmt'):
            return self.DEFAULT_FORMAT % self.real
        return self._fmt % self.real

    def __str__(self):
        return repr(self)


# pylint: disable-msg=invalid-name,no-member,no-self-use

FixedArrayT = NewType('FixedArrayT', list)


class FixedArray(list):
    """An array of fixed size and type.

       Items in the array can be modified - as long as they match the array
       type.

       Items neither be removed nor added, as the count of items within the
       array should match the array size.

       :param arg: optional sequence of initial values
    """

    FixedBoundError = IndexError('Out of bound')

    LOCK = Lock()
    VARIANTS = {}

    @classmethod
    def create(cls, type_: Type, size: int) -> FixedArrayT:
        """Create a new FixedArray class that exactly store ``size`` elements
           of specified ``type_`` type.

           :param type_: the type of stored values
           :param size: the count of stored values
        """
        kind = (type_, size)
        with cls.LOCK:
            if kind not in cls.VARIANTS:
                name = ''.join((cls.__name__, '%d' % size, '_',
                                type_.__name__))
                newtype = type(name, (FixedArray, ),
                               {'SIZE': size, 'TYPE': type_})
                cls.VARIANTS[kind] = newtype
        return cls.VARIANTS[kind]

    def __init__(self, arg=None):
        if arg is None:
            arg = [self.TYPE() for _ in range(self.SIZE)]
        else:
            if not isinstance(arg, list):
                raise TypeError('Invalid argument')
            if len(arg) != self.SIZE:
                raise IndexError('Size mismatch')
        super(FixedArray, self).__init__(arg)

    @property
    def size(self):
        return sum([elem.size if hasattr(elem, 'size') else
                    (len(elem) if hasattr(elem, 'len') else 1)
                    for elem in self])

    def __add__(self, _):
        raise IndexError()

    def __iadd__(self, _):
        raise IndexError()

    def __deepcopy__(self, memo):
        items = []
        for item in self:
            item = deepcopy(item, memo)
            items.append(item)
        obj = self.__class__(items)
        return obj

    def __delitem__(self, key):
        raise IndexError()

    def __setitem__(self, key, value):
        if isinstance(key, slice):
            length = len(value)
            left = key.start
            right = key.stop
            # left = key.start or 0
            # right = key.stop or min(self.SIZE, length+1)
            if left is None:
                left = 0
            if left < 0:
                left = len(self)+left
            if right is None:
                right = left+length
            if left+length > self.SIZE:
                raise self.FixedBoundError
            if right < 0:
                right = len(self)+right
            if right-left != length:
                raise IndexError('Size mismatch')
            key = slice(left, right, key.step)
            self._check_value_type(value)
        else:
            if key >= self.SIZE:
                raise self.FixedBoundError
            self._check_value_type([value])
        super(FixedArray, self).__setitem__(key, value)

    def duplicate(self):
        """Create an exact but unrelated copy of this instance."""
        return deepcopy(self)

    def append(self, x):
        raise IndexError()

    def insert(self, i, x):
        raise IndexError()

    def extend(self, iterable):
        raise IndexError()

    def _check_value_type(self, values: Iterable):
        if not self.TYPE:
            return
        for val in values:
            if not isinstance(val, self.TYPE):
                raise TypeError('Value %s not of type %s' %
                                (val, self.TYPE.__name__))

# pylint: enable-msg=invalid-name,no-member,no-self-use


class BitfieldDecoder:
    """Bitfield decoder.

    """

    # pylint: disable-msg=too-few-public-methods

    def __init__(self, decmap):
        self._map = decmap

    @classmethod
    def from_range(cls, bitfield: Mapping[Union[int, Tuple[int, int]],
                                          Tuple[str, Sequence[Any]]]):
        """
            .. code:

                 bitfield = {
                     7: ('bit_name', ('disabled', 'enabled')),
                     (4, 3): ('multi_bit_name', (1, 2, 4, 6)),
                 }

            :param bitfield: a mapping to verify and convert
        """
        decmap = {}
        chunk = 0
        for bits, desc in bitfield.items():
            if isinstance(bits, int):
                bits = (bits, bits)
            elif len(bits) != 2:
                raise ValueError('Invalid bitfield definition: %s' % bits)
            bits = tuple(reversed(sorted(bits)))
            bitcount = 1 + bits[0] - bits[1]
            bitcomb = 1 << bitcount
            if len(desc[1]) != bitcomb:
                raise ValueError('Invalid value count for %s' % desc[0])
            bitchunk = (bitcomb - 1) << bits[1]
            if bitchunk & chunk:
                raise ValueError('Overlapping bits')
            chunk |= bitchunk
            decmap[(bitchunk, bits[1])] = desc
        return cls(decmap)

    @classmethod
    def from_values(cls, valmap):
        decmap = {}
        chunk = 0
        for bitchunk, desc in valmap.items():
            if not isinstance(bitchunk, int) or not bitchunk:
                raise ValueError('Invalid value: %s' % bitchunk)
            bitchars = '{:032b}'.format(bitchunk).lstrip('0')
            roffset = bitchars.rindex('1')
            offset = len(bitchars)-roffset-1
            ones = bitchars[:roffset+1]
            if '0' in ones:
                raise ValueError('Non-consecutive bits: $s' % bitchunk)
            if bitchunk & chunk:
                raise ValueError('Overlapping bits')
            chunk |= bitchunk
            decmap[(bitchunk, offset)] = desc
        return cls(decmap)

    def decode(self, value: int,
               include_all: bool = True) -> Sequence[Tuple[str, Any]]:
        """Decode an integer value with a bitmap mapping.

           :param value: the bitfield value to decode
           :param include_all: if not set, bits that are unset are ignored
           :return: a sequence of decoded (name, values)
        """
        output = []
        for (bits, offset), (name, values) in \
                reversed(sorted(self._map.items())):
            bitval = (value & bits) >> offset
            if include_all or bitval:
                if isinstance(values, bool):
                    is_set = not xor(bool(bitval), values)
                    output.append(name if is_set else '/%s' % name.lower())
                else:
                    output.append((name, values[bitval]))
        return output
