"""This module formats the IN/OUT trace messages to ease function call
tracking.
It supports thread highlighting: if a trace starts with {id} where id is a
decimal value representing the thread that prints out the trace, thread
differenciation is done.
"""

from configparser import ConfigParser
from logging import FATAL, ERROR, WARNING, INFO, DEBUG
from os import getenv
from os.path import isfile, join as joinpath
from re import compile as re_compile
from time import localtime, mktime, strftime, time as now
from .filtermime import FilterMime
from .resources import Resources
from .term import get_term_colors

__all__ = ['TextFormatter', 'AnsiFormatter', 'ExtendedAnsiFormatter',
           'XhtmlFormatter']


def get_term_formatter(disable_colors=False):
    """Return the best formatter for the current terminal"""
    if disable_colors:
        return TextFormatter
    colors = get_term_colors()
    for f in [ExtendedAnsiFormatter, AnsiFormatter, TextFormatter]:
        if colors >= f.MAX_COLORS:
            return f
    return None


# --- B A S E   C L A S S --------------------------------------------------

LEVELS = {'C': (1, '[CHAT]  ', DEBUG),
          'D': (2, '[DEBUG] ', DEBUG),
          'I': (3, '[INFO]  ', INFO),
          'W': (4, '[WARN]  ', WARNING),
          'E': (5, '[ERROR] ', ERROR),
          'F': (6, '[FATAL] ', FATAL),
          '>': (0, '> ', DEBUG),
          '<': (0, '< ', DEBUG),
          '.': (6, '[?????] ', DEBUG)}
TIME_RE = r'(?:\^(?P<tick>[0-9a-f]{8})\s)?'
COUNT_RE = r'(?::(?P<count>[0-9a-f]{2})\s)?'
THREAD_RE = r'(?:{(?P<thread>\d{2,})\}\s)?'
LEVEL_RE = r'(?:(?P<level>[' + r''.join(LEVELS.keys()) + r'])\s)?'
FUNC_RE = r'(?:(?P<comp>[\w\d_]+)\[(?P<line>\d+)\]\s(?P<func>[\w\d_]+)\(\))?'
MSG_RE = r'\s*(?P<msg>.*)'
PARTS_RE = (TIME_RE, COUNT_RE, THREAD_RE, LEVEL_RE, FUNC_RE, MSG_RE)
LINE_RE = r''.join(PARTS_RE)+r'$'


