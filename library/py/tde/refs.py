"""Object tracking
"""

from collections import defaultdict
from weakref import ref as wref


class KeepRefs:
    """Object tracking (for debugging purposes)
    """

    __refs__ = defaultdict(list)

    def __init__(self):
        self.__refs__[self.__class__].append(wref(self))

    @classmethod
    def get_instances(cls):
        for inst_ref in cls.__refs__[cls]:
            inst = inst_ref()
            if inst is not None:
                yield inst
