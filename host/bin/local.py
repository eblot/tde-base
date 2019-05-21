# Automatically update module system path to locate local modules

from glob import glob
from os.path import dirname, isdir, join as joinpath, normpath, pardir
from sys import path as syspath, version_info

PY_REQ_VERSION = (3, 5)

if version_info[:2] < PY_REQ_VERSION:
    raise RuntimeError("Python %s+ is required" %
                       '.'.join(['%d' % ver for ver in PY_REQ_VERSION]))

curdir = dirname(__file__)
topdir = normpath(joinpath(curdir, pardir, pardir))
extradirs = [path for path in glob(joinpath(topdir, '*', 'py')) if isdir(path)]
syspath.extend(extradirs)
