"""FTDI SPI proxy to access the PyFtdi SPI API from CLI API.

   It enabled mapping several instances of CLI objects onto the same SPI
   controller.
"""

from logging import getLogger
from threading import Lock
from typing import Optional
from pyftdi.spi import SpiController, SpiGpioPort, SpiPort
from .gpio import GpioDevice, GpioError


# pylint: disable-msg=invalid-name


class FtdiSpiProxy:
    """SPI master through FTDI device

       :param url: FTDI URL to access the FTDI device/port
       :param cs: consecutive CS lines reserved for SPI (vs. GPIO)
       :param debug: whether to enable debug mode
    """

    DEFAULT_BUS_FREQUENCY = 6E6  # 6 MHz

    lock = Lock()
    spi_masters = dict()

    def __init__(self, url: str, cs_count: int = 1, debug: bool = False):
        self._debug = debug
        self._ports = [None] * cs_count
        self._io_port = None
        self._ctrl = self.get_master(url=url, cs_count=cs_count, debug=debug)

    def close(self) -> None:
        """Close the proxy.

           No need to actually close the SPI port
        """
        self._ports = [None] * len(self._ports)
        self._io_port = None

    @classmethod
    def get_master(cls, url, cs_count=1, debug=False) -> SpiController:
        """Instanciate and/or retrieve the SPI master.

           :param url: FTDI URL to access the FTDI device/port
           :param cs_count: consecutive CS lines reserved for SPI (vs. GPIO)
           :param debug: whether to enable debug mode
           :return: the SPI controller (master)
        """
        with cls.lock:
            if url not in cls.spi_masters:
                ctrl = SpiController()
                ctrl.configure(url, frequency=cls.DEFAULT_BUS_FREQUENCY,
                               cs_count=cs_count, debug=debug)
                cls.spi_masters[url] = ctrl
            return cls.spi_masters[url]

    def get_port(self, cs: int, frequency: Optional[float] = None,
                 mode: int = 0) -> SpiPort:
        """Retrieve a SPI port to communicate with a SPI slave.

           .. note::
             cs index should be less than the specified cs_count value of the
             SPI controller

           :param cs: the /CS index, starting from 0
           :param frequency: the bus frequency to communicate with the remote
                             slave
           :return: the SPI port
        """
        if cs >= len(self._ports):
            raise ValueError(f'Invalid CS: {cs}')
        if not self._ports[cs]:
            port = self._ctrl.get_port(cs, freq=frequency, mode=mode)
            self._ports[cs] = port
        return self._ports[cs]

    def get_io_port(self) -> SpiGpioPort:
        """Retrieve the IO port.

           The IO port maps all FTDI I/O lines that are not reserved for the
           SPI communication.

           :return: the GPIO port
        """
        if not self._io_port:
            self._io_port = self._ctrl.get_gpio()
        return self._io_port


class FtdiGpio(GpioDevice):
    """GPIO wrapper for FTDI master
    """

    def __init__(self, name, port):
        super(FtdiGpio, self).__init__(name, port.width)
        self._port = port
        # update IO mask, removing all SPI pins
        self._io_mask = self._port.all_pins

    def _configure_io(self):
        """Configure the IO ports"""
        self._port.set_direction(self._pins, self._dirs)
        self._port.write(0)

    def _write_port(self, value):
        """Update the GPIO port
        """
        self._port.write(value)

    def _read_port(self):
        """Read from the GPIO port
        """
        return self._port.read(True)

    def _filter_output(self, value):
        return value & self._dirs & self._port.pins

    def _filter_input(self, value):
        return value & self._port.pins
