"""Command line interpreter core
"""

from ast import literal_eval
from binascii import hexlify, unhexlify
from collections import OrderedDict, deque
from contextlib import redirect_stderr, redirect_stdout
from cmd import Cmd
from csv import reader as csvreader
from glob import glob
from importlib import import_module
from inspect import signature, Parameter
from io import StringIO
from os import environ, linesep, pardir, sep as pathsep, stat, walk
from os.path import (dirname, expanduser, isdir, isfile, join as joinpath,
                     normpath, realpath, relpath, splitext)
from pprint import pformat
from re import compile as recompile, split as resplit, sub as resub
from shlex import shlex
from shutil import get_terminal_size
from subprocess import call, check_call
import sys
from sys import argv, modules, platform
from textwrap import fill as wrapfill
from tempfile import mkstemp
from textwrap import TextWrapper
from time import localtime, strftime, sleep, time as now
from traceback import extract_tb, print_exc
from typing import Any, Callable, List, NewType, Optional, Tuple, Union
from .misc import (EasyConfigParser, EasyDict, EasyFloat, classproperty,
                      file_generator, flatten, flatten_dict, group,
                      is_iterable, plural, to_bool, to_int, xor)
from .term import cleanup_console, getkey

# pylint: disable-msg=broad-except
# pylint: disable-msg=eval-used
# pylint: disable-msg=try-except-raise
# pylint: disable-msg=missing-docstring
# pylint: disable-msg=too-many-locals
# pylint: disable-msg=too-many-statements
# pylint: disable-msg=too-many-branches
# pylint: disable-msg=too-many-nested-blocks
# pylint: disable-msg=unused-argument


try:
    import readline as rl
except ImportError:
    try:
        import pyreadline as rl
    except ImportError:
        rl = None


class CmdShellError(Exception):
    """Exception raised when a command cannot be executed."""

    def __init__(self, msg, show_usage=False, cmd=None):
        super(CmdShellError, self).__init__(msg)
        self.show_usage = show_usage
        self.cmd = cmd
        self.reported = False


class CmdShellExtError(CmdShellError):
    """CmdShellError with an error code."""

    def __init__(self, code, msg, *args, **kwargs):
        super(CmdShellExtError, self).__init__(msg, *args, **kwargs)
        self.code = code


