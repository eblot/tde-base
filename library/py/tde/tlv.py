"""A module to create and parse TLV binary sequences"""

import copy
import re
import struct
import sys
from binascii import hexlify, unhexlify
from io import StringIO
from .misc import to_int, to_bool, EasyConfigParser
from numbers import Integral
from string import Template
from textwrap import TextWrapper


__all__ = ['TlvContainer', 'TlvFormatter']


class TlvError(AssertionError):
    """Base class for TLV errors"""


class TlvValueError(ValueError, TlvError):
    """Value error in TLV"""


class TlvItem:
    "TLV item"

    def __init__(self, container, pos):
        """Construct a new TLV item"""
        self._container = container
        self._pos = pos

    def __getitem__(self, key):
        """Retrieve a property of the TLV item"""
        tag, value = self._container[self._pos]
        if key == 'tag':
            return tag
        elif key == 'length':
            return len(value)
        elif key == 'value':
            return value
        else:
            raise KeyError("No such key")

    def __setitem__(self, key, value):
        """Change a property of the TLV item"""
        if key != 'value':
            raise KeyError("No such key")
        self._container[self._pos] = value

    def __len__(self):
        return len(self._container[self._pos][1])

    @property
    def tag(self):
        return self._container[self._pos][0]

    @property
    def value(self):
        return self._container[self._pos][1]

    def __repr__(self):
        """Return a string representation of the TLV item"""
        tag, value = self._container[self._pos]

        def pretty_repr(value):
            """Create a pretty ASCII representation of the value"""
            if isinstance(value, str):
                for v in value:
                    if (ord(v) < 0x30) or (ord(v) > 0x7F):
                        return ','.join(['x%02x' % ord(x) for x in value])
            else:
                print(type(value))
            return value
        if (tag >= 0x30) and (tag <= 0x7f):
            tag = chr(tag)
        return "<%r = %r>" % (tag, pretty_repr(value))


