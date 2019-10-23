#!/usr/bin/env python3

"""Newt config file parser
"""

from argparse import ArgumentParser
from os.path import isdir
from sys import exit as sysexit, modules, stderr
from traceback import format_exc
import local
from newt.config import NewtConfigParser
from tde.log import BareLogger
from tde.misc import configure_logging, to_int

# pylint: disable-msg=broad-except
# pylint: disable-msg=invalid-name


def main():
    """Main routine"""

    debug = False
    try:
        argparser = ArgumentParser(description=modules[__name__].__doc__)
        argparser.add_argument('dir', nargs='+',
                               help='directory to scan')
        argparser.add_argument('-l', '--log',
                               help='logfile (defaults to stderr)')
        argparser.add_argument('-v', '--verbose', action='count',
                               help='increase verbosity')
        argparser.add_argument('-d', '--debug', action='store_true',
                               help='enable debug mode')
        args = argparser.parse_args()
        debug = args.debug

        configure_logging(args.verbose or 2, debug, args.log, [BareLogger])

        for topdir in args.dir:
            if not isdir(topdir):
                argparser.error(f'No such directory: {topdir}')

        parser = NewtConfigParser(debug)
        for topdir in args.dir:
            parser.scan(topdir)

    except Exception as exc:
        print(f'\nError: {exc}', file=stderr)
        if debug:
            print(format_exc(chain=False), file=stderr)
        sysexit(1)
    except KeyboardInterrupt:
        sysexit(2)


if __name__ == '__main__':
    main()