class CmdShellManager(Cmd):
    """
    """

    VAR_RE = r'[A-Z_]\w*'
    VAR_CRE = recompile(r'(?i)^' + VAR_RE + r'$')
    ENVVAR_CRE = recompile(r'(?i)\${(?P<envvar>' + VAR_RE + ')'
                           r'(?P<default>\:[\-=][\w\.]+)?}')
    ITE_CRE = recompile(r'(?P<ite>if|else|fi|it|ite)(?:\s*$|\s+(?P<cond>.*)?)')
    NPTH_CRE = recompile(r'[\,\:]\s?')
    SPC_CRE = recompile(r'\s+')
    DOCARG_CRE = recompile(r':param\s+([^:]+)\s*:')

    DEFAULT_MODULES = {}
    """Enable modules preload from an external source (pyinstaller)."""

    VERSION = ''
    """Enable revision definition from an external source."""

    DynVarHandler = NewType('DynVarHandler', Callable[[str], Any])
    """A handler to generate variable value on demand."""


    class Environ(dict):

        def __init__(self, *args, **kwargs):
            dict.__init__(self, *args, **kwargs)
            self._dynvars = dict()

        def register(self, name: str,
                     handler: Optional['DynVarHandler']) -> None:
            if handler:
                self._dynvars[name] = handler

        def __getitem__(self, name):
            if name not in self._dynvars:
                return dict.__getitem__(self, name)
            handler = self._dynvars[name]
            return handler(name)


    def __init__(self, name, debug=False):
        super(CmdShellManager, self).__init__()
        self.prompt = '> '
        self._modules = self.DEFAULT_MODULES
        self._providers = {}
        self._curdomains = None
        self._force_multi = False
        self._regular = True
        self._last_result = ''
        self._expect_error = None
        self._speak = False
        self._debug = debug
        history_name = name.replace(' ', '').lower()
        self._history_path = expanduser("~/.py%s" % history_name)
        self._disable_show_usage = set()
        self._environ = CmdShellManager.Environ(environ)
        self._environ.pop('_', None)
        self._environ['_lasterror_'] = 0
        self._environ.register('_store_', self._get_readonly_store)
        self._store = [[]]
        self._store_columns = []
        self._scripts = []

    def complete(self, text, state):
        # Override default Cmd.complete method
        # when this method is used with pyreadline module on Windows, state
        # may be None, which trigger an uncaught TypeError exception.
        # As Cmd is part of standard Python distribution and pyreadline is an
        # external module, there would be hard to fix so add this workaround
        # here.
        try:
            return super(CmdShellManager, self).complete(text, state)
        except TypeError:
            return None

    def finalize(self):
        for provider, _ in self._providers.values():
            provider.finalize()

    def add_provider(self, provider):
        containers = []
        for class_ in provider.containers:
            try:
                containers.append(class_(**provider.context))
            except Exception as ex:
                if self._debug:
                    print_exc(chain=False, file=sys.stderr)
                raise CmdShellError('Unable to instanciate %s: %s' %
                                    (class_.__name__, ex))
        if not containers:
            print('%s expose no commands' % provider.__class__.__name__,
                  file=sys.stderr)
        self._providers[provider.domains] = provider, containers
        if not self.is_multi:
            self._curdomains = list(self._providers)[0]
        else:
            self._curdomains = ('', '')
        self._set_prompt()

    @classmethod
    def load_candidates(cls, paths):
        try:
            candidates = {}
            for path in paths:
                for dirpath, dirnames, filenames in walk(path):
                    dirnames[:] = [d for d in dirnames if not d.endswith('__')
                                   and not d.startswith('.')]
                    for fname in filenames:
                        if not fname.endswith('.py'):
                            continue
                        if fname.startswith('.'):
                            continue
                        fpath = joinpath(dirpath, fname)
                        with open(fpath, 'rt') as pyfp:
                            content = pyfp.read()
                            for mo in CmdShellProvider.CRE.finditer(content):
                                rpath = relpath(fpath, path)
                                rname = splitext(rpath)[0]
                                mod = rname.replace(pathsep, '.')
                                class_ = mo.group('class')
                                name = class_.lower()
                                for suffix in 'provider command'.split():
                                    if name.endswith(suffix):
                                        name = name[:-len(suffix)]
                                candidates[name] = ((mod, mo.group(1)))
            return candidates
        except Exception as ex:
            print(ex, file=sys.stderr)

    def set_module_paths(self, paths, show=False):
        self._modules.update(self.load_candidates(paths))
        if show:
            self.show_modules()

    def show_modules(self):
        for name in sorted(self._modules):
            print(' %s' % name)

    @property
    def is_multi(self):
        return self._force_multi or (len(self._providers) > 1)

    def load(self, rcfp):
        try:
            return self._load(rcfp, False)
        except (KeyboardInterrupt, SystemExit):
            self.finalize()
            raise

    @staticmethod
    def domain_key(dmk):
        # sort by shorter length, lowercase before uppercase
        return (len(dmk), sum([int('A' <= v <= 'Z') for v in dmk]))

    @classmethod
    def normalize_path(cls, path: str) -> str:
        """Ensure a file path name is valid, replacing invalid chars.

           :param path: path to normalize
           :return: normalized path
        """
        path = cls.NPTH_CRE.sub('-', path)
        path = cls.SPC_CRE.sub('_', path)
        return path.strip('"')

    @classmethod
    def short_domain(cls, domains):
        return list(sorted(domains, key=cls.domain_key))[0]

    @staticmethod
    def is_cli_error(exc: Exception) -> bool:
        """Guess if an exception comes from the CLI argument interpretation.

           This is an heuristic to help the shell manager to report the proper
           error message. A wrapper function name should always start and end
           with '_' (CmdShell naming convention).

           :return: True if the exception has been raised by the CLI front end.
        """
        if not isinstance(exc, TypeError):
            return False
        tbf = extract_tb(exc.__traceback__)
        if len(tbf) == 1:
            return True
        fname = tbf[1].name
        if fname.startswith('_') and fname.endswith('_'):
            return True
        return False

    @classmethod
    def long_domain(cls, domains):
        return list(sorted(domains, key=cls.domain_key))[-1]

    def _get_readonly_store(self, name):
        return list(self._store[-1])

    def _store_result(self, result):
        if isinstance(result, dict):
            if not isinstance(result, EasyDict):
                result = EasyDict(result)
        self._last_result = result

    def _set_prompt(self):
        self.prompt = '%s> ' % self.long_domain(self._curdomains)

    def run(self, clean=False):
        if rl:
            # ':' is used as a natural MAC address character and should not
            # be considered as an argument delimiter
            delims = rl.get_completer_delims()
            for nodelim in ':/-=':
                delims = delims.replace(nodelim, '')
            rl.set_completer_delims(delims)
            if not clean:
                if isfile(self._history_path):
                    rl.read_history_file(self._history_path)
        try:
            self.cmdloop()
        except (KeyboardInterrupt, SystemExit):
            self.finalize()

    def emptyline(self):
        pass

    def onecmd(self, line, stop_on_error=False):
        """`line` may be a `str` or an `unicode` object"""
        # Re-implement Cmd.onecmd to avoid raising an AttributeException on
        # every command call
        try:
            cmd, arg, line = self.parseline(line)
            if not line:
                return self.emptyline()
            if cmd is None:
                return self.default(line)
            self.lastcmd = line
            if line == 'EOF':
                self.lastcmd = ''
            if cmd == '':
                return self.default(line)
            do_cmd = 'do_' + cmd
            if hasattr(self, do_cmd):
                func = getattr(self, do_cmd)
                if self._speak:
                    self._say(' '.join((cmd, arg)))
                try:
                    if cmd not in ('count', 'echo'):
                        arg = self.ENVVAR_CRE.sub(self._replace_env_var,
                                                  arg)
                except ValueError as ex:
                    raise CmdShellError(str(ex))
                args = self.arg_tokenize(arg)
                sts = now()
                try:
                    result = func(*args)
                except ValueError as exc:
                    raise CmdShellError(str(exc))
                exec_time = EasyFloat(now()-sts)
                exec_time.format = '%.6f'
                self._environ['_time_'] = exec_time
                self._store_result(result)
                return
            return self.default(line)
        except SystemExit:
            raise
        except CmdShellError as exc:
            if isinstance(exc, CmdShellExtError):
                self._environ['_lasterror_'] = exc.code
            if not exc.reported:
                print("Error: %s" % exc, file=sys.stderr)
                exc.reported = True
            if exc.show_usage:
                print()
                args = self.arg_tokenize(exc.cmd or line)
                self.do_help(args[0], *args[1:])
            if stop_on_error:
                raise
        except TypeError as exc:
            if self._debug:
                print_exc(chain=False, file=sys.stderr)
            if stop_on_error:
                raise RuntimeError('Invalid call to %s: %s' %
                                   (cmd, str(exc).split(')')[-1].strip()))
        except Exception as exc:
            if stop_on_error:
                raise

    def _get_commands(self, domains, container, use_default=False):
        prefix = self.short_domain(domains) if self.is_multi else ''
        while True:
            for cmd in container.get_commands():
                if prefix and not any(self._curdomains):
                    cmdl = list(cmd)
                    cmdl[0] = ' '.join((prefix, cmd[0]))
                    cmd = tuple(cmdl)
                yield cmd
            if prefix:
                break
            if not use_default:
                break
            prefix = self.short_domain(self._curdomains)
            if not prefix:
                break

    def get_command_help(self, args=None):
        """Return help information for a set of commands."""
        commands = []
        if args is None:
            args = []
        for domains, (_, containers) in self._providers.items():
            if any(self._curdomains) and self._curdomains != domains:
                continue
            for container in containers:
                for cmd in self._get_commands(domains, container, False):
                    parts = cmd[0].split()
                    if parts[:len(args)] == args:
                        commands.append(cmd[0:3])
        commands.sort()
        return commands

    def complete_command(self, args, cmd_only=False):
        """Perform auto-completion on the given arguments."""
        comp = []
        for domains, (_, containers) in self._providers.items():
            if any(self._curdomains) and self._curdomains != domains:
                continue
            for container in containers:
                for cmd in self._get_commands(domains, container, True):
                    parts = cmd[0].split()
                    plen = min(len(parts), len(args) - 1)
                    # Prefix doesn't match
                    if args[:plen] != parts[:plen]:
                        continue
                    # Command name
                    elif len(args) <= len(parts):
                        comp.append(parts[len(args) - 1])
                    # Arguments
                    elif not cmd_only:
                        if cmd[3] is None:
                            return []
                        return cmd[3](args[len(parts):]) or []
        return comp

    def execute_command(self, *args):
        """Execute a command given by a list of arguments."""
        args = list(args)
        for domains, (provider, containers) in self._providers.items():
            for container in containers:
                if any(self._curdomains) and self._curdomains != domains:
                    continue
                for cmd in self._get_commands(domains, container, True):
                    if len(cmd) < 5:
                        raise CmdShellError('Invalid command descriptor: %s' %
                                            (len(cmd) and cmd[0] or 'unknown'))
                    parts = cmd[0].split()
                    if args[:len(parts)] == parts:
                        func = cmd[4]
                        fargs = args[len(parts):]
                        try:
                            if self._speak:
                                self._say(' '.join(args))
                            sts = now()
                            result = func(*fargs)
                            exec_time = EasyFloat(now()-sts)
                            exec_time.format = '%.6f'
                            self._environ['_time_'] = exec_time
                            self._store_result(result)
                            return
                        except CmdShellError as exc:
                            if isinstance(exc, CmdShellExtError):
                                self._environ['_lasterror_'] = exc.code
                            if self._debug and self._expect_error is None:
                                print_exc(chain=False, file=sys.stderr)
                                exc.reported = True
                            if self._speak:
                                self._say('Execution error: %s' % exc)
                            exc.cmd = ' '.join(parts)
                            raise
                        except TypeError as exc:
                            if self.is_cli_error(exc):
                                if self._debug:
                                    print_exc(chain=False, file=sys.stderr)
                                raise CmdShellError("Invalid arguments",
                                                    show_usage=True,
                                                    cmd=' '.join(parts))
                            raise
                        except KeyboardInterrupt:
                            print('')
                            if len(cmd) > 5:
                                abort_func = cmd[5]
                                if abort_func:
                                    abort_func()
                            raise CmdShellError('Aborted')
                        except Exception as ex:
                            if self._speak:
                                self._say('Failure: %s' % ex)
                            if self._debug and self._expect_error is None:
                                print_exc(chain=False, file=sys.stderr)
                                raise
                            raise CmdShellError(str(ex))
        show_usage = 'command_not_found' not in self._disable_show_usage
        raise CmdShellError("Command not found", show_usage=show_usage)

    def arg_tokenize(self, argstr):
        """`argstr` is an `unicode` string

        ... but shlex is not unicode friendly.
        """
        lex = shlex(argstr, posix=False)
        lex.whitespace_split = True
        lex.commenters = ''
        if platform == 'win32':
            lex.escape = ''
        return list(lex) or ['']

    def word_complete(self, text, words):
        words = list(set(a for a in words if a.startswith(text)))
        if len(words) == 1:
            words[0] += ' '     # Only one choice, skip to next arg
        return words

    @staticmethod
    def split_help_text(text):
        paragraphs = resplit(r'(?m)(?:^[ \t]*\n){1,}', text)
        return [resub(r'(?m)[ \t\n]+', ' ', each.strip())
                for each in paragraphs]

    @classmethod
    def print_doc(cls, docs, stream=None, short=False, long_=False):
        if stream is None:
            stream = sys.stdout
        docs = [doc for doc in docs if doc[2]]
        if not docs:
            return
        if short:
            max_len = max(len(doc[0]) for doc in docs)
            for (cmd, args, doc) in docs:
                paragraphs = cls.split_help_text(doc)
                print('%s  %s' % (cmd.ljust(max_len), paragraphs[0]))
        else:
            nb_cmd_in_docs = len(docs)
            for (cmd, args, doc) in docs:
                paragraphs = cls.split_help_text(doc)
                print('%s %s' % (cmd, args))
                doc_first_line = '    %s' % paragraphs[0]
                if len(paragraphs) > 1:
                    if (long_ or nb_cmd_in_docs == 1):
                        print(doc_first_line)
                        columns, _ = get_terminal_size((80, 20))
                        for paragraph in paragraphs[1:]:
                            print(wrapfill(paragraph.replace(u'\u00a0', ' '),
                                           columns-2, initial_indent='    ',
                                           subsequent_indent='    '))
                    else:
                        print('%s...' % doc_first_line.rstrip('.'))
                else:
                    print(doc_first_line)

                # Final new line
                print('')

    # --- Command dispatcher

    def complete_line(self, text, line, cmd_only=False):
        args = self.arg_tokenize(line)
        if line and line[-1] == ' ':    # Space starts new argument
            args.append('')
        try:
            comp = self.complete_command(args, cmd_only)
        except Exception as exc:
            print('\nCompletion error: %s' % exc, file=sys.stderr)
            comp = []
        if len(args) == 1:
            comp.extend(name[3:] for name in self.get_names()
                        if name.startswith('do_'))
        try:
            return comp.complete(text)
        except AttributeError as ex:
            return self.word_complete(text, comp)

    def completenames(self, text, line, begidx, endidx):
        return self.complete_line(text, line, True)

    def completedefault(self, text, line, begidx, endidx):
        return self.complete_line(text, line)

    def default(self, line):
        try:
            line = self.ENVVAR_CRE.sub(self._replace_env_var, line)
        except ValueError as ex:
            raise CmdShellError(str(ex))
        args = self.arg_tokenize(line)
        should_raise = self._expect_error is not None
        try:
            self.execute_command(*args)
        except Exception as exc:
            if self._expect_error is not None:
                error = str(exc)
                if not self._expect_error or \
                        error.startswith(self._expect_error):
                    return error
                if self._debug:
                    print('Error mismatch')
            raise
        finally:
            self._expect_error = None
        if should_raise:
            raise CmdShellError('Error not triggered')

    def _load(self, fp, resume_on_error=False):
        self._scripts.append(fp.name)
        try:
            self._regular = True
            result = self._execute_script(fp)
            if resume_on_error:
                self._regular = True
            return result
        except Exception:
            if not resume_on_error:
                raise
            self._regular = True
            # signal an exception has been raised
            return True
        finally:
            self._scripts.pop()

    def _execute_script(self, fp):
        linemark = '*'*len(self._scripts)
        lines = ['']
        for nln, line in enumerate(fp, start=1):
            if '#' in line:
                line = line[:line.find('#')]
            line = line.strip()
            lines.append(line)
        nln = 1
        lastl = len(lines)-1
        stack = deque()
        ite = deque()
        self._disable_show_usage.add('command_not_found')
        exec_exc = None
        while nln <= lastl:
            line = lines[nln]
            if not line:
                # empty line
                nln += 1
                continue
            if stack and stack[-1][-1] is None:
                # repeater exists but has been cancelled (broken)
                if not line.strip().startswith('@end'):
                    #ignore all lines till @end is found
                    nln += 1
                    continue
            if line.strip().startswith('@') and self._regular:
                line = line[line.find('@')+1:]
                if line.startswith('repeat'):
                    args = []
                    for arg in line[6:].split():
                        mo = self.ENVVAR_CRE.match(arg)
                        if mo:
                            arg = self._expand_env_var(mo)
                        if not isinstance(arg, str) and is_iterable(arg):
                            args.extend(arg)
                        else:
                            args.append(arg)
                    try:
                        if not args:
                            raise ValueError('Missing repeat variable')
                        if len(args) < 2:
                            raise ValueError('Missing count')
                        if len(args) > 4:
                            raise ValueError('Too many arguments')
                        vname = args[0]
                        if not self.VAR_CRE.match(vname):
                            raise ValueError('Invalid value name: %s' % vname)
                        args = [to_int(val) for val in args[1:]]
                    except ValueError as ex:
                        raise CmdShellError('Invalid repetition: %s' % ex)
                    rrange = range(*args)
                    repeater = iter(rrange)
                    try:
                        self._environ[vname] = next(repeater)
                    except StopIteration:
                        raise CmdShellError('Repetition cannot iterate %s' %
                                            rrange)
                    stack.append([nln, vname, len(ite), repeater])
                    nln += 1
                    continue
                elif line.startswith('foreach'):
                    args = []
                    for arg in line[8:].split():
                        mo = self.ENVVAR_CRE.match(arg)
                        if mo:
                            try:
                                arg = self._expand_env_var(mo)
                            except Exception as exc:
                                print(arg, mo)
                                raise
                        if not isinstance(arg, str) and is_iterable(arg):
                            args.extend(arg)
                        else:
                            args.append(arg)
                    try:
                        if not args:
                            raise ValueError('Missing foreach variable')
                        vname = args[0]
                        if not self.VAR_CRE.match(vname):
                            raise ValueError('Invalid value name: %s' % vname)
                    except ValueError as ex:
                        raise CmdShellError('Invalid foreach: %s' % ex)
                    repeater = iter(args[1:])
                    try:
                        self._environ[vname] = next(repeater)
                    except StopIteration:
                        raise CmdShellError('Foreach is empty')
                    stack.append([nln, vname, len(ite), repeater])
                    nln += 1
                    continue
                elif line.startswith('break'):
                    if not stack:
                        raise CmdShellError('@break without repeat')
                    # let this special command execute through conditional
                    # evaluation (fallthrough and restore special marker)
                    line = '@break'
                elif line.startswith('end'):
                    if not stack:
                        raise CmdShellError('@end without repeat')
                    rln, vname, lenite, riter = stack[-1]
                    try:
                        if riter is None:
                            raise StopIteration()
                        self._environ[vname] = next(riter)
                        nln = rln+1
                    except StopIteration:
                        stack.pop()
                        nln += 1
                    continue
                else:
                    imo = self.ITE_CRE.match(line)
                    if imo:
                        condparts = line.split(' ', 1)
                        if len(condparts) > 1:
                            try:
                                cond = self._environ[condparts[1]]
                            except Exception as exc:
                                raise CmdShellError("Cannot use '%s' as "
                                                    "condition" % condparts[1])
                        else:
                            cond = self._last_result
                        try:
                            execute = bool(cond)
                        except Exception:
                            raise CmdShellError('Cannot interpret condition')
                        itew = imo.group('ite')
                        if itew == 'if':
                            ite.append([True, execute])
                        elif itew in ('else', 'fi'):
                            if not ite:
                                raise CmdShellError('%s without if' % itew)
                            if not ite[-1][0]:
                                # should end if/else, not it/ite
                                raise CmdShellError('%s invalid here' % itew)
                            if itew == 'fi':
                                ite.pop()
                            else:  # else
                                ite[-1][1] = not ite[-1][1]
                        elif itew == 'ite':
                            ite.append([False, not execute, execute])
                        elif itew == 'it':
                            ite.append([False, execute])
                        else:  # should never happen (RE match)
                            CmdShellError('Internal ITE error')
                        nln += 1
                    else:
                        raise CmdShellError('Invalid syntax: @%s' % line)
                    continue
            commands = [cmd.strip() for cmd in line.split(';')]
            for cmd in commands:
                if self._regular:
                    # do not try to use conditionals and loops after an error
                    if ite:
                        if ite[-1][0]:
                            # if/then/else
                            conds = ite[-1]
                        else:
                            # it/ite
                            conds = ite.pop()
                            if len(conds) > 2:
                                # ite
                                ite.append([False, conds[1]])
                        if not conds[-1]:
                            if self._debug:
                                print('%s%s %d: %s -> disabled' %
                                      (linesep, linemark, nln, cmd))
                            continue
                    if cmd == '@break':
                        stack[-1][-1] = None
                        lenite = stack[-1][2]
                        while len(ite) > lenite:
                            # unpop all conditions that are skipped
                            ite.pop()
                        continue
                forced = cmd.startswith('!')
                if forced:
                    cmd = cmd[1:]
                if self._regular:
                    mode = ''
                else:
                    if forced:
                        mode = ' (forced)'
                    else:
                        mode = ' -> skipped'
                action = cmd.split(' ', 1)[0]
                if self._debug or action not in ('echo', 'prompt'):
                    print('%s%s %d: %s%s' % (linesep, linemark, nln, cmd, mode))
                if self._regular or forced:
                    try:
                        self.onecmd(cmd, True)
                    except KeyboardInterrupt:
                        break
                    except SystemExit as exc:
                        if exec_exc and not exc.code:
                            # executing quit if a stored exception should not
                            # lose the error code
                            raise SystemExit(1)
                        raise
                    except CmdShellError as exc:
                        # error has already be printed out
                        self._regular = False
                        if not exec_exc:
                            exec_exc = exc
                    except Exception as exc:
                        print(exc, file=sys.stderr)
                        self._regular = False
                        if not exec_exc:
                            exec_exc = exc
                    if not self._regular and stack:
                        # clear the execution stack on error
                        stack.clear()
            nln += 1
        self._disable_show_usage.discard('command_not_found')
        if stack:
            raise CmdShellError('Repetition without end @ line %d' %
                                stack[-1][0])
        if not self._debug:
            if exec_exc:
                # re-raise the first caught exception (except in debug mode)
                raise exec_exc
        return bool(exec_exc)

    def _replace_env_var(self, mo):
        value = self._expand_env_var(mo)
        if not isinstance(value, str) and is_iterable(value):
            if isinstance(value, dict):
                value = ' '.join([f'{k},{v}' for k, v in value.items()])
            else:
                value = ' '.join([str(x) for x in value])
        else:
            value = str(value)
        return value

    def _expand_env_var(self, mo):
        varname = mo.group('envvar')
        defval = mo.group('default')
        if defval:
            default = defval[2:]
            if defval[1] == '=':
                if varname not in self._environ:
                    self._environ[varname] = default
        else:
            default = None
        try:
            self._environ['_'] = self._last_result
            try:
                value = self._environ[varname]
            except KeyError:
                if default is None:
                    raise ValueError(f"Environment variable '{varname}' does "
                                     f"not exist")
                return default
            return value
        finally:
            if '_' in self._environ:
                del self._environ['_']

    @classmethod
    def get_default_args(cls, func):
        sig = signature(func)
        return {
            k: (v.default if k != 'args' else None)
            for k, v in sig.parameters.items()
            if v.default is not Parameter.empty or k == 'args'
        }

    @classmethod
    def _parse_argument(cls, parameter, value) -> Union[Tuple[Any], None]:
        annot = parameter.annotation
        origin = getattr(annot, '__origin__', None)
        if origin and origin is Union:
            types = set(annot.__args__)
        else:
            types = {annot}
        val = None
        optional = False
        while types:
            if float in types:
                types.remove(float)
                try:
                    val = float(value)
                    break
                except Exception:
                    pass
            if value is not None:
                if bool in types:
                    types.remove(bool)
                    try:
                        val = to_bool(value, permissive=False)
                        break
                    except Exception:
                        pass
                if int in types:
                    types.remove(int)
                    try:
                        val = to_int(value)
                        break
                    except Exception:
                        pass
            if str in types:
                types.remove(str)
                val = value
                break
            if type(None) in types:
                types.remove(type(None))
                optional = True
                break
            if types:
                default = types.pop()
                try:
                    val = default(value)
                except Exception:
                    pass
        if val is None:
            if optional:
                return None
            if value is not None:
                raise ValueError(f"Invalid value '{value}' for "
                                 f"{parameter.name}")
            raise ValueError(f"Missing value for '{parameter.name}'")
        return (val, )

    @classmethod
    def parse_arguments(cls, func: Callable, *args: str) -> List[Any]:
        sig = signature(func)
        parameters = sig.parameters
        values = list(args)
        values.extend([None]*(len(parameters) - len(values)))
        vargs = []
        params = parameters.values()
        multi = False
        param = None
        for param, value in zip(params, values):
            multi = param.kind == param.VAR_POSITIONAL
            val = cls._parse_argument(param, value)
            if val is not None:
                vargs.append(val[0])
            if multi:
                break
        if multi:
            for value in values[len(vargs):]:
                val = cls._parse_argument(param, value)
                if val is not None:
                    vargs.append(val[0])
        return vargs

    @classmethod
    def document_handler(cls, func: Callable) -> Tuple[str, str]:
        params = signature(func).parameters
        args = []
        for param in params.values():
            annot = param.annotation
            origin = getattr(annot, '__origin__', None)
            if origin and origin is Union:
                types = set(annot.__args__)
            else:
                types = {annot}
            multi = param.kind == param.VAR_POSITIONAL
            name = param.name
            if multi:
                name = name.rstrip('s')
            if type(None) in types:
                args.append(f'[{name}]')
            else:
                args.append(f'<{name}>')
            if multi:
                args.append(f'[{name}]...')
        lines = []
        docstr = func.__doc__
        if docstr:
            for pos, line in enumerate(docstr.split('\n')):
                if not pos:
                    lines.append(line.rstrip('.').strip())
                    continue
                line = line.lstrip()
                pline = cls.DOCARG_CRE.sub(r' \1:', line)
                if line != pline:
                    lines.append('\n')
                    lines.append(pline)
                else:
                    lines.append(line)
            doc = '\n'.join(lines)
        else:
            doc = '(not documented)'
        return doc, ' '.join(args)

    # --- Available Commands

    def all_docs(self):
        docs = [('', '', '--- Root domain commands ---')]
        docs.extend(self.build_short_doc())
        if self._curdomains:
            if self._curdomains[0]:
                msg = '--- Commands for domain %s [%s] ---' % \
                       (self._curdomains[1], self._curdomains[0])
            else:
                msg = '--- Commands for loaded providers ---'
            docs.append(('', '', msg))
            docs.extend(self.get_command_help())
        return docs

    def complete_help(self, text, line, begidx, endidx):
        if line[5:].startswith('setup'):
            args = self.arg_tokenize(line[5:])
            comp = list(self._modules)
            if len(args) > 1:
                return self.word_complete(text, comp)
            return comp
        return self.complete_line(text, line[5:], True)

    def complete_setup(self, *args):
        params = [x for x in args[1].split()]
        count = len(params)
        candidates = []
        issues = {}
        for provider, (module, classname) in self._modules.items():
            out = StringIO()
            with redirect_stderr(out):
                with redirect_stdout(out):
                    try:
                        mod = import_module(module)
                        pvdr_cls = getattr(mod, classname)
                        if pvdr_cls.domains in self._providers:
                            continue
                    except Exception as ex:
                        print(f'discarding {classname}, {ex}', file=out)
                        continue
                    candidates.append(provider)
            output = out.getvalue().strip()
            if output:
                issues[provider] = output
        wrapper = None
        for provider, issue in issues.items():
            if wrapper is None:
                wrapper = TextWrapper()
                if not self._debug:
                    wrapper.max_lines=1
                print('')
            indent = ' ' * len(f'{provider}: ')
            wrapper.subsequent_indent = indent
            msg = wrapper.fill(issue)
            print(f'{provider}: {msg}')
        if count == 1:
            return candidates
        if args[-2] == args[-1]:
            count += 1
        if count == 2:
            return ['%s ' % provider for provider in candidates
                    if provider.startswith(params[1])]
        if count <= 2:
            return
        try:
            module, classname = self._modules[params[1]]
            mod = import_module(module)
            pvdr_cls = getattr(mod, classname)
            arguments = self.document_provider_setup(pvdr_cls)
            pos = count-3
            if len(arguments) > pos:
                candidate = arguments[pos][0]
                olds = params[-1].split('=', 1)
                if len(olds) == 2 and olds[1]:
                    if olds[0] == candidate:
                        return ['%s ' % params[-1]]
                return ['%s=' % candidate]
        except Exception as ex:
            pass

    def do_help(self, command='', *args):
        """Display the help for all or a specific command.

           :param command: the command to document
        """
        try:
            if command:
                doc = None
                func = getattr(self, 'do_%s' % command, None)
                if func:
                    doc = self.build_command_doc(func, args)
                if not doc:
                    doc = self.get_command_help([command] + list(args))
                if doc:
                    self.print_doc(doc)
                else:
                    print("No documentation found for '%s'."
                          " Use 'help' to see the list of commands." %
                          ' '.join([command] + list(args)), file=sys.stderr)
            else:
                self.print_doc(self.all_docs(), short=True)
        except Exception:
            if self._debug:
                print_exc(chain=False, file=sys.stderr)
            raise

    def do_quit(self, exit_code=None):
        """Quit the command line interpreter.

           :param: exit_code optional exit code
        """
        code = 0
        try:
            if exit_code:
                try:
                    code = int(exit_code)
                    if code > 127:
                        raise ValueError()
                except ValueError:
                    raise CmdShellError('Invalid exit code')
            print()
            if rl:
                if rl.get_current_history_length() > 0:
                    try:
                        rl.append_history_file(100, self._history_path)
                    except (AttributeError, OSError):
                        rl.write_history_file(self._history_path)
        except Exception as ex:
            print("Error while quitting: ", ex)
            code = 127
        sys.exit(code)

    do_exit = do_quit  # Alias

    def do_setup(self, provider=None, *args):
        """Load and configure a command provider.

           Depending on the provider, this command may expect a list of
           mandatory arguments, followerd with optional arguments, if any.

           Use auto-completion to retrieve the list of the available provider
           and the expected arguments.

           :param provider: the provider to set up.
           :param args: mandatory and/or optional arguments
        """
        if not provider:
            print('Available modules:')
            self.show_modules()
            return
        try:
            module, classname = self._modules[provider]
            mod = import_module(module)
            pvdr_cls = getattr(mod, classname)
            if pvdr_cls.domains in self._providers:
                raise CmdShellError('Provider %s already set up' % provider)
            for arg in args:
                if '=' not in arg:
                    raise CmdShellError('Arguments should be specifed as '
                                        'key=value pairs')
        except KeyError:
            if self._debug:
                print_exc(chain=False, file=sys.stderr)
            raise CmdShellError('No such provider: %s' % provider)
        except ImportError:
            if self._debug:
                print_exc(chain=False, file=sys.stderr)
            raise CmdShellError('Cannot load module: %s' % module)
        except AttributeError:
            if self._debug:
                print_exc(chain=False, file=sys.stderr)
            raise CmdShellError('Cannot find provider: %s' % classname)
        except TypeError as ex:
            if self._debug:
                print_exc(chain=False, file=sys.stderr)
            raise CmdShellError('%s does not accept configuration: %s' %
                                (classname, ex))
        except NotImplementedError:
            if self._debug:
                print_exc(chain=False, file=sys.stderr)
            raise CmdShellError('Provider %s is not fully implemented' %
                                classname)
        except Exception as ex:
            if self._debug:
                print_exc(chain=False, file=sys.stderr)
            raise CmdShellError('Unmanaged error: %s' % ex)
        try:
            kwargs = dict([arg.split('=', 1) for arg in args])
            pvdr = pvdr_cls(**kwargs)
        except TypeError as ex:
            if self._debug:
                print_exc(chain=False, file=sys.stderr)
            error = str(ex).split(')', 1)[-1].strip()
            docs = []
            for par, default in self.document_provider_setup(pvdr_cls):
                if default is not None:
                    docs.append('%s[=%s]' % (par, default))
                else:
                    docs.append(par)
            doc = ' '.join(docs)
            raise CmdShellError('Invalid %s initialisation: %s\n  %s' %
                                (provider, error, doc))
        except Exception as ex:
            if self._debug:
                print_exc(chain=False, file=sys.stderr)
            raise CmdShellError('Cannot setup provider %s: %s' %
                                (provider, str(ex)))
        try:
            self.add_provider(pvdr)
        except Exception as ex:
            if self._debug:
                print_exc(chain=False, file=sys.stderr)
                raise

    def do_domain(self, domain):
        """Change the default domain.

           Switch to another domain, / being the root domain.

           Each provider uses a dedicated domain. When a domain is selected,
           the specified command line only applies to the current domain.

           When the root domain is selected, each command line should be
           prefixed with the short domain name to reach a specific command
           provider.

           :param domain: the new domain to default to
        """
        self._force_multi = domain == '/'
        if self._force_multi:
            self._curdomains = ('', '')
            self._set_prompt()
            return
        domain = domain.lower()
        for domains in self._providers:
            if domain in [dom.lower() for dom in domains]:
                self._curdomains = domains
                self._set_prompt()
                return

    def do_include(self, filename, *args):
        """Load a resource script by its name.

           :param filename: the path to the resource script to load.
           :param args: optional boolean to allow resuming normal execution
                        if some command fails in the subscript
        """
        resume_on_error = False
        if args:
            try:
                resume_on_error = to_bool(args[0])
            except ValueError:
                raise CmdShellError('Invalid resume argument')
        filename = filename.strip('"')
        if not filename.startswith(pathsep):
            if self._scripts:
                latest = self._scripts[-1]
                if isfile(latest):
                    filename = realpath(joinpath(dirname(latest),
                                                 filename))
        if not isfile(filename):
            raise CmdShellError('No such script: %s' % relpath(filename))
        with open(filename, 'rt') as rcfp:
            return self._load(rcfp, resume_on_error)

    def do_heal(self, error=None):
        """Clear out execution error status so that execution may resume as if
           no error had been previously triggered.

           :param error: if evaluated to a truth value, clear out the
                         last error as well
        """
        try:
            if to_bool(error):
                self._environ['_lasterror_'] = 0
        except ValueError:
            raise CmdShellError('%s not a valid value' % error)
        self._regular = True

    def do_history(self, line=None):
        """Show the command history."""
        if rl:
            max_items = 0
            if line:
                try:
                    max_items = int(line)
                except ValueError:
                    pass
            od = OrderedDict()
            for hpos in range(rl.get_current_history_length()):
                command = rl.get_history_item(hpos)
                if command in od:
                    del od[command]
                if max_items and (len(od) >= max_items):
                    od.popitem(last=False)
                od[command] = True
            for command in od:
                print(' ', command)

    def do_pause(self, delay=1.0):
        """Wait for a delay.

           :param delay: the delay in seconds before resuming execution
        """
        try:
            timeout = float(delay)
        except ValueError:
            raise CmdShellError('Invalid time value: %s' % delay)
        sleep(timeout)

    def do_filter(self, name, *values):
        """Apply a filter on variables.

           :param: values the name of variables to filter (not expanded)
           :return: the result of the filter
        """
        filters = {
            'min': (min, list),
            'max': (max, list),
            'sum': (sum, list),
            'count': (len, list),
            'avg': (lambda l: sum(l)/len(l), list),
        }
        try:
            func, kind = filters[name]
        except KeyError:
            raise CmdShellError(f"Unknown filter '{name}'")
        if not values:
            data = self._last_result
        else:
            data = flatten([self._environ[val] for val in values])
        if not isinstance(data, kind):
            raise CmdShellError(f'Invalid data type, expect {kind}')
        try:
            result = func(data)
        except Exception as exc:
            raise CmdShellError(f'Cannot apply filter: {exc}')
        print(f' {name}: {result}')
        return result

    def do_voice(self, enable):
        """Enable or disable voice.

           When voice is enabled, every command is spoken before being executed

           :param enable: if evaluate to true, enable voice speaking
        """
        if platform == 'darwin':
            try:
                self._speak = to_bool(enable.split()[0])
            except ValueError:
                raise CmdShellError('Invalid boolean: %s' % enable)
        else:
            print('Voice over not yet supported on %s' % platform)

    def do_say(self, line):
        """Speak the line.

           :param line: the command line to speak
        """
        self._say(line)

    def do_timestamp(self, tsname='', fmt='') -> None:
        """Show and optionally store the current time.

            Time format:

              * default format use hour:minute:second.milliseconds
              * ``iso`` format the timestamp according to ISO8601 format
              * ``utc`` same as ``iso`` format, using timezone code
              * ``short`` BCD-style string: YYMMDDHHMMSSmmm
              * ``epoch`` or ``ts`` seconds since Epoch (01/01/1970 00:00:00)
              * ``file`` for sort-friendly filename generation
              * or an arbitrary strftime formatter

           :param tsname: the variable name to store the current timestamp.
                          ``tsname`` is assigned the formatted string value,
                          except if epoch or default formatter where ``tsname``
                          is assigned the elapsed time since Epoch as a real
                          number
           :param fmt: optional format string
        """
        ts = now()
        now_sec = int(ts)
        now_ms = 1000*(ts-float(now_sec))
        if tsname:
            mo = self.VAR_CRE.match(tsname)
            if not mo:
                raise ValueError('Invalid value name: %s' % tsname)
        if not fmt:
            fmt = '%H:%M:%S'
            now_str = '%s.%03d' % (strftime('%H:%M:%S', localtime(now_sec)),
                                   now_ms)
            now_val = ts
        elif fmt == 'iso':
            fmt = '%Y-%m-%dT%H:%M:%S%z'
            now_str = strftime(fmt, localtime(ts))
            now_val = now_str
        elif fmt == 'utc':
            fmt = '%Y-%m-%dT%H:%M:%S%Z'
            now_str = strftime(fmt, localtime(ts))
            now_val = now_str
        elif fmt == 'short':
            fmt = '%y%m%d%H%M%S'
            now_str = ''.join((strftime(fmt, localtime(ts)),'%03d' % now_ms))
            now_val = now_str
        elif fmt in ('epoch', 'ts'):
            fmt = '%.3f'
            now_str = fmt % ts
            now_val = ts
        elif fmt == 'file':
            fmt = '%Y_%m_%d_%H_%M_%S'
            now_str = strftime(fmt, localtime(ts))
            now_val = now_str
        else:
            try:
                now_str = strftime(fmt.strip('"'), localtime(ts))
            except Exception as exc:
                raise CmdShellError('Invalid timestamp format')
            now_val = now_str
        print(now_str)
        if tsname:
            self._environ[tsname] = now_val

    def do_eval(self, *args):
        """Evaluate an expression.

           The result is stored in the default _ environment variable.

           :param args: the arguments of the expression to evaluate
        """
        result = eval(' '.join(args), self._environ, {'_': self._last_result})
        print(' %s' % result)
        return result

    def do_assert(self, expression):
        """Assert an expression.

           If the expression does not evaluate to the truth value, the command
           fails.

           :param expression: the expression to assert
        """
        line = expression.strip()
        if line.startswith('!'):
            invert = True
            line = line[1:].strip()
        else:
            invert = False
        if line == 'NIL':
            line = 'None'
        try:
            # Try to compare with a very simple syntax
            # (i.e. string, number, ...)
            simple = literal_eval(line)
            if simple is None:
                result = self._last_result is simple
            else:
                result = self._last_result == simple
        except Exception:
            # Maybe the syntax is more complex
            try:
                result = eval(line, self._environ,
                              {'_': self._last_result})
            except Exception as exc:
                self._dump_last_result()
                raise ValueError('Cannot eval: %s' % str(exc))
        if not xor(invert, bool(result)):
            self._dump_last_result()
            raise CmdShellError('Assertion failed')
        return self._last_result

    def do_expect(self, error=''):
        """Check that next executed command triggers an error.

           The executed command should not be a system one, i.e. all commands
           from providers can be tested.

           The triggered error message is compared with the specified error
           message. If the error message starts with the specified error,
           execution resumes. If the error message differs, or if no error is
           triggered, the execution stops and an execution error is raised.

           As a special case, if no error message is specified, any error
           message is considered as a valid error. Error message is case
           sensitive.

           :param error: the error message to test
        """
        error = error.strip()
        self._expect_error = literal_eval(error) if error else ''

    def _dump_last_result(self):
        if isinstance(self._last_result, set):
            result = list(sorted(self._last_result))
        else:
            result = self._last_result
        rstr = pformat(result, indent=4).lstrip('{[(').rstrip('}])')
        print('  last result:\n', rstr, file=sys.stderr)

    def do_prompt(self, comment='', timeout=None):
        """Prompt the user for input or resume after the specified timeout.

           If no timeout is specified, this command wait until the user hits
           the return key. The default _ variable is updated with the string
           provided by the user.

           If the timeout is 0, - or !, this command wait until any key is
           hit, the default _ variable is updated with the hit key.

           In other cases the execution resumes after the specicied timeout,
           if the user does not provide any input.

           :param comment: a comment that is ignored
           :param timeout: timeout in seconds
        """
        # skip the first argument which is considered as a comment
        if timeout:
            if timeout in '-!0':
                delay = 0
            else:
                try:
                    delay = float(timeout)
                except ValueError:
                    raise CmdShellError('Invalid timeout: %s' % timeout)
        else:
            delay = None
        if delay is None:
            while True:
                value = input(' > ')
                try:
                    value = literal_eval(value)
                    break
                except Exception:
                    value = value.strip()
                    if value:
                        break
        else:
            try:
                value = getkey(fullterm=False, timeout=delay or None)
            finally:
                cleanup_console()
            if value:
                try:
                    value = value.decode()
                except Exception:
                    pass
            else:
                value = ''
        return value

    def do_let(self, name, value, *values):
        """Defines a variable with one or more values.

           Each value may be an integer, a real number or a quoted string.

           If several values are specified, the generated variable is either
           a simple list, or if all values are specified as pairs using the
           full column separator, *i.e.* ``x:y``, the generated variable is
           a mapping.

           :param name: the name of the variable to assign/override
           :param value: the new value to assign
        """
        if not self.VAR_CRE.match(name):
            raise ValueError('Invalid value name: %s' % name)
        results = []
        vals = [value]
        vals.extend(values)
        mapping = [True for val in vals if val.count(',') == 1]
        if mapping:
            if len(mapping) != len(vals):
                raise ValueError('Invalid mixed mapping definition')
            vals = flatten([val.split(',', 1) for val in vals])
            mapping = True
        discards = set()
        for pos, val in enumerate(vals):
            if mapping:
                if (pos & 1) == 0:
                    # mapping mey
                    results.append(val)
                    continue
                if val == '':
                    # no value, remove item
                    discards.add(results.pop())
                    continue
            try:
                result = eval(val, self._environ, {'_': self._last_result})
            except SyntaxError:
                raise CmdShellError(f"Invalid syntax: '{val}'")
            except Exception as exc:
                raise ValueError(f'Invalid value: {exc}')
            results.append(result)
        results = [EasyFloat(r) if isinstance(r, float) else r
                   for r in results]
        if len(results) == 1:
            results = results[0]
        if mapping:
            results = EasyDict(group(results, 2))
            for discard in discards:
                del results[discard]
            print(results)
        self._environ[name] = results
        # do not alter the last result, except if name is the special variable
        if name == '_':
            return results
        return self._last_result

    def do_echo(self, *args):
        """Print the line.

           :param args: the line (as tokenized arguments) to verbatim print
        """
        def _replace_var(mobj):
            value = self._expand_env_var(mobj)
            if isinstance(value, (list, dict)):
                return pformat(value)
            return str(value)
        for arg in args:
            strarg = self.ENVVAR_CRE.sub(_replace_var, arg).strip('"')
            print('%s %s' % ('\n' if not self._debug else '', strarg))
        return self._last_result

    def do_count(self, *args):
        """Count the number of scalar items from an expression.

           The result is stored in the default _ environment variable.

           :param args: the arguments to evaluate
        """
        count = 0
        for arg in args:
            mobj = self.ENVVAR_CRE.match(arg)
            if mobj:
                value = self._expand_env_var(mobj)
                if not isinstance(value, str) and is_iterable(value):
                    count += len(value)
                    continue
            count += 1
        print(f' {count}')
        return count

    def do_report(self, line):
        """Report (speak) the last result.

           Any text preceding the $ sign is spoken before the result, any text
           following the $ sign is spoke after. This enable to speak the name
           of a value and its unit, for example.

           :param line: the prefix and suffix parts.
        """
        only = False
        if line:
            parts = line.split('$', 1)
            prefix = parts[0].rstrip()
            suffix = len(parts) > 1 and parts[1] or ''
            if '.' in line:
                prefix, only = prefix.split('.', 1)
                only = only.split()[0]
        if self._last_result:
            try:
                if isinstance(self._last_result, dict):
                    results = [' '.join([str(it) for it in item]) for item in
                               sorted(self._last_result.items())
                               if not only or item[0] == only]
                elif isinstance(self._last_result, str):
                    results = [self._last_result]
                for result in results:
                    result = str(result)
                    if line:
                        self._say(' '.join((prefix, result, suffix)))
                    else:
                        self._say(result)
            except Exception:
                if self._debug:
                    print_exc(chain=False, file=sys.stderr)
                raise
        return self._last_result

    def do_columns(self, *columns):
        """Names the column of a store.

           There is no action associated with this command, it is only used
           as syntactic sugar when saving store into CSV files, or to a plot
           if not legend is provided with the plot

           If no column name is specifed, any predefined column names are
           cleared out.

           :param columns: a list of column names
        """
        self._store_columns = list(filter(None, columns))
        return self._last_result

    def do_push(self, item=''):
        """Push/Append the last result as the last element(s) of the current
           line of the store.

           A store is an array of line, column similar to a spreadsheet, which
           can be used to store results as an array.

           * if the element to be pushed is a scalar, this element is appended
             to the line,
           * if the element is a vector, all its scalar values are appended to
             the line,
           * if the element is a mapping, it is flattened and its values are
             appended to the line. The mapping keys are used as the columns
             names if none have already been defined, or if they have been
             cleared.

           Each line of the store is made of a sequence of pushed values.

           See the store command to create a new line in the store.

           :param item: select an explicit item to be pushed rather than the
                        last result.
        """
        if item:
            try:
                value = self._environ[item]
            except KeyError:
                raise CmdShellError('No such variable: %s' % item)
        else:
            value = self._last_result
        if value is None:
            value = ''
        if isinstance(value, dict):
            mapping = flatten_dict(value)
            value = OrderedDict({k: mapping[k] for k in sorted(mapping)})
            if not self._store_columns:
                self._store_columns = value.keys()
            value = value.values()
        if not isinstance(value, str) and is_iterable(value):
            self._store[-1].extend(value)
        else:
            self._store[-1].append(value)
        cols = len(self._store[-1])
        if self._debug:
            print(' %d column%s in row' % (cols, plural(cols)))

    def do_store(self, line=None):
        """Create a new empty line buffer.

           Any existing line, whatever it actual column count, is pushed into
           the store.

           See the push command for details.
        """
        if not self._store[-1]:
            print(' empty row')
            return
        lines = len(self._store)
        print(' %d row%s in store' % (lines, plural(lines)))
        self._store.append([])

    def do_save(self, filename, flush=False, append=False):
        """Save the result store as a CSV file.

           The CSV filename is specified as the first argument.
           The second argument, if specified, tells whether the store should
           be cleared off, or preserved, after the file is saved.

           :param filename: the filename to save the store to as CSV content
           :param flush: whether to clear the store once the CSV file has been
                             created or preserve its content (default)
           :param append: if set, any existing CSV file content is preserved,
                          the store content is appended. Default is to
                          overwrite any previous file with the same filename.
        """
        if not filename:
            raise CmdShellError('Missing destination file name')
        try:
            flush = to_bool(flush, permissive=False)
        except ValueError:
            raise CmdShellError('Invalid flush option')
        try:
            append = to_bool(append, permissive=False)
        except ValueError:
            raise CmdShellError('Invalid append option')
        columns = max([len(line) for line in self._store] or [0])
        output = None
        if append:
            if not isfile(filename):
                append = False
            else:
                try:
                    print('File already exist:')
                    with open(filename, 'rt') as ofp:
                        output = StringIO(ofp.read())
                except Exception:
                    raise CmdShellError('Cannot append to existing store file '
                                        '%s' % filename)
        if not output:
            output = StringIO()
        try:
            if not append:
                colnames = list(self._store_columns)
                colnames = colnames[:columns]
                if len(colnames) < columns:
                    miscols = columns - len(colnames)
                    colnames.extend([chr(0x41+ix) for ix in range(miscols)])
                colnames.insert(0, '@')
                header = ','.join(colnames)
                print(header, file=output)
            for lix, vline in enumerate(self._store, start=1):
                if not vline:
                    break
                values = ['%d' % lix]
                for value in vline:
                    if isinstance(value, EasyFloat):
                        values.append(str(value))
                    elif isinstance(value, float):
                        values.append('%.3f' % value)
                    elif isinstance(value, str):
                        values.append(value)
                    else:
                        values.append(str(value))
                print(','.join(values), file=output)
            file_generator(self.normalize_path(filename),
                           lambda dst, src: dst.write(src.encode('utf8')),
                           output.getvalue())
            if flush:
                self._store.clear()
                self._store.append([])
        except Exception as ex:
            if self._debug:
                print_exc(chain=False, file=sys.stderr)
            raise CmdShellError('Cannot save results: %s' % ex)

    def do_flush(self, *count):
        """Discard the content of the store.

           :param count: how many line to discard (default: all)
        """
        if not count:
            self._store.clear()
        else:
            try:
                rows = to_int(count[0])
                if rows < 0:
                    raise ValueError()
            except ValueError:
                raise CmdShellError('Invalid row count')
            del self._store[-rows:]
        self._store.append([])

    def do_plot(self, *args):
        """Render the result store as a plot.

           The plot can be rendered inline (in the executing console) if the
           Terminal supports it, or displayed in the graphical environment if
           any.

           :param args: a list of column legend, if any. Use the column names
                        as legend if not is provided
        """
        try:
            from matplotlib import pyplot as pp
            from matplotlib import rc
            from numpy import array as nparray
        except ImportError as exc:
            print('Numpy/Matplotlib not available: %s' % exc)
            return
        if not self._store:
            return
        arrays = [list() for _ in range(len(self._store[0]))]
        legends = [arg.strip() for arg in args if arg]
        if not legends:
            legends = self._store_columns
        missing = len(arrays)-len(legends)
        if missing > 0:
            legends.extend(['' for _ in range(missing)])
        for vline in self._store:
            if not vline:
                break
            arit = iter(arrays)
            for value in vline:
                if isinstance(value, (float, int)):
                    next(arit).append(value)
                else:
                    next(arit).append(None)
        with pp.style.context(('dark_background')):
            rc('axes', edgecolor='xkcd:silver')
            rc('grid', color='xkcd:grey')
            rc('xtick', color='xkcd:grey')
            rc('ytick', color='xkcd:grey')
            background = (0.0, 0.0, 0.0, 1.0)
            pp.figure(figsize=(8, 5))
            axes = pp.axes()
            axes.get_yaxis().grid(True)
            axes.set_facecolor(background)
            colors = ('lime', 'magenta', 'wheat', 'turquoise', 'salmon',
                      'olive', 'azure', 'orangered')
            for arr, label, color in zip(arrays, legends, colors):
                pp.plot(nparray(arr), color='xkcd:%s' % color, marker='o',
                        label=label, linewidth=3.0)
            if any(legends):
                legend = pp.legend()
                legend.get_frame().set_facecolor(background)
            try:
                figformat = 'png'
                figdir = normpath(joinpath(dirname(argv[0]), pardir, pardir,
                                           'private'))
                figfd, figname = mkstemp(suffix='.%s' % figformat,
                                         dir=joinpath('private'))
                with open(figfd, 'wb') as figfp:
                    pp.savefig(figfp, format=figformat, transparent=True)
                check_call(('imgcat', figname))
                print('Figure path: %s' % relpath(figname))
            except Exception as exc:
                if self._debug:
                    print('Failed to save and display image: %s' % exc,
                          file=sys.stderr)
                    print_exc(chain=False, file=sys.stderr)
                pp.show()

    def do_logconf(self, filename, config, varname):
        """Save a configuration into a ini file.

           :param filename: the filename to create/update
           :param config: the configuration section to create/update
           :param var: the values to log
        """
        cfg = EasyConfigParser()
        if varname not in self._environ:
            raise CmdShellError('%s is not defined' % varname)
        values = self._environ[varname]
        if not isinstance(values, dict):
            if isinstance(values, list):
                if len(values) % 2:
                    raise CmdShellError('%s is not a valid config list' %
                                        varname)
                values = dict(group(values, 2))
            else:
                raise CmdShellError('%s is not a mapping type' % varname)
        if isdir(filename):
            raise CmdShellError('Config is a directory: %s' % filename)
        update = isfile(filename)
        if update:
            try:
                cfg.read(filename)
            except Exception as exc:
                raise CmdShellError('Cannot read back config %s' % filename)
        config = config.replace(' ','_')
        if not cfg.has_section(config):
            cfg.add_section(config)
        for vk, vv in values.items():
            if isinstance(vv, str):
                vv = self.ENVVAR_CRE.sub(self._replace_env_var, vv)
            cfg.set(config, str(vk), str(vv))
        output = StringIO()
        cfg.write(output)
        try:
            file_generator(filename,
                           lambda dst, src: dst.write(src.encode('utf8')),
                           output.getvalue())
        except Exception as exc:
            raise CmdShellError('Failed to %s config file %s' %
                                ('udpate' if update else 'create', filename))

    def do_load(self, filename, kind=None):
        """Load content or values from a file.

           :param filename: pathname to the file to read
           :param kind: type of file content

           ``kind`` may either be:

            * ``ini`` a INI file, where section names define the value encoding
               format, and each option define the valuf of an env. var.
              define the destination environment variable
            * ``csv`` a real CSV file, where first column define the name of
              an env. var. and the other columns define the value, w/o any
              format conversion. Resulting var is either a scalar or a vector,
              depending of the column count
            * ``hex`` a hex string file, whose content is stored in the last
              result value (``_``)
            * ``raw`` a binary file, whose content is stored in the last
              result value

            Value size/length is limited to 4KB each.

            Supported ini formats:
             * ``integer``, ``float``, ``bool``, ``hex``, ``text``
        """
        if not isfile(filename):
            raise CmdShellError(f'No such filename: {filename}')
        if kind is None:
            kind = splitext(filename)[1][1:]
        kind = kind.lower()
        if kind not in ('ini', 'hex', 'raw', 'csv'):
            raise CmdShellError(f'Unsupported file kind: {kind}')
        if kind == 'ini':
            cfg = EasyConfigParser()
            try:
                cfg.read(filename)
            except Exception as exc:
                raise CmdShellError(f'Cannot read ini file: {exc}')
            for section in cfg.sections():
                if section not in ('hex', 'integer', 'float', 'bool', 'text'):
                    continue
                for option in cfg.options(section):
                    if not self.VAR_CRE.match(option):
                        raise CmdShellError(f'Invalid name {option} in '
                                            f'{section}')
            if cfg.has_section('hex'):
                for option in cfg.options('hex'):
                    hstr = cfg.get('hex', option).strip().replace(' ', '')
                    try:
                        data = unhexlify(hstr)
                    except Exception as exc:
                        raise CmdShellError(f'Invalid hex data {option}')
                    if len(data) > 4<<10:
                        raise CmdShellError(f'Value too large {option}')
                    self._environ[option] = hstr
            if cfg.has_section('integer'):
                for option in cfg.options('integer'):
                    value = cfg.get('integer', option).strip().replace(' ', '')
                    try:
                        ival = to_int(value)
                    except Exception as exc:
                        raise CmdShellError(f'Invalid integer value {option}')
                    self._environ[option] = ival
            if cfg.has_section('float'):
                for option in cfg.options('float'):
                    value = cfg.get('float', option).strip()
                    try:
                        fvalue = float(value)
                    except Exception as exc:
                        raise CmdShellError(f'Invalid integer value {option}')
                    self._environ[option] = fvalue
            if cfg.has_section('bool'):
                for option in cfg.options('bool'):
                    value = cfg.get('bool', option).strip()
                    try:
                        bvalue = to_bool(value)
                    except Exception as exc:
                        raise CmdShellError(f'Invalid integer value {option}')
                    self._environ[option] = bvalue
            if cfg.has_section('text'):
                for option in cfg.options('text'):
                    value = cfg.get('text', option).strip()
                    if len(value) > 4<<10:
                        raise CmdShellError(f'String too large {option}')
                    self._environ[option] = value
            return
        if kind == 'csv':
            with open(filename, 'rt') as cfp:
                try:
                    for lpos, line in enumerate(csvreader(cfp)):
                        if not line:
                            continue
                        if len(line) < 2:
                            raise CmdShellError(f'Malformed line %s @ %d' %
                                                (line, lpos))
                        name = line[0]
                        if not self.VAR_CRE.match(name):
                            raise CmdShellError(f'Invalid name {name}')
                        values = line[1:]
                        if len(values) == 1:
                            self._environ[name] = values[0]
                        else:
                            self._environ[name] = values
                except ValueError:
                    raise CmdShellError(f'Invalid line {line} @ {lpos}')
            return
        if kind == 'raw':
            if stat(filename).st_size > 4<<10:
                raise CmdShellError('File too big: {filename}')
            with open(filename, 'rb') as rfp:
                data = rfp.read()
            hstr = hexlify(data)
            return hstr
        if kind == 'hex':
            if stat(filename).st_size > 16<<10:
                raise CmdShellError('File too big: {filename}')
            with open(filename, 'rt') as hfp:
                hstr = hfp.read()
            hstr = hstr.replace(' ', '').strip()
            try:
                data = unhexlify(hstr)
            except Exception as exc:
                raise CmdShellError('Invalid file content: {exc}')
            if len(data) > 4<<10:
                raise CmdShellError('File too big: {filename}')
            return hstr

    def complete_domain(self, *args):
        print()
        params = [x for x in args[1].split()]
        count = len(params)
        if count == 1 or ((count == 2) and (args[-2] != args[-1])):
            domains = ['/'] + list(self.short_domain(domains)
                                   for domains in self._providers)
            if count == 2:
                domains = [dom for dom in domains
                           if dom.startswith(params[1])]
            return domains

    @classmethod
    def document_provider_setup(cls, pvdr_cls):
        sig = signature(pvdr_cls.__init__)
        docs = []
        for pos, (name, par) in enumerate(sig.parameters.items()):
            if pos == 0:
                continue
            if par.default != Parameter.empty:
                docs.append((name, par.default))
            else:
                docs.append((name, None))
        return docs

    @classmethod
    def build_short_doc(cls):
        docs = []
        for name, value in cls.__dict__.items():
            if not callable(value):
                continue
            if not name.startswith('do_'):
                continue
            try:
                docstr = value.__doc__.split(linesep)[0].rstrip('.')
            except AttributeError:
                docstr = ''
            name = name[3:]
            if name == 'history':
                if not rl:
                    continue
            docs.append((name, '', docstr))
        docs.sort()
        return docs

    def build_command_doc(self, func, args):
        try:
            docstr = func.__doc__
        except AttributeError:
            return None
        cmd = func.__name__.split('_', 1)[1]
        defargs = self.get_default_args(func)
        docs = self._build_command_doc(cmd, docstr, defargs)
        if not docs or cmd != 'setup' or not args:
            return docs
        # setup command is a special command whose arguments depend on the
        # actual provider. If the provider is found, replace the default setup
        # help with the help from the provider, if any
        provider = args[0]
        if provider in self._modules:
            modname, clsname = self._modules[provider]
            try:
                mod = import_module(modname)
                pvdr_cls = getattr(mod, clsname)
                pvdr_doc = pvdr_cls.__doc__
                if not pvdr_doc:
                    return [(provider, '', 'No help available')]
            except Exception as exc:
                if self._debug:
                    print_exc(file=sys.stderr)
                return [(provider, '', 'Cannot load help: %s' % exc)]
            init = getattr(pvdr_cls, '__init__', {})
            defargs = self.get_default_args(init)
            docs = self._build_command_doc(' '.join([cmd, provider]),
                                           pvdr_cls.__doc__, defargs,
                                           pvdr_cls.domains)
        return docs

    @classmethod
    def _build_command_doc(cls, cmd, docstr, defargs, domains=None):
        parcre = recompile(r'^\s*:param (\w+)\s*:(.*)$')
        docs = []
        params = []
        param_cont = 0
        for line in docstr.split(linesep):
            line_info = line.lstrip()
            mo = parcre.match(line_info)
            if mo:
                param_cont = line.find(':', line.find(':'))
                pname = mo.group(1).strip()
                pdoc = mo.group(2).strip()
                params.append([pname, pdoc])
                continue
            else:
                indent = len(line) - len(line_info)
                if indent < param_cont:
                    param_cont = 0
                elif param_cont:
                    params[-1][1] = ' '.join([params[-1][1],
                                              line_info.rstrip()])
                    continue
            line = line_info.rstrip()
            if not docs:
                # skip all first empty lines
                if not line_info:
                    continue
            elif not line_info:
                # collapse multiple empty lines into a single one
                if not docs[-1].lstrip():
                    continue
            docs.append(line)
        pnames = [param[0] for param in params]
        if pnames:
            maxplen = max([len(param) for param in pnames])
            for pname, pdoc in params:
                # use non breaking space to prevent formatting
                pfname = pname.join('[]' if pname in defargs else '<>')
                parts = [pfname, ':', u'\u00a0' * (maxplen-len(pname)+1), pdoc]
                docs.append(''.join(parts))
                if pname in defargs:
                    if defargs[pname] not in (None, ''):
                        docs.append(
                            ''.join([' ' * maxplen,
                                     '(default: %s)' % defargs[pname]]))
                docs.append(linesep)
        # remove trailing empty lines
        while docs[-1] == linesep:
            docs.pop()
        if domains:
            docs.append('')
            domains = tuple(reversed(domains[:2]))
            docs.append('>> "%s" domain or "%s" for short' % domains)
        return [(cmd,
                 ' '.join([pname.join('[]' if pname in defargs else '<>')
                           for pname in pnames]),
                 linesep.join(docs))]

    def _say(self, line):
        if platform == 'Darwin':
            if line.startswith('-'):
                line = ' %s' % line
            args = ('say', '-v', 'Daniel', '%s' % line)
            call(args)

    # --- Quit / EOF

    _help_quit = [('quit', '', 'Exit the program')]
    _help_exit = _help_quit
    _help_EOF = _help_quit


