from os import getenv
from os.path import (dirname, isfile, isdir, join as joinpath, normpath,
                     pardir, sep)
from .misc import EasyConfigParser


class ResourceError(ValueError):
    """Base class for Resource errors"""


class Resources:
    """Simple network resource referencer

       :param config_file: specify an alternative configuration file to parse
    """

    def __init__(self, config_file=None):
        self._passwords = {}
        if not config_file:
            config_file = self.get_etc('resources.ini')
        if not isfile(config_file):
            raise ResourceError('Missing configuration file "%s"' %
                                config_file)
        self._cfgparser = EasyConfigParser()
        try:
            with open(config_file, 'rt') as config:
                self._cfgparser.readfp(config)
        except IOError as exc:
            raise ResourceError('Unable to read config file "%s": %s' %
                                (config_file, exc))

    @staticmethod
    def get_etc(filename=None, strict=True):
        """Returns the path to the 'etc' directory that contains template
           files and invariant configuration files.

           :param filename: if specified, the returned path is concatenated
                            with this filename
           :param strict: if set, existance of the resulting path is checked,
                          and a ResourceError is raised on failure
        """
        path = joinpath(dirname(__file__),
                        pardir, pardir, pardir, 'host', 'etc')
        if filename:
            path = joinpath(path, filename)
        path = normpath(path)
        if strict:
            if filename:
                if not isfile(path):
                    raise ResourceError('No such file: %s' % path)
            else:
                if not isdir(path):
                    raise ResourceError('No such dir: %s' % path)
        return path

    def get_hostname(self, feature, strict=True):
        """Return the FQDN of a host providing the specified feature

           :param feature: the feature to seek
           :param strict: raise a ResourceError if the service is not found
        """
        url = self._cfgparser.get('services', feature, None)
        if strict and not url:
            raise ResourceError('No such feature: %s' % feature)
        return url.strip()

    def get_domains(self, constraint, strict=True):
        """Return a list of valid domain names for the specified constraint

           :param constraint: a valid constraint, see configuration file
           :param strict: raise a ResourceError if the constraint is not found
        """
        urls = self._cfgparser.get('services', constraint, None)
        if strict and not urls:
            raise ResourceError('No such domain: %s' % constraint)
        return [x.strip() for x in urls.split(',')]

    def get_protocol(self, service, strict=True):
        """Return the communication protocol to use for the specified service

           :param service: the service to seek
           :param strict: raise a ResourceError if the service is not found
        """
        proto = self._cfgparser.get('protocols', service, None)
        if strict and not proto:
            raise ResourceError('No such service: %s' % service)
        return proto.strip()

    def build_url(self, service, feature, path=''):
        """Build a network URL for the specified service

           :param service: the service to use
           :param feature: the feature to seek
           :param path: if defined, the path is concatenated to the URL
           :param strict: raise a ResourceError on Error
        """
        proto = self.get_protocol(service)
        svc = self.get_hostname(feature)
        path = path.lstrip('/')
        return '%s://%s/%s' % (proto, svc, path)
