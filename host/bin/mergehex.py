#!/usr/bin/env python3

"""iHex file merger"""

import local
from os.path import basename
from sys import modules, stderr, stdout
from argparse import ArgumentParser, FileType
from tde.misc import pretty_size
from tde.recfmt import IHexBuilder, IHexParser


def main():
    argparser = ArgumentParser(description=modules[__name__].__doc__)
    argparser.add_argument('-i', '--input', type=FileType('rt'),
                           action='append', required=True,
                           help='path to input iHex file, may be repeated')
    argparser.add_argument('-o', '--output', type=FileType('wt'),
                           default=stdout,
                           help='path to output iHex file')
    argparser.add_argument('-x', '--noexec', action='store_true',
                           help='do not emit start address')
    argparser.add_argument('-r', '--report', action='store_true',
                           help='show stats about the generated file')
    argparser.add_argument('-d', '--debug', action='store_true',
                           help='enable debug mode')
    args = argparser.parse_args()
    start_addr = None
    segments = []
    for inhex in args.input:
        parser = IHexParser(inhex)
        parser.parse()
        exec_addr = parser.getexec()
        if not args.noexec and exec_addr is not None:
            if start_addr is not None and start_addr != exec_addr:
                raise RuntimeError('Several start up address are defined')
            start_addr = exec_addr
        for segment in parser.get_data_segments():
            c_start = segment.baseaddr
            c_end = segment.baseaddr + segment.size
            for seg in segments:
                s_start = seg.baseaddr
                s_end = seg.baseaddr + seg.size
                if c_end >= s_start and c_start < s_end:
                    raise RuntimeError('Segment override')
            segments.append(segment)
            segments.sort(key=lambda seg: seg.baseaddr)
    builder = IHexBuilder()
    if args.noexec:
        start_addr = None
    builder.build(segments, execaddr=start_addr)
    args.output.write(builder.getvalue())
    if args.report:
        min_addr = min([seg.baseaddr for seg in segments])
        max_addr = max([seg.baseaddr+seg.size for seg in segments])
        size = max_addr-min_addr
        if args.output != stdout:
            print("Flash file:   %s" % basename(args.output.name), file=stderr)
        print("Flash memory: [%06x..%06x], %s" %
              (min_addr, max_addr, pretty_size(size)), file=stderr)


if __name__ == '__main__':
    main()
