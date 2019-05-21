#!/usr/bin/env python3

"""STM32L011 UART firmware flasher
"""

import local
from argparse import ArgumentParser, FileType
from logging import getLogger
from hashlib import sha256
from sys import exit, modules, stderr
from traceback import format_exc
from tde.log import BareLogger
from tde.misc import configure_logging, to_int
from tde.recfmt import IHexFastParser as IHexParser, SRecParser
from stm32l01.flasher import StmFlasher

# pylint: disable-msg=broad-except


def main():
    """Main routine"""

    debug = True
    try:
        argparser = ArgumentParser(description=modules[__name__].__doc__)
        argparser.add_argument('-p', '--device', required=True,
                               help='serial port device name')
        argparser.add_argument('-s', '--srec', type=FileType('rt'),
                               help='path to a SREC firwmare file')
        argparser.add_argument('-i', '--ihex', type=FileType('rt'),
                               help='path to a iHex firware file')
        argparser.add_argument('-e', '--erase', action='store_true',
                               help='erase the flash firmware')
        argparser.add_argument('-E', '--clear', action='store_true',
                               help='clear out the EEPROM configuration')
        argparser.add_argument('-c', '--check', action='store_true',
                               help='verify if flash content matches FW file')
        argparser.add_argument('-u', '--update', action='store_true',
                               help='update flash content with FW file')
        argparser.add_argument('-x', '--execute', action='store_true',
                               help='execute application from flash')
        argparser.add_argument('-b', '--baudrate',
                               help='listen for app trace @ baudrate')
        argparser.add_argument('-l', '--log',
                               help='logfile (defaults to stderr)')
        argparser.add_argument('-v', '--verbose', action='count',
                               help='increase verbosity')
        argparser.add_argument('-d', '--debug', action='store_true',
                               help='enable debug mode')
        args = argparser.parse_args()
        debug = args.debug

        configure_logging(args.verbose or 2, debug, args.log, [BareLogger])

        if all((args.srec, args.ihex)):
            argparser.error('SREC and iHex option switches are mutually '
                            'exclusive')
        log = getLogger('tde.vowflash')

        if args.srec:
            parser = SRecParser(args.srec)
            parser.parse()
        elif args.ihex:
            parser = IHexParser(args.ihex)
            parser.parse()
        else:
            parser = None

        flasher = StmFlasher()
        flasher.open(args.device)
        flasher.boot(True)
        flasher.connect()
        flasher.configure()
        flasher.identify()

        if args.erase or args.update:
            if parser:
                for segment in parser.get_data_segments():
                    flasher.erase(segment.baseaddr, segment.size)
            else:
                flasher.erase(flasher.FLASH_ADDRESS, flasher.flash_size)

        if args.clear:
            # for now, erase a single page, not the whole EEPROM
            flasher.write(flasher.EEPROM_ADDRESS, [0] * flasher.PAGE_SIZE)

        baudrate = args.baudrate and to_int(args.baudrate)

        if not parser:
            if args.execute:
                flasher.boot(False, baudrate=baudrate)
                flasher.listen()
            return

        if args.update:
            for segment in parser.get_data_segments():
                flasher.write(segment.baseaddr, segment.data)
        if args.check:
            for segment in parser.get_data_segments():
                ref = sha256()
                ref.update(segment.data)
                remote = sha256()
                remote.update(flasher.read(segment.baseaddr, segment.size))
                if ref.digest() != remote.digest():
                    raise ValueError('Content mismatch')
                log.info('Flash contents match file')
        if args.execute:
            flasher.boot(False, baudrate=baudrate)
            flasher.listen()


    except Exception as exc:
        print('\nError: %s' % exc, file=stderr)
        if debug:
            print(format_exc(chain=False), file=stderr)
        exit(1)
    except KeyboardInterrupt:
        exit(2)


if __name__ == '__main__':
    main()