class TlvContainer:
    """Simple TLV sequence container and manipulator"""

    NUMBERS = 'BHI'
    LSIZES = {}
    for k in NUMBERS:
        LSIZES[struct.calcsize('=%c' % k)] = k

    def __init__(self, tsize=1, lsize=1, asize=1, bigendian=False, magic=None):
        """Create a new TLV container"""
        for value in (tsize, lsize, asize):
            if value not in TlvContainer.LSIZES:
                raise TlvValueError("Unsupported TLV size: %s" % value)
        self.tsize = tsize
        self.lsize = lsize
        self.talign = asize
        self.endian = bigendian and '>' or '<'
        if isinstance(magic, str):
            self.magic = bytes(magic, encoding='utf8')
        else:
            self.magic = magic
        self._sequence = []

    def __getitem__(self, index):
        """Retrieve an indexed (tag, value) pair"""
        return copy.deepcopy(self._sequence[index])

    def __setitem__(self, index, value):
        """Update an indexed (tag, value) pair. It should already exist"""
        if index >= len(self._sequence):
            raise KeyError('Invalid position')
        _, value = self._format(value=value)
        self._sequence[index] = (self._sequence[index][0], value)

    @property
    def max_payload_size(self):
        """Report the maximum size of an item payload"""
        size = 1 << (8 * self.lsize)
        return size-1

    def set_magic(self, magic=None):
        """Define (or cancel) a magic header"""
        if isinstance(magic, bytes):
            if len(magic) != 4:
                raise TlvValueError('Invalid magic size')
            self.magic = magic
        elif isinstance(magic, str):
            if len(magic) != 4:
                raise TlvValueError('Invalid magic size')
            self.magic = bytes(magic, encoding='utf8')
        elif isinstance(magic, int):
            self.magic = struct.pack("%cI" % self.endian, magic)
        elif magic is None:
            self.magic = None
        else:
            raise TypeError('Magic type not supported "%s"' % magic)

    def get_magic(self):
        """Retrieve the magic header, if any"""
        if not self.magic:
            return None
        try:
            bytes_ = struct.unpack("%c4B" % self.endian, self.magic)
            for b in bytes_:
                if (b < 0x30) or (b > 0x7F):
                    (magic, ) = struct.unpack("%cI" % self.endian, self.magic)
                    return magic
            return self.magic
        except Exception as e:
            print(e, file=sys.stderr)

    def __iter__(self):
        """Create a container iterator that provides TLV items
           Iterator is currently only designed for internal use
        """
        class TlvContainterIter:
            "Simple TLV container iterator"

            def __init__(self, container):
                """Instanciate the iterator"""
                self._container = container
                self._pos = 0

            def __next__(self):
                """Provide the iterated TLV item"""
                if self._pos >= len(self._container._sequence):
                    raise StopIteration
                item = TlvItem(self._container, self._pos)
                self._pos += 1
                return item
        return TlvContainterIter(self)

    def add_item(self, tag, length=0, value=None):
        """Add a new TLV item to the container tail"""
        if isinstance(tag, bytes) or isinstance(tag, str):
            if len(tag) > self.tsize:
                raise TlvValueError("Invalid tag size: %d / %d" %
                                    (len(tag), self.tsize))
            if isinstance(tag, str):
                tag = bytes(tag, encoding='utf8')
            tag = tag + b'\x00' * self.tsize
            tag, = struct.unpack('%c%c' % (self.endian,
                                           TlvContainer.LSIZES[self.tsize]),
                                 tag[:self.tsize])
        elif isinstance(tag, int):
            if (tag < 0) or (tag >= (1 << (8 * self.lsize))):
                raise TlvValueError("Invalid tag value")
        else:
            raise TypeError("Invalid tag type %s for %s" % (type(tag), tag))
        if not isinstance(length, int):
            raise TypeError("Invalid length type")
        length, value = self._format(length, value)
        self._sequence.append((tag, value))

    def update(self, tag, length=0, value=None, match=None, single=True):
        """Update an existing TLV item with a new value"""
        changed = False
        for item in self:
            if isinstance(tag, str) and len(tag) == 1:
                tag = ord(tag)
            if item['tag'] == tag:
                if match:
                    if item['value'] != match:
                        continue
                item['value'] = value
                changed = True
                if single:
                    break
        return changed

    def load(self, inf, have_magic=False, end_tag=None, dump=False):
        """Load (deserialize) the TLV container from a binary file"""
        if not have_magic:
            self.magic = None
        self._sequence = []
        if have_magic:
            magic = inf.read(4)
            if self.magic is None:
                self.set_magic(magic)
            elif self.magic != magic:
                raise TlvError('Magic mismatch, cannot load')
        tlformat = '%c%c%c' % (self.endian,
                               TlvContainer.LSIZES[self.tsize],
                               TlvContainer.LSIZES[self.lsize])
        if dump:
            from .misc import hexline
        try:
            while True:
                tlsize = self.tsize+self.lsize
                tl = inf.read(tlsize)
                if tlsize != len(tl):
                    if len(tl) == 0 and end_tag is None:
                        break
                    raise TlvError('Cannot read %d bytes from stream: %d' %
                                   (tlsize, len(tl)))
                if dump:
                    print("TL: %s" % hexline(tl), end=' ')
                tag, length = struct.unpack(tlformat, tl)
                if length > 0:
                    value = inf.read(length)
                if end_tag is not None and tag == end_tag:
                    break
                padlen = (self.talign - inf.tell()) & (self.talign - 1)
                inf.read(padlen)
                if length:
                    if dump:
                        print("V: %s" % hexline(value))
                    self.add_item(tag, length, value)
        except OverflowError as e:
            raise TlvError('Invalid TLV content: %s' % str(e))
        if dump:
            print("")

    def save(self, outf, end_tag=None):
        """Save (serialize) the TLV container into a binary file"""
        if self.magic:
            outf.write(self.magic)
        tlformat = '%c%c%c' % (self.endian,
                               TlvContainer.LSIZES[self.tsize],
                               TlvContainer.LSIZES[self.lsize])
        for item in self:
            tag = item['tag']
            value = item['value']
            length = len(value)
            outf.write(struct.pack(tlformat, tag, length))
            outf.write(value)
            padlen = (self.talign - outf.tell()) & (self.talign - 1)
            outf.write(b'\x00' * padlen)
        if end_tag is not None:
            outf.write(struct.pack(tlformat, end_tag, 0))

    def _format(self, length=0, value=None):
        """Validate and format a TLV (length, value) pair"""
        if length == 0 and value is not None:
            length = len(value)
        if (length < 0) or (length >= (1 << (8 * self.lsize))):
            raise TlvValueError("Invalid length value")
        if isinstance(value, bytes):
            if len(value) != length:
                raise TlvValueError("Invalid value size")
        elif isinstance(value, str):
            if len(value) != length:
                raise TlvValueError("Invalid value size")
            value = bytes(value, encoding='utf8')
        elif isinstance(value, Integral):
            value = struct.pack('%c%c' %
                (self.endian, TlvContainer.LSIZES[length]), value)
        else:
            raise TypeError("Unsupported value type %s for %s" %
                            (type(value), value))
        return (length, value)


