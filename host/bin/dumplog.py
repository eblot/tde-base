#!/usr/bin/env python3

"""Parse and enhance off-line log streams
"""

import local
from os import fstat
from sys import exit, modules, stderr, stdin, stdout
from argparse import ArgumentParser, FileType
from traceback import format_exc
from tde.term import is_colorterm
import tde.filterlog


# pylint: disable-msg=broad-except

def enumerate_formatters():
    """Discover the available filterlog formatters"""
    formatters = {}
    for k, v in modules['tde.filterlog'].__dict__.items():
        if k.endswith('Formatter'):
            name = k[:k.rfind('Formatter')].lower()
            if name not in ['base']:
                formatters[name] = v
    return formatters


def main():
    """Main routine"""

    debug = True
    try:
        formatters = enumerate_formatters()
        defformat = 'ansi' if is_colorterm() else 'text'

        parser = ArgumentParser(description=modules[__name__].__doc__)
        parser.add_argument('-f', '--format', choices=list(formatters.keys()),
                            default=defformat,
                            help='output format [%s] (default: %s)' %
                            ('|'.join(list(formatters.keys())), defformat))
        parser.add_argument('-s', '--show', action='store_true',
                            help='Show all supported colors')
        parser.add_argument('-t', '--logtime', action='store_true',
                            help='Index log time on input file creation time')
        parser.add_argument('-i', '--input', type=FileType('rb'),
                            default=stdin,
                            help='input file (default: stdin)')
        parser.add_argument('-o', '--output', type=FileType('wt'),
                            default=stdout,
                            help='output file (default: stdout)')
        parser.add_argument('-d', '--debug', action='store_true',
                            help='enable debug mode')
        args = parser.parse_args()
        debug = args.debug

        with args.output as outfp:
            with args.input as infp:
                btime = -1
                if args.logtime and infp.name != '<stdin>':
                    instat = fstat(infp.fileno())
                    btime = instat.st_ctime
                try:
                    formatter = formatters[args.format](outfp, basetime=btime)
                except ImportError:
                    raise ValueError("No such filter: %s" % args.format)

                if args.show:
                    formatter.show_colors()
                    exit(0)

                formatter.start()
                while True:
                    line = infp.readline()
                    if not line:
                        break
                    try:
                        formatter.inject(line)
                    except Exception:
                        print("line: '%s'" % line)
                        raise
                formatter.stop()
                print('', file=outfp)

    except Exception as exc:
        print('\nError: %s' % exc, file=stderr)
        if debug:
            print(format_exc(chain=False), file=stderr)
        exit(1)
    except KeyboardInterrupt:
        exit(2)


if __name__ == '__main__':
    main()
