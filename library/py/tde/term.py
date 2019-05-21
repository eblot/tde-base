"""Console helper routines
"""

from os import getenv, isatty, read as readfd
from atexit import register
from sys import platform, stdin, stdout
from time import sleep, time as now
from .misc import EasyDict

#pylint: disable-msg=import-error
#pylint: disable-msg=global-statement
#pylint: disable-msg=invalid-name


if platform == 'win32':
    from msvcrt import getch, kbhit
elif platform in ('darwin', 'linux'):
    from select import select
    from termios import (tcgetattr, tcsetattr, ICANON, ECHO, TCSAFLUSH,
                         TCSANOW, VMIN, VTIME, VINTR, VSUSP)


_STATIC_VARS = EasyDict(init=False, term=stdout.isatty())


def cleanup_console():
    global _STATIC_VARS
    if 'term_config' in _STATIC_VARS:
        fd, old = _STATIC_VARS['term_config']
        tcsetattr(fd, TCSAFLUSH, old)
        _STATIC_VARS.init = False


def _init_term(fullterm):
    """Internal terminal initialization function"""
    if platform == 'win32':
        return True
    elif platform in ('darwin', 'linux'):
        global _STATIC_VARS
        fd = stdin.fileno()
        if not isatty(fd):
            return
        old = tcgetattr(fd)
        _STATIC_VARS.term_config = (fd, old)
        new = tcgetattr(fd)
        new[3] = new[3] & ~ICANON & ~ECHO
        new[6][VMIN] = 1
        new[6][VTIME] = 0
        if fullterm:
            new[6][VINTR] = 0
            new[6][VSUSP] = 0
        tcsetattr(fd, TCSANOW, new)
        # terminal modes have to be restored on exit...
        register(cleanup_console)
        return True
    else:
        return True


def getkey(fullterm=False, timeout=None):
    """Return a key from the current console, in a platform independent way

       :param fullterm: Ctrl+C is not handled as an interrupt signal
       :param timeout: how long to wait for a char (wait forever if None)
    """
    # there's probably a better way to initialize the module without
    # relying onto a singleton pattern. To be fixed
    global _STATIC_VARS
    if not _STATIC_VARS.init:
        _STATIC_VARS.init = _init_term(fullterm)
    if timeout:
        expire = now() + timeout
    else:
        expire = False
    if platform == 'win32':
        while not expire or now() < expire:
            if not kbhit():
                sleep(0.1)
                continue
            inz = getch()
            if inz == '\3' and not fullterm:
                raise KeyboardInterrupt('Ctrl-C break')
            if inz == '\0':
                getch()
            else:
                if inz == '\r':
                    return '\n'
                return inz
    elif platform in ('darwin', 'linux'):
        sinfd = stdin.fileno()
        while not expire or now() < expire:
            ready = select([sinfd], [], [], 0.1)[0]
            if ready:
                inc = readfd(sinfd, 1)
                return inc
    else:
        # unsupported OS, ignore
        sleep(0.25)
    return None


def is_term():
    """Tells whether the current stdout/stderr stream are connected to a
    terminal (vs. a regular file or pipe)"""
    global _STATIC_VARS
    return _STATIC_VARS.term


def is_colorterm():
    """Tells whether the current terminal (if any) support colors escape
    sequences"""
    global _STATIC_VARS
    if 'colorterm' not in _STATIC_VARS:
        terms = ['ansi', 'xterm-color', 'xterm-256color', 'screen']
        _STATIC_VARS.colorterm = _STATIC_VARS.term and \
            getenv('TERM') in terms
    return _STATIC_VARS.colorterm


def get_term_colors():
    """Reports the number of colors supported with the current terminal"""
    term = getenv('TERM')
    if not is_term() or not term:
        return 1
    if term in ('xterm-color', 'ansi', 'screen'):
        return 16
    if term in ('xterm-256color'):
        return 256
    return 1


def charset():
    """Reports the current terminal charset"""
    global _STATIC_VARS
    if 'charset' not in _STATIC_VARS:
        lang = getenv('LC_ALL')
        if not lang:
            lang = getenv('LANG')
        if lang:
            _STATIC_VARS.charset = \
                lang.rsplit('.', 1)[-1].replace('-', '').lower()
        else:
            _STATIC_VARS.charset = ''
    return _STATIC_VARS.charset


CSI = '\x1b['
END = 'm'
BACKGROUND_COLOR = 9
RV_FORMAT = '%s%%2d%%2d%s' % (CSI, END)
FG_FORMAT = '%s38;5;%%d%s' % (CSI, END)
BG_FORMAT = '%s48;5;%%d%s' % (CSI, END)
DF_FORMAT = '%s%02d%s' % (CSI, 40 + BACKGROUND_COLOR, END)


def _make_term_color(fg, bg, bold=False, reverse=False):
    """Emit the ANSI escape string to change the current color"""
    return '%s%02d;%02d;%02d;%02d%s' % \
        (CSI, bold and 1 or 22, reverse and 7 or 27, 30 + fg, 40 + bg, END)


def make_term_color(fg, bg, bold=False, reverse=False):
    """Emit the ANSI escape string to change the current color"""
    rev = RV_FORMAT % (bold and 1 or 22, reverse and 7 or 27)
    fore = FG_FORMAT % fg
    if bg == BACKGROUND_COLOR:
        back = DF_FORMAT
    else:
        back = BG_FORMAT % bg
    return ''.join((rev, fore, back))


def print_progressbar(fmt, current, last, start=0, dot=None, lastfmt=None,
                      maxwidth=0, **kwargs):
    """Give user some feedback with a poor man dotgraph"""
    global _STATIC_VARS
    if not _STATIC_VARS.term:
        return
    if last == start:
        return
    WIDTH = maxwidth or 80
    EMPTYBLOCK = ord(' ')
    width = WIDTH-1-len("%06x:   00%%" % last)
    if start == current:
        level = 0
    else:
        level = width*8*(current-start)
    distance = last-start
    progress = current-start
    if charset() != 'utf8':
        fullblock = ord('.')
        if not dot:
            lastchar = EMPTYBLOCK
        else:
            lastchar = dot == 'E' and 0x2718 or ord(dot)
        if not lastfmt:
            lastfmt = fmt
        level //= distance
    else:
        fullblock = 0x2588  # unicode char
        level //= distance
        sublevel = level % 8
        if not dot:
            lastchar = sublevel and (fullblock+8-sublevel) or EMPTYBLOCK
        else:
            lastchar = dot == 'E' and 0x2718 or ord(dot)
        if not lastfmt:
            lastfmt = '%s \u2714' % fmt
    completion = (100*progress)//distance
    barcount = min(width, level//8)  # deal with rounding
    if current < last:
        barg = u''.join((chr(fullblock)*barcount,
                         chr(lastchar),
                         chr(EMPTYBLOCK)*(width-barcount+1)))
        format_ = u'\r%s\r' % fmt
    else:
        barg = chr(fullblock)*(2+barcount)
        format_ = u'\r%s\r' % lastfmt
    arguments = dict(kwargs)
    arguments.update({'pos': current,
                      'bargraph': barg,
                      'percent': completion})
    output = format_ % arguments
    stdout.write(output)
    stdout.flush()