class TlvTemplate:
    """TLV template for generating or parsing TLV sequence"""

    CODES = {'byte'  : 'B',  # byte, 8 bits
             'half'  : 'H',  # half-word, 16 bits
             'word'  : 'I',  # word, 32 bits
             'bool'  : '?',  # bool, 8 bits
             'string': 's',  # string, not-zero terminated
             'array' : 's',  # byte sequence
            }

    def __init__(self):
        self._parser = EasyConfigParser()
        self._tags = {}
        self._mandatorytags = []
        self._order = []
        self._magic = None
        self._endmarker = None
        self._bigendian = False
        self._formats = {}

    @staticmethod
    def sizeof(stype):
        """Returns the size, in bytes, of a type"""
        return struct.calcsize('=%c' % stype)

    def _get_formats(self, names):
        """Returns a dictionary of name formats"""
        formats = {}
        for n in names:
            format_ = self._parser.get('config', '%csize' % n[0], 'byte')
            if (format_ not in self.CODES) or \
               (self.CODES[format_] not in TlvContainer.NUMBERS):
                raise TlvError('Invalid %s format: %s' % (n, format_))
            formats[n] = self.CODES[format_]
        return formats

    def load(self, template):
        """Load the template definition from an INI file"""
        if not self._parser.read(template):
            raise TlvError('Unable to parse template file "%s"' % template)
        # verify that mandatory sections exist within the file
        for section in ('config', 'format'):
            if not self._parser.has_section(section):
                raise TlvError('Missing section "%s"' % section)

        # retrieve the endianess
        self._bigendian = to_bool(self._parser.get('config', 'bigendian',
                                                   'no'))
        # load optional order list
        order = self._parser.get('config', 'order')
        self._order = order and order.split(',') or []
        # load optional magic marker
        self._magic = bytes(self._parser.get('config', 'magic'),
                            encoding='utf8')
        # load whether end marker is required
        endmarker = self._parser.get('config', 'end', None)
        if endmarker is not None:
            self._endmarker = to_int(endmarker)

        # retrieve the format definitions
        self._formats = self._get_formats(('tag', 'length', 'alignment'))

        # compute the format RE
        taglen = self.tag_size
        types = r'|'.join(list(self.CODES.keys()))
        tsre = r'(?P<ts>[\w]{1,%d})' % taglen
        thre = r'(?P<th>0x[A-Fa-f0-9]{1,%d})' % (2*taglen)
        tdre = r'(?P<td>\d{1,%d})' % (2*taglen)
        fmtre = r'^(?:' + r'|'.join((tsre, thre, tdre)) + '):(' + types + \
                r')(?:\[(\d+)\])?([\?\!\+\*\~]?)$'
        fmtcre = re.compile(fmtre)

        # parse the format section (description of each tag property)
        for tagname in self._parser.options('format'):
            format_ = self._parser.get('format', tagname)
            # use a RE to split the tag description into its token
            mo = fmtcre.match(format_)
            if not mo:
                raise TlvError('Invalid format "%s" for tag "%s"' %
                               (format_, tagname))
            (type_, repeat, prop) = mo.group(4, 5, 6)
            # ignore this type of entries
            if prop == '~':
                continue
            # extract the tag and convert the format
            (ts, th, td) = (x and bytes(x, encoding='utf8') or None for x in
                                mo.group('ts', 'th', 'td'))
            tag = ts or to_int(th is not None and th or td)
            # detect override
            if tag in [v[0] for v in self._tags.values()]:
                raise TlvError('Tag "%s" redefined for "%s"' %
                               (tag, tagname))
            # if the tag does not have a property, consider it as mandatory
            if not prop:
                prop = '!'
            # build up the mandatory tag list
            if prop not in '?*':
                self._mandatorytags.append(tagname)
            # dictionnary of all possible tags
            self._tags[tagname] = (tag, type_, repeat or '')

    @property
    def magic(self):
        return self._magic

    @property
    def order(self):
        return list(self._order)

    @property
    def endmarker(self):
        return self._endmarker

    @property
    def tags(self):
        return dict(self._tags)

    @property
    def mandatorytags(self):
        return list(self._mandatorytags)

    @property
    def bigendian(self):
        return self._bigendian

    @property
    def tag_size(self):
        return TlvTemplate.sizeof(self._formats['tag'])

    @property
    def length_size(self):
        return TlvTemplate.sizeof(self._formats['length'])

    @property
    def alignment_size(self):
        return TlvTemplate.sizeof(self._formats['alignment'])

    @property
    def tag_code(self):
        return self._code(self.tag_size)

    @property
    def length_code(self):
        return self._code(self.length_size)

    def _code(self, size):
        try:
            return {1: 'B', 2: 'H', 4: 'I'}[size]
        except KeyError:
            raise TlvValueError('Invalid size')


