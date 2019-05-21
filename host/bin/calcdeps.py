#!/usr/bin/env python3
#
# Generate the component inter-dependency list
# Caveat: does not detect nor manage circular dependencies yet

import os
import sys
from optparse import OptionParser

EXCLUDE_DIRS = ('build', 'private')

usage = 'Usage: %prog [options]\n'\
        '  generates component inter-dependency list'
optparser = OptionParser(usage=usage)
optparser.add_option('-x', '--exclude', dest='exclude',
                     default=','.join(EXCLUDE_DIRS),
                     help='comma-separated list of exclude directories')
(options, args) = optparser.parse_args(sys.argv[1:])

dirs = [d for d in os.listdir('.')
        if not d.startswith('.') and
        os.path.isdir(d) and
        d not in options.exclude.split(',')]
order = []
ooo = []
for d in dirs:
    dep = os.path.join(d, 'build.dep')
    if os.path.exists(dep):
        f = open(dep)
        cdep = filter(None, [l.strip() for l in f.readlines()])
        f.close()
        for c in cdep:
            if not os.path.exists(c):
                print("No such component: %s (from %s)" % (c, d),
                      file=sys.stderr)
                sys.exit(1)
            if d in order:
                i = order.index(d)
                if c in order[:i]:
                    pass
                elif c in order[i:]:
                    order.remove(c)
                    order.insert(i, c)
                else:
                    order.insert(0, c)
            else:
                if c not in order:
                    order.append(c)
                order.append(d)
    else:
        ooo.append(d)
order.extend([o for o in ooo if o not in order])
print(','.join(order))