class BaseFormatter:
    """
    stacks is a dictionnary keyed on thread id
    each entry is a FIFO of called function
    the youngest pushed element is the last item in the FIFO
    """

    LINECRE = re_compile(LINE_RE)

    def __init__(self, output, outdir=None, basetime=None):
        # Output stream
        self._out = output
        # Thread stacks
        self._stacks = {}
        # Current indentation level
        self._indent = 0
        # Tick period in seconds
        self._period = 0.001
        # when/how to show real time
        self._basetime = basetime
        # Start time on the host
        self._start_time = 0
        # MIME filter
        self._filtermime = FilterMime(outdir)
        # trace counter
        self._last_count = 0
        # trace level hilight
        self._hilight_level = False
        # initialise time
        self._init_time()

    def _stacksize(self, tid):
        """Returns the stack size of any registered thread
        :tid: the thread ID, as a decimal value
        return the number of method stacked into the thread trace stack"""
        if tid is None or tid not in self._stacks:
            return 0
        return len(self._stacks[tid])

    def _stackpush(self, tid, function):
        """Pushes a new method on top of a thread trace stack
        :tid: the thread ID, as a decimal value
        :function: the name of the method, as a string"""
        if tid is None:
            return
        if tid not in self._stacks:
            self._stacks[tid] = list()
        self._stacks[tid].append(function)

    def _stackpop(self, tid):
        """Pops a method from the top of a thread trace stack
        :tid: the thread ID, as a decimal value
        return the name of the method, as a string"""
        if tid is None or tid not in self._stacks or not self._stacks[tid]:
            return ''
        return self._stacks[tid].pop()

    def _stacktop(self, tid):
        """Provides the top element of a thread trace trace
        :tid: the thread ID, as a decimal value
        return the name of the method, as a string"""
        if tid is None or tid not in self._stacks or not self._stacks[tid]:
            return ''
        return self._stacks[tid][-1]

    def _print_line(self, indent, tid, level, stime, string):
        """Emit a formatted line"""
        pass

    def _print_stack_error(self, string, info=None):
        """Emit a stack error message"""
        pass

    def _print_oob(self, string):
        """Print an out of band message"""
        pass

    def _use_raw_mode(self, enable):
        """Enable or disable raw (uncolorized) output"""
        pass

    def set_output(self, out):
        """Set the output stream"""
        self._out = out

    def start(self):
        """Start (initialize) the formatter job"""

    def stop(self):
        """Stop (finalize) the formatter job"""
        pass

    def inject(self, string, logger=None):
        """Inject a string into the formatter"""
        # get rid of carriage return chars
        if not isinstance(string, str):
            string = string.decode('latin-1').strip('\n\r')

        self._use_raw_mode(True)
        injected = self._filtermime.inject(string)
        self._use_raw_mode(False)
        if injected:
            return

        tid = None
        target_time = None
        htime = ''
        lvlnum = 0
        lmo = BaseFormatter.LINECRE.match(string)
        if lmo:
            tick = lmo.group('tick')
            if tick is None:
                # on init, the first trace may be corrupted because of
                # previous traces in various comm line buffers or invalid
                # chars sampled on physical line connection, so try to locate
                # the init string in the received buffer
                pos = string.rfind('^')
                if pos >= 0:
                    trailing = string[pos:]
                    lmo = BaseFormatter.LINECRE.match(trailing)
                    tick = lmo.group('tick')
            if tick:
                tick = int(tick, 16)
                if 0 == tick and 'tick:' in string:
                    self._init_time()
                    # recover the target tick period to compute the proper
                    # clock on the host
                    if string.endswith('us'):
                        try:
                            us = float(string.split(' ')[-2])
                        except ValueError:
                            raise ValueError("Failed to parse tick period")
                        self._period = us/1000000.0
                    elif string.endswith('Hz'):
                        try:
                            hz = int(string.split(' ')[-2])
                        except ValueError:
                            raise ValueError("Failed to parse tick frequency")
                        self._period = 1/hz
                tick_time = self._period*float(tick)
                target_time = self._start_time+tick_time
                ms = (1000*target_time) % 1000
                htime = '%s.%03d' % (strftime('%H:%M:%S',
                                              localtime(target_time)), ms)
            count = lmo.group('count') and int(lmo.group('count'), 16)
            if count is not None:
                if self._last_count != (256-1) and count == 0:
                    # reset @ startup
                    self._print_oob('<restart> %d' % self._last_count)
                    self._stacks.clear()
                else:
                    exp_count = (self._last_count + 1) % 256
                    if count != exp_count:
                        self._print_oob('lost %d messages' % (count-exp_count))
                self._last_count = count
            tid = lmo.group('thread') and int(lmo.group('thread'))
            level = lmo.group('level')
            if level:
                try:
                    lvlnum, lvlstr, lvllog = LEVELS[level]
                except KeyError:
                    lvlnum, lvlstr, lvllog = LEVELS['F']
            else:
                lvlstr = ''
                lvllog = DEBUG
            stid = tid
            if tid is None and level and level in '<>':
                tid = 0
            if all(lmo.group('comp', 'func', 'line')):
                line = lmo.group('line') and int(lmo.group('line'))
                function = '%s::%s' % lmo.group('comp', 'func')
                string = '%s [%d] %s' % \
                    (function, line, lmo.group('msg'))
            else:
                string = lmo.group('msg')
                function = None

            # shifts the text when coming in a method
            if function and level == '>':
                self._stackpush(tid, function)

            # calcs the shift to operate for the trace
            if tid is not None:
                self._indent = 2*(self._stacksize(tid)-1)
            else:
                self._indent = 0

            # shifts back when going out of the method
            if function and level == '<':
                # detects stack empty case (returns from a method without
                # previously entered it)
                if self._stacksize(tid) < 1:
                    self._print_stack_error('underflow in thread %d' % tid)

                stored_function = self._stackpop(tid)

                # detects stack mismatch case (returns from a function which
                # is not the expected one)
                if function != stored_function:
                    self._print_stack_error('thread %d' % tid,
                                            (function, stored_function,
                                             self._stacktop(tid)))
                    # now tries to recover from a corrupted stack
                    # check if the shift is alone
                    if stored_function == self._stacktop(tid):
                        # then get the synchro by removing the supplemental
                        # item in the list
                        self._stackpop(tid)
                    else:
                        # then get the synchro by canceling the latest action
                        self._stackpush(tid, stored_function)

        # print the current line
        self._print_line(self._indent, stid, lvlnum, htime,
                         ' '.join((lvlstr, string)))
        if logger:
            extra = {} if target_time is None else {'timestamp': target_time}
            if stid is not None:
                logger.log(lvllog, '%d %s', stid, string, extra=extra)
            else:
                logger.log(lvllog, '%s', string, extra=extra)

    def _init_time(self):
        # re-initialize the time tracker
        if self._basetime is None:
            self._start_time = now()
        elif self._basetime < 0:
            basetime = list(localtime(now()))
            # clear out HH:MM:SD
            basetime[3] = 0
            basetime[4] = 0
            basetime[5] = 0
            self._start_time = mktime(tuple(basetime))
        else:
            self._start_time = self._basetime