class TlvFormatter:
    """TLV formatter: apply values defined in a configuration file
       to a TLV template file and emit the result as a binary TLV file"""

    PVCRE = re.compile(r'^\$\((.*)\)$')

    def __init__(self, template, ignore=False, subset=False):
        if not isinstance(template, TlvTemplate):
            raise TlvError('API changed, expect a TlvTemplate instance')
        self._template = template
        # whether to accept value that are not defined within the template
        # and to warn about or not
        self._ignore = (ignore and 1 or 0) + (subset and 2 or 0)
        self._tlv = None

    @property
    def tlv(self):
        """returns the tlv container"""
        return self._tlv

    def save(self, outfp):
        """Dump the TLV sequence into the output stream"""
        self._tlv.save(outfp, self._template.endmarker)

    def build(self, valfp, bracket_values=None, parenthesis_values=None):
        """Build the TLV sequence from an INI stream"""
        parser = EasyConfigParser()
        # use the input stream as an INI configuration source
        parser.readfp(valfp)
        # verify that mandatory sections exist within the file
        if not parser.has_section('values'):
            raise TlvError('Missing section "values"')
        values = {k: v for k, v in parser.items('values')}
        self.generate(values, bracket_values, parenthesis_values)

    def generate(self, values, bracket_values=None, parenthesis_values=None):
        """Build the TLV sequence from the dictionary"""
        if bracket_values is None:
            bracket_values = dict()
        if parenthesis_values is None:
            parenthesis_values = dict()
        tags = list(values.keys())
        order = self._template.order
        if order:
            # if an order is specified, reorder the tag list to emit the TLV
            # within the defined order
            for o in reversed([o.strip() for o in order]):
                if o in tags:
                    tags.remove(o)
                    tags.insert(0, o)
        else:
            # else use natural order to ease read back
            tags.sort()

        # instanciate the TLV container
        self._tlv = TlvContainer(self._template.tag_size,
                                 self._template.length_size,
                                 self._template.alignment_size,
                                 self._template.bigendian)

        # emit prolog (magic word) if any
        if self._template.magic is not None:
            self._tlv.set_magic(self._template.magic)

        # retrieve tags
        alltags = self._template.tags
        mandatorytags = self._template.mandatorytags

        # now process the list of TLV to emit
        lensize = self._template.length_size
        for tagname in tags:
            # tag without a defined format
            if tagname not in alltags:
                if self._ignore > 1:
                    continue
                msg = 'no format for entry "%s"' % tagname
                if self._ignore:
                    print('Warning: %s' % msg, file=sys.stderr)
                    continue
                else:
                    raise TlvError(msg)
            # get the raw tag value
            value = values[tagname]
            # replace any parametric value $(...) with its actual value
            mo = self.PVCRE.match(value)
            if mo:
                if mo.group(1) not in parenthesis_values:
                    raise TlvError("Value '%s' has no parameter" % value)
                value = parenthesis_values[mo.group(1)]
            # replace any parametric value ${...} with its actual value
            try:
                value = Template(value).substitute(**bracket_values)
            except KeyError:
                raise TlvError("Value '%s' has no parameter" % value)
            except TlvValueError:
                raise TlvError("Invalid value '%s' for '%s'" %
                               (value, tagname))
            # if the tag is mandatory, update the mandatory tag list
            if tagname in mandatorytags:
                mandatorytags.remove(tagname)

            tag, length, data = \
                TlvFormatter.format_tlv(tagname, value, alltags,
                    lensize, self._tlv.max_payload_size)
            self._tlv.add_item(tag, length, data)

        # if the mandatory tag list is not empty, some tags have been missing
        if mandatorytags:
            raise TlvError('Missing mandatory tags: %s' %
                ', '.join(mandatorytags))

    @staticmethod
    def format_tlv(tagname, value, alltags, lensize, max_payload_size):
        """prepare parameters for update/add_item according to the template
           from a tagname/value pair
        """
        # retrieve the tag properties
        (tag, type_, repeat) = alltags[tagname]
        valcode = TlvTemplate.CODES[type_]
        repcount = int(repeat or 1)
        # tag references an integer, parse the integer value
        if valcode in TlvContainer.NUMBERS:
            try:
                if repcount > 1:
                    value = [to_int(val) for val in
                                re.split(r'[\s:]', value)]
                else:
                    value = [to_int(value)]
            except TlvValueError:
                raise TlvError('Invalid integer value: %s' % value)
        # tag references a boolean, parse it and update the format
        # to emit a byte (shortest value width in the TLV)
        elif type_ == 'bool':
            if repcount > 1:
                value = [to_bool(val) for val in value.split(' ')]
            else:
                value = [to_bool(value)]
            valcode = valcode.upper()
        elif type_ == 'string':
            repcount = repeat = len(value)
            if (repcount >= max_payload_size-lensize):
                raise TlvError('String "%s" too long' % value)
            value = [bytes(value, encoding='utf8')]
        elif type_ == 'array':
            if value.startswith('0x'):
                value = value[2:]
            value = ''.join([v for v in value if v not in '\n\r '])
            if len(value) % 2:
                raise TlvError('Array "%s" is not a valid byte '
                                'sequence' % tagname)
            value = unhexlify(value)
            repeat = len(value)
            if (repcount > 1) and (repeat != repcount):
                raise TlvError('Array "%s" length is not the '
                                'expected one: %d/%d' %
                                (tagname, repcount, repeat))
            else:
                repcount = repeat
            if (repcount >= max_payload_size - lensize):
                raise TlvError('Array "%s" too long' % tagname)
            value = [value]
        else:
            raise TlvError('Support for type "%s" not implemented' % type_)

        length = struct.calcsize('<%s' % valcode) * repcount
        structfmt = '<%s%s' % (repeat, valcode)
        try:
            data = struct.pack(structfmt, *value)
        except struct.error:
            raise TlvError("Value for '%s' does not match "
                            "the specified template" % tagname)
        return tag, length, data


