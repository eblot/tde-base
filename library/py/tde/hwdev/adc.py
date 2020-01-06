class AdcError(Exception):
    """Base class exception for all GPIO errors"""


class AdcValueError(ValueError, AdcError):
    """Invalid value for GPIO"""


class AdcDevice:
    """An abstract device that gather one or more GPIO pins"""

    def read(self, channel=0):
        raise NotImplementedError()
