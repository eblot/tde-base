#!/usr/bin/env python3

"""SRec to TItxt file converter"""

import local
import sys
from argparse import ArgumentParser, FileType
from tde.recfmt import SRecParser, TItxtBuilder


def main():
    argparser = ArgumentParser(description=sys.modules[__name__].__doc__)
    argparser.add_argument('input', type=FileType('rt'),
                           help='path to the input SRec file')
    argparser.add_argument('output', type=FileType('wt'),
                           help='path to the output TItxt file')
    argparser.add_argument('-d', '--debug', action='store_true',
                           help='enable debug mode')
    args = argparser.parse_args()
    parser = SRecParser(args.input, segment_gap=2,
                        min_addr=0xc000, max_addr=0xffff)
    parser.parse()
    builder = TItxtBuilder()
    builder.build(parser.get_data_segments())
    args.output.write(builder.getvalue())

if __name__ == '__main__':
    main()
