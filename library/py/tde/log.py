"""Logging helpers."""

from logging import StreamHandler, ERROR, INFO, WARNING, getLogger
from typing import IO, Optional
import sys


class BareLogger:

    log = getLogger('tde')
    log.addHandler(StreamHandler(sys.stderr))
    log.setLevel(level=WARNING)

    @classmethod
    def set_formatter(cls, formatter):
        handlers = list(cls.log.handlers)
        for handler in handlers:
            handler.setFormatter(formatter)

    @classmethod
    def get_level(cls):
        return cls.log.getEffectiveLevel()

    @classmethod
    def set_level(cls, level):
        cls.log.setLevel(level=level)


class BareStreamToLogger:
    """Fake file-like stream object that redirects writes to a logger instance.

       :param log_name: name of the logger
       :param log_level: level of the logger
       :param tee_stream: optional stream to tee
    """

    def __init__(self, log_name: str, log_level: int,
                 tee_stream: Optional[IO] = None):
        self.log = getLogger(log_name)
        self._level = log_level
        self._tee_stream = tee_stream

    def write(self, buf):
        """Write data to the logger, and optionally to the tee stream.
        """
        if self._tee_stream:
            print(buf, file=self._tee_stream, end='')
        for line in buf.rstrip().splitlines():
            self.log.log(self._level, line.rstrip())

    def flush(self):
        if self._tee_stream:
            self._tee_stream.flush()

    @classmethod
    def capture_stdout(cls, name: Optional[str] = None,
                       tee: Optional[bool] = True):
        """Capture stdout.

           :param name: the logger name
           :param tee: whether to tee stderr, or send exclusively to logger
        """
        if not name:
            name = 'tde.main'
        elif name.startswith('.'):
            name = 'tde.%s' % name
        stl = cls(name, INFO, tee and sys.__stdout__)
        sys.stdout = stl

    @classmethod
    def capture_stderr(cls, name: Optional[str] = None,
                       tee: Optional[bool] = True):
        """Capture stderr.

           :param name: the logger name
           :param tee: whether to tee stderr, or send exclusively to logger
        """
        if not name:
            name = 'tde.main'
        elif name.startswith('.'):
            name = 'tde.%s' % name
        stl = cls(name, ERROR, tee and sys.__stderr__)
        sys.stderr = stl
