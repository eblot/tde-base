"""Simple command line wrapper"""

import os
from io import TextIOWrapper
from subprocess import Popen, DEVNULL, PIPE
from sys import stderr
from time import sleep, time as now


class Command:
    """Context manager for a shell command.
       Run the command specified as a list of parameters.

       The Command constructor accepts modifiers as keyword arguments:

         * ``nosignal`` (expects a boolean value) to prevent Python from
           forwarding signals received in the Python VM to the subprocess
         * ``nostderr`` (expects a boolean value) to prevent the command from
           sending stderr to the default stderr (stderr messages are discarded)
         * ``debug`` to report errors
         * ``cwd`` to specify a working directory
    """

    GRACE_DELAY = 0.5
    POLL_PERIOD = 0.0025

    def __init__(self, command, *args, **kwargs):
        self._cmd = None
        # be sure to use the untranslated output strings
        environment = dict(os.environ)
        environment['LC_ALL'] = 'C'
        preexec = Command.preexec if kwargs.get('nosignal', False) else None
        self._stderr = not bool(kwargs.get('nostderr', False))
        cwd = kwargs.get('cwd', None) or os.getcwd()
        self._dbg = kwargs.get('debug', False)
        self._args = [command] + list(args)
        try:
            self._cmd = Popen(self._args,
                              stdout=PIPE,
                              stderr=PIPE if self._stderr else DEVNULL,
                              env=environment,
                              cwd=cwd,
                              preexec_fn=preexec)
        except OSError as exc:
            raise OSError("Cannot launch command: %s" % str(exc))

    def __enter__(self):
        return TextIOWrapper(self._cmd.stdout, encoding='utf8')

    def __exit__(self, type, value, tbl):
        # process not started or process exited with code 0
        if not self._cmd:
            return
        # give the process a delay to exit properly
        polltime = now() + self.GRACE_DELAY
        while now() < polltime:
            if self._check_status() is not None:
                return
        # give the process a delay to exit properly
        killtime = now() + self.GRACE_DELAY
        while now() < killtime:
            # check periodically if it exited by itself
            rc = self._check_status()
            if rc is not None:
                return
            # process still alive
            self._cmd.terminate()
            sleep(self.POLL_PERIOD)
        # kill it
        self._cmd.kill()
        self._cmd.wait()
        if self._dbg:
            raise OSError('Command process had to be killed '
                          'as it looked stuck', file=stderr)

    def _check_status(self):
        rc = self._cmd.poll()
        if rc is not None:
            if rc != 0:
                if self._stderr:
                    error = []
                    while True:
                        char = self._cmd.stderr.read(1)
                        if char in b'\r\n':
                            break
                        error.append(char)
                    stderr.write(b''.join(error).decode())
                raise OSError(rc)
        return rc

    @staticmethod
    def preexec():
        # Don't forward signals.
        os.setpgrp()