# --- T E X T   O U T P U T -------------------------------------------------

class TextFormatter(BaseFormatter):
    """Default basic formatter
    """

    MAX_COLORS = 1

    def __init__(self, output, *args, **kwargs):
        BaseFormatter.__init__(self, output, *args, **kwargs)
        self._lastid = None

    def _use_raw_mode(self, enable):
        if enable and not self._lastid:
            self._lastid = self.update_color(0)
        elif not enable and self._lastid:
            self.update_color(self._lastid)
            self._lastid = None

    def _print_line(self, indent, tid, level, stime, string):
        space = indent and (' ' * indent) or ''
        if stime:
            self.update_color(0)
            print(stime, end=' ', file=self._out)
        self.update_color(tid, level)
        idstr = tid is not None and '#%02d ' % tid or ''
        print('%s%s%s' % (idstr, space, string), file=self._out)
        self._out.flush()

    def _print_stack_error(self, string, info=None):
        self.update_color(-1)
        print('STACK TRACE ERROR: %s' % string, file=self._out)
        if info:
            (func, expect, next_) = info
            print(' got      %s' % func, file=self._out)
            print(' expected %s' % expect, file=self._out)
            print(' next     %s' % next_, file=self._out)
        self.update_color(0)

    def _print_oob(self, string):
        self.update_color(-1)
        print(string, file=self._out)
        self.update_color(0)

    def start(self):
        self.update_color(0)

    def update_color(self, tid, level=0):
        """Change the output color"""
        return tid

    def show_colors(self):
        """Show supported color, for debug purpose only"""
        print('Color mode is not supported', file=self._out)


# --- A N S I   O U T P U T -------------------------------------------------