class CmdShellProvider:
    """Abstract base class for command providers
    """

    CRE = recompile(r'(?m)(?:^|\s+)class\s+(?P<class>\w+)\s*\((?:\s*\w+,)*'
                    r'\s*CmdShellProvider\s*'
                    r'(?:,\s*\w+\s*)*\)\s*:\s')

    @classproperty
    def domains(cls):
        """Provide the domain(s) this provider supports

            :return: domain name(s)
            :rtype: str or tuple(str)
        """
        raise NotImplementedError('Abstract base class')

    @classproperty
    def containers(cls):
        """Enumerate the supported command handlers

            :return: a list of command shell command handers
            :rtype: list(CmdShellCommand)
        """
        raise NotImplementedError('Abstract base class')

    @property
    def context(self):
        """Provice command containers' initiliasation parameters

            :return: a map of parameters to initialize all command containers
            :rtype: dict
        """
        return {}

    def finalize(self):
        """Optional finalization method"""
        pass

    @staticmethod
    def enumerate_containers(class_, name):
        containers = []
        module = modules[name]
        for name in dir(module):
            subcls = getattr(module, name)
            if not isinstance(subcls, type):
                continue
            if not issubclass(subcls, class_):
                continue
            if subcls != class_:
                containers.append(subcls)
        return containers


class CmdShellPathCompleter:
    """Helper to auto-complete paths
    """

    def complete(self, text):
        pattern = ''.join((text, '*'))
        completions = []
        for path in glob(pattern):
            if path and isdir(path) and not path.endswith(pathsep):
                path = ''.join((path, pathsep))
            completions.append(path)
        return completions
