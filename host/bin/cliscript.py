#!/usr/bin/env python3

"""Command line interface scripter
"""

import local
from argparse import ArgumentParser, FileType
from importlib import import_module
from os import getenv
from os.path import basename, splitext
from sys import exit, modules, stderr
from traceback import format_exc
from tde.cmdshell import CmdShellError, CmdShellManager
from tde.log import BareLogger, BareStreamToLogger
from tde.misc import configure_logging

# pylint: disable-msg=broad-except


def main():
    """Main routine"""

    debug = True
    extloggers = {'pyftdi': 'Ftdi'}
    try:
        doc = modules[__name__].__doc__
        if CmdShellManager.VERSION:
            doc = '%s (%s)' % (doc, CmdShellManager.VERSION)
        argparser = ArgumentParser(description=doc)
        argparser.add_argument('-s', '--start', type=FileType('rt'),
                               help='file to execute on startup')
        argparser.add_argument('-c', '--clear', action='store_true',
                               help='clear history of interactive sessions')
        argparser.add_argument('-t', '--threadid', action='store_true',
                               default=False,
                               help='Show thread ID in log')
        argparser.add_argument('-T', '--notime', action='store_true',
                               default=False,
                               help='Omit time in log message (ease diff)')
        argparser.add_argument('-v', '--verbose', action='count', default=0,
                               help='increase verbosity')
        argparser.add_argument('-d', '--debug', action='store_true',
                               help='enable debug mode')
        argparser.add_argument('-l', '--log',
                               help='log output, file or syslog '
                                    '(defaults to stderr)')
        argparser.add_argument('-C', '--nocapture', action='store_true',
                               help='Disable stdout/stderr stream logging')
        argparser.add_argument('-L', '--loggers', action='append',
                               choices=extloggers,
                               help='Add traces from specified logger (avail: '
                                     '%s)' % ', '.join(extloggers))
        args = argparser.parse_args()
        debug = args.debug

        loggers = [BareLogger]
        extra_log_sources = []
        extra_loggers = [logname.lower() for logname in args.loggers or []]
        log_args = {'threadid': args.threadid}
        for modname, logname in extloggers.items():
            if modname not in extra_loggers:
                continue
            try:
                mod = import_module(modname)
                logcls = getattr(mod, '%sLogger' % logname)
            except (AttributeError, ImportError):
                continue
            loggers.append(logcls)
            logger = getattr(logcls, 'log')
            logger_name = getattr(logger, 'name')
            extra_log_sources.append(logger_name)
        log_args['debug' if args.verbose > 3 else 'info'] = extra_log_sources
        log_args['_notime'] = args.notime
        configure_logging(args.verbose, debug, args.log, loggers, **log_args)
        if args.log and not args.nocapture:
            BareStreamToLogger.capture_stdout('.uniclient')
            BareStreamToLogger.capture_stderr('.uniclient')

        csm = CmdShellManager(splitext(basename(__file__))[0], debug)
        csm.set_module_paths(local.extradirs)

        success = True
        if args.start:
            success = csm.load(args.start)
            args.start.close()
        csm.run(args.clear)
        exit(0 if success else 1)
    except Exception as exc:
        if not isinstance(exc, CmdShellError) or not exc.reported:
            print('\nError: %s' % exc, file=stderr)
        if debug:
            print(format_exc(chain=False), file=stderr)
        exit(1)
    except KeyboardInterrupt:
        exit(2)


if __name__ == '__main__':
    main()