class TlvPrinter:
    """Pretty formatter for a TLV sequence"""

    INDENT_SIZE = 8

    def __init__(self, template):
        tagmap = {}
        tags = template.tags
        for name in tags:
            tag, type_, repeat = tags[name]
            repeat = repeat and to_int(repeat) or 1
            tagmap[tag] = (name, type_, repeat)
        self._tagmap = tagmap
        self._endian = template.bigendian and '>' or '<'
        self._tagcode = template.tag_code
        self._tagsize = template.tag_size

    def decode(self, item):
        tag, = struct.unpack('%ds' % self._tagsize,
                             struct.pack(self._tagcode, item.tag))
        name, format, repeat = self._tagmap.get(tag, ("'%s'" % tag, '', 0))
        try:
            code = TlvTemplate.CODES[format]
            if format == 'string':
                repeat = len(item)
            fmt = '%c%d%c' % (self._endian, repeat, code)
            values = struct.unpack(fmt, item.value)
        except (struct.error, TlvValueError, KeyError) as e:
            return (name, None, 0)
        if len(values) == 1:
            return (name, format, values[0])
        else:
            return (name, format, values)

    def get_as_dict(self, tlv, decode_map=None):
        def _strhexlify(data):
            return str(hexlify(data), encoding='ascii')
        typemap = {'bool': lambda x: x and 'enabled' or 'disabled',
                   'array': _strhexlify, }
        namemap = {}
        if decode_map is not None:
            namemap.update(decode_map)
        values = {}
        for item in tlv:
            name, format, value = self.decode(item)
            if format is None:
                pass
            elif name in namemap:
                value = namemap[name](value)
            elif format in typemap:
                value = typemap[format](value)
            if isinstance(value, int):
                value = hex(value)
            values[name] = value
        return values

    def show(self, tlv, decode_map=None, wmax=76, matchdict=None):
        tlvstr = StringIO()
        error = self.format(tlvstr, tlv, decode_map, wmax, matchdict)
        print(tlvstr.getvalue())
        return error

    def format(self, tlvstr, tlv, decode_map=None, wmax=76, matchdict=None):
        typemap = {'bool': lambda x: x and 'enabled' or 'disabled',
                   'array': hexlify, }
        namemap = {}
        if decode_map is not None:
            namemap.update(decode_map)
        error = False
        if matchdict is None:
            matchdict = {}
        for item in tlv:
            name, format, value = self.decode(item)
            if format is None:
                error = True
                print("  %-12s:" % name, '<decoding error>', file=tlvstr)
                continue
            if name in namemap:
                value = namemap[name](value)
            elif format in typemap:
                value = typemap[format](value)
            # matchdict may take three values:
            # True (match), False (mismatch), None (not tested)
            refvalue = matchdict.get(name, None)
            if refvalue is True:
                name = '%s (verified)' % name
            elif refvalue is False:
                name = '%s (invalid)' % name
            if isinstance(value, int):
                value = hex(value)
            if isinstance(value, list):
                firstline, lines = value[0], value[1:]
                print("  %-12s:" % name, firstline, file=tlvstr)
                for line in lines:
                    print(" " * 15, line, file=tlvstr)
            else:
                if isinstance(value, bytes):
                    value = str(value, encoding='utf8')
                elif isinstance(value, bytearray):
                    value = value.decode('utf8')
                if len(value) > wmax:
                    skip = len(name) + 2 + 2 - self.INDENT_SIZE
                    tw = TextWrapper(width=wmax)
                    pad = ''.join(('\n', ' ' * self.INDENT_SIZE))
                    value = tw.fill(''.join((' ' * skip, value)))[skip:]
                    value = value.replace('\n', pad)
                print("  %-12s:" % name, value, file=tlvstr)
        return error