class AnsiFormatter(TextFormatter):
    """Formatter for an color ANSI terminal/console"""
    #   Intensity   0    1    2     3     4      5     6     7     9
    #   Normal    Black Red Green Yellow Blue Magenta Cyan White reset
    #   Bright    Black Red Green Yellow Blue Magenta Cyan White

    CSI = '\x1b['
    END = 'm'
    MAX_COLORS = 16
    COLOR_RANGE = 7
    BACKGROUND_COLOR = 9

    def __init__(self, output, *args, **kwargs):
        if get_term_colors() < self.MAX_COLORS:
            raise AssertionError("Not an ANSI terminal")
        TextFormatter.__init__(self, output, *args, **kwargs)
        self._threads = {}
        self._curcode = None
        self._fg = 0
        self._bg = self.BACKGROUND_COLOR
        self._reverse = False
        self._bold = False
        self._reset_term()

    def show_colors(self):
        """Show supported color, for debug purpose only"""
        self._reverse = False
        for c in range(0, self.MAX_COLORS):
            self._reset_term()
            print("Color %3d " % c, end=' ')
            self._fg = c % (self.COLOR_RANGE+1)
            self._bold = (c//(self.COLOR_RANGE+1)) > 0
            self._set_term_color()
            print("Message")
        self._reset_term()

    def stop(self):
        self._reset_term()

    def update_color(self, tid, level=0):
        """Update the terminal color parameters to highlight each thread with
        a different color"""
        oldid = self._curcode
        if tid and tid > 0:
            if tid not in self._threads:
                # threads may share color if there are too many of them.
                key = 1+(len(list(self._threads.keys())) %
                         (2*(self.COLOR_RANGE)))
                self._threads[tid] = (key > self.COLOR_RANGE) and (key+1) \
                    or key
            code = self._threads[tid]
        else:
            code = level
        if code != self._curcode:
            self._reverse = False
            if code is None:
                self._fg = self.COLOR_RANGE
                self._bold = True
            elif code < 0:
                self._fg = -code
                self._bold = False
                self._reverse = True
            elif code == 0:
                self._reset_term()
                self._fg = self.COLOR_RANGE
                self._bold = False
            else:
                self._fg = code % (self.COLOR_RANGE+1)
                self._bold = (code//(self.COLOR_RANGE+1)) == 0
            self._curcode = code
        self._set_term_color()
        return oldid

    def _set_term_color(self):
        """Emit the ANSI escape string to change the current color"""
        self._out.write('%s%02d;%02d;%02d;%02d%s' %
                       (self.CSI,
                        self._bold and 1 or 22,
                        self._reverse and 7 or 27,
                        30 + self._fg,
                        40 + self._bg,
                        self.END))

    def _reset_term(self):
        """Reset the terminal to its initial state"""
        self._fg = self.COLOR_RANGE
        self._bg = self.BACKGROUND_COLOR
        self._reverse = False
        self._bold = False
        self._set_term_color()


class ExtendedAnsiFormatter(TextFormatter):
    """Formatter for 256-color capable terminals"""

    MAX_COLORS = 256
    DEFAULT_COLOR = 256-10
    RV_FORMAT = '%s%%02d%s' % (AnsiFormatter.CSI, AnsiFormatter.END)
    FG_FORMAT = '%s38;5;%%03d%s' % (AnsiFormatter.CSI, AnsiFormatter.END)
    BG_FORMAT = '%s48;5;%%03d%s' % (AnsiFormatter.CSI, AnsiFormatter.END)
    DF_FORMAT = '%s%02d%s' % (AnsiFormatter.CSI,
                              40 + AnsiFormatter.BACKGROUND_COLOR,
                              AnsiFormatter.END)

    def __init__(self, output, *args, **kwargs):
        if output.name == '<stdout>' and get_term_colors() < 256:
            raise AssertionError("Terminal does not support 256 color mode")
        TextFormatter.__init__(self, output, *args, **kwargs)
        self._init_colors()
        self._threads = {}
        self._curcode = None
        self._fg = 0
        self._bg = AnsiFormatter.BACKGROUND_COLOR
        self._reverse = False
        self._reset_term()

    def _init_colors(self):
        self._colors = [7]
        color_files = [joinpath(getenv('HOME'), '.pylogtermrc'),
                       joinpath(Resources.get_etc(), 'tools', 'pylogterm.rc')]
        for color_file in color_files:
            if isfile(color_file):
                cfg = ConfigParser()
                with open(color_file) as cfp:
                    cfg.readfp(cfp)
                section = self.__class__.__name__[:-9].lower()
                if cfg.has_option(section, 'colors'):
                    colorstr = cfg.get(section, 'colors')
                    try:
                        colors = [int(c.strip()) for c in colorstr.split(',')]
                        self._colors = colors
                    except Exception as ex:
                        print('Invalid color definition: %s', str(ex))
                break

    @staticmethod
    def lfsr_7(lfsr):
        bit = ((lfsr >> 0) ^ (lfsr >> 1)) & 1
        lfsr = (lfsr >> 1) | (bit << 2)
        return lfsr

    def _set_term_color(self):
        """Emit the ANSI escape string to change the current color"""
        rev = self.RV_FORMAT % (self._reverse and 7 or 27)
        fg = self.FG_FORMAT % self._fg
        if self._bg == AnsiFormatter.BACKGROUND_COLOR:
            bg = self.DF_FORMAT
        else:
            bg = self.BG_FORMAT % self._bg
        # print("TC %s %s %s" % (self._reverse, self._fg, self._bg))
        esc_cmd = ''.join((rev, fg, bg))
        # print("ESC:", esc_cmd.replace('\x1b', '^'))
        self._out.write(esc_cmd)

    def _reset_term(self):
        """Reset the terminal to its initial state"""
        self._fg = self.DEFAULT_COLOR
        self._bg = AnsiFormatter.BACKGROUND_COLOR
        self._reverse = False
        self._bold = False
        self._set_term_color()

    def update_color(self, tid, level=0):
        """Update the terminal color parameters to highlight each thread with
        a different color"""
        oldid = self._curcode
        if tid or level == 0:
            if tid is not None and tid >= 0:
                if tid not in self._threads:
                    # threads may share color if there are too many of them.
                    key = len(self._threads) % len(self._colors)
                    self._threads[tid] = self._colors[key % len(self._colors)]
                code = self._threads[tid]
            else:
                code = tid
        else:
            code = self._colors[level % len(self._colors)]
        if code != self._curcode:
            self._reverse = False
            if code is None:
                self._fg = self.DEFAULT_COLOR
            elif code < 0:
                self._fg = -code
                self._reverse = True
            elif code == 0:
                self._reset_term()
                self._fg = self.DEFAULT_COLOR
            else:
                self._fg = code
            self._curcode = code
        self._set_term_color()
        return oldid

    def show_colors(self):
        """Show supported color, for debug purpose only"""
        self._reverse = False
        for c in range(len(self._colors)):
            self._reset_term()
            self._fg = self._colors[c]
            print("Color %3d " % self._fg, end=' ')
            self._set_term_color()
            print("Message")
        self._reset_term()


# --- X H T M L   O U T P U T -----------------------------------------------

class XhtmlFormatter(BaseFormatter):
    """Formatter that output XHTML-compliant stream"""
    COLORS = ['black', 'red', 'green', '#e0a030', 'blue', 'magenta', 'cyan',
              '#211']

    def __init__(self, output, *args, **kwargs):
        BaseFormatter.__init__(self, output, *args, **kwargs)
        self._threads = {}

    def start(self):
        self._print_header()

    def stop(self):
        self._print_footer()

    @staticmethod
    def escape(s):
        """Escape special XHTML characters"""
        return s.replace('&',
                         '&amp;').replace('<',
                                          '&lt;').replace('>', '&gt;')

    def _print_line(self, indent, tid, level, stime, string):
        """Print out a single line, using XHTML markup
        :string: the string to print out"""
        print('<tr>', end=' ', file=self._out)
        if stime:
            print('<th class="time">%s</th>' % stime, end=' ', file=self._out)
        space = indent and ('&nbsp;' * indent) or ''
        if tid and tid > 0 and tid not in self._threads:
            # threads may share color if there are too many of them.
            self._threads[tid] = (1 + len(list(self._threads.keys()))) % \
                                    (len(self.COLORS)-1)
        fg = ''
        bg = None
        if tid is None:
            fg = self.COLORS[-1]
        elif tid < 0:
            fg = bg
            bg = self.COLORS[-id]
        elif tid == 0:
            fg = self.COLORS[-1]
        else:
            fg = self.COLORS[self._threads[tid]]
        string = '%s%s' % (space, self.escape(string))
        print('<td><span style="color: %s;' % fg, end=' ', file=self._out)
        if bg:
            print('background-color: %s' % bg, end=' ', file=self._out)
        print('">%s</span></td></tr>' % string, file=self._out)

    def _print_stack_error(self, string, info=None):
        s = self.escape(string)
        print('''</table>
           <div class="error">
           <ul><li>Stack trace Error: %s</li></ul>''' % s, file=self._out)

        if info:
            print('''<div class="stack">
               <table>
                 <tr><th>received</th><td>%s</td></tr>
                 <tr><th>expected</th><td>%s</td></tr>
                 <tr><th>next</th><td>%d</td></tr>
               </table>
             </div>''' % info, file=self._out)

        print('''</div>
            <table class="code">''', file=self._out)

    def _print_oob(self, string):
        s = self.escape(string)
        print('''</table>
           <div class="oob">
           <ul><li>%s</li></ul>''' % s, file=self._out)
        print('''</div>
            <table class="code">''', file=self._out)

    def _print_header(self):
        """Generate a XHTML 1.0 header"""
        print(r"""
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
         "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml">
         <head>
          <title></title>
          <style type="text/css">
          .code {
           background: #f7f7f7;
           border: 1px solid #d7d7d7;
           margin: 1em 1.75em;
           padding: .25em;
           overflow: auto
          }
          table.code {
           border: 1px solid #ddd;
           border-spacing: 0;
           border-top: 0;
           empty-cells: show;
           font-size: 12px;
           line-height: 130%;
           padding: 0;
           margin: 0 auto;
           table-layout: fixed;
           width: 100%;
          }
          table.code td {
           font: normal 11px monospace;
           overflow: hidden;
           padding: 1px 2px;
           vertical-align: top;
          }
          table.code th.time {
           color: grey;
          }
          .code span {
           font-family: monospace;
          }
          .stack table {
           background-color: #c00;
           width: 100%;
           font-family: monospace;
          }
          .stack th {
           text-align: left;
           width: 10ex;
          }
          </style>
         </head>
         <body>
          <div>
           <table class="code">
        """, file=self._out)

    def _print_footer(self):
        """Generate a XHTML 1.0 footer"""
        print(r"""
           </table>
          </div>
         </body>
        </html>
        """, file=self._out)
