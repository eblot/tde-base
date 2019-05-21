"""
Filter an input stream to detect MIME encoding scheme used by the target to
send binary content to the host over the serial ASCII line. If a MIME header is
detected, it automatically decodes and writes to a local file (in the current
directory) the binary data. MIME data are not shown, but replaced with a
completion indicator showing the progression of the transmission, and the ETA.

If a MD5 checksum is detected in the MIME header (as per RFC1864), a checksum
is computed on received data, and both checksums (board, host) are compared
once the binary data transfer is over. A checksum mismatch (which indicates
a corrupted binary stream) is signalled to the user.

It can also autodetect Zlib encoded stream (deflate algorithm). When such a
stream compression is detected, this script performs on-the-fly decompression
of the stream, and store the inflated, original binary stream in the
destination file.
"""

import base64
import binascii
import os
import re
import time
import sys

__all__ = ['FilterMime']

# Hints for PyLint:
#   catch Exception, too few public methods
#pylint: disable-msg=W0703
#pylint: disable-msg=R0903


class FilterMime:
    """
    Extracts, decodes and decompresses a binary file sent over the serial line
    """
    (MIME_IDLE, MIME_HEADER, MIME_DATA) = range(3)

    def __init__(self, outdir=None, verbose=True):
        # MIME transfer marker: 0: no MIME, 1: MIME header, 2: MIME data
        self._state = self.MIME_IDLE
        # MIME file
        self._file = None
        # Expected file length
        self._length = 0
        # Received bytes
        self._count = 0
        # Start time
        self._start = False
        # MD checksum for data transfer
        self._checksum = None
        # Message Digest object
        self._md = None
        # ZLIB compression
        self._zstream = None
        # Output path for received files
        self._outdir = outdir or os.curdir
        # Whether to display Download progress or not
        self._verbose = verbose
        # Various RE to parse input stream
        ctere = r'^Content-Transfer-Encoding: (.*)'
        self.ctecre = re.compile(ctere, re.IGNORECASE)
        ctyre = r'^Content-Type:\s([\w\d\-]+\/[\w\d\-]+)(;\s)?(?:name=(.*))$'
        self.ctycre = re.compile(ctyre, re.IGNORECASE)
        ctlre = r'^Content-Length:\s(\d+)$'
        self.ctlcre = re.compile(ctlre, re.IGNORECASE)
        ctdre = r'^Content-SHA1:\s([A-Za-z0-9\+\/]+={0,2})$'
        self.ctdcre = re.compile(ctdre, re.IGNORECASE)
        ctcre = r'^Content-coding:\sdeflate$'
        self.ctccre = re.compile(ctcre, re.IGNORECASE)
        mimre = r'^[A-Za-z0-9\+\/=]+$'
        self.mimcre = re.compile(mimre)

    def inject(self, string):
        """Inject a string into the formatter"""
        ctemo = self.ctecre.match(string)
        if ctemo:
            if ctemo.group(1).strip().lower() != 'base64':
                print('MIME encoding "%s" not supported' %
                      ctemo.group(1), file=sys.stderr)
                self._reset()
                return False
            return True

        # Retrieves the name of the file, and open a file for writing
        ctymo = self.ctycre.match(string)
        if ctymo:
            mimefile = ctymo.group(3)
            if not os.path.isdir(self._outdir):
                try:
                    os.makedirs(self._outdir)
                except Exception:
                    print("Unable to create host dir %s, falling back to %s"
                          % (self._outdir, os.curdir), file=sys.stderr)
                    self._outdir = os.curdir
            if '/' in mimefile:
                mimedir = os.path.dirname(mimefile)
                destdir = os.path.join(self._outdir, mimedir)
                if not os.path.isdir(destdir):
                    try:
                        os.makedirs(destdir)
                    except Exception:
                        print("Unable to create output dir %s, "
                              "falling back to %s"
                              % (destdir, self._outdir), file=sys.stderr)
                        destdir = self._outdir
            mimefile = os.path.join(self._outdir, mimefile)
            self._file = open(mimefile, "wb")
            if self._file:
                self._state = self.MIME_HEADER
                self._count = 0
                self._start = time.time()
                if self._verbose:
                    print('[Saving file as %s]' % mimefile)
            return True

        # Retrieves the length of the file
        ctlmo = self.ctlcre.match(string)
        if ctlmo:
            self._length = int(ctlmo.group(1))
            return True

        # Hash checksum is always encoded with Base64, see RFC1864
        # do not decode it, as local checksum can generate a
        # Base64-encoded checksum, without the padding byte(s)
        ctdmo = self.ctdcre.match(string)
        if ctdmo:
            import hashlib
            self._md = hashlib.sha1()
            self._checksum = ctdmo.group(1)
            return True

        # Data transfer is compressed using the ZLIB library
        ctdmo = self.ctccre.match(string)
        if ctdmo:
            import zlib
            self._zstream = zlib.decompressobj()
            return True

        # no MIME transfer detected
        if not self._state:
            return False

        # start/stop condition (empty line)
        if not string.strip():
            # first occurence: start condition
            if self._state == self.MIME_HEADER:
                self._state = self.MIME_DATA
                return True
            # second occurence: stop condition
            elif self._state == self.MIME_DATA:
                if self._verbose:
                    print('')
                # padding+line endings tolerance
                if abs(self._length - self._count) > 2:
                    print('Warning: %d/%d bytes received' %
                          (self._length, self._count))
                self._file.close()
                # now verify the received data
                if self._md:
                    # compare b64 encoded strings
                    checksum = base64.b64decode(self._checksum)
                    digest = self._md.digest()
                    if checksum != digest:
                        print("ERROR: SHA1 checksums do not match:")
                        print("  remote: %s" % binascii.hexlify(checksum))
                        checksum = base64.b64encode(digest)
                        print("  local:  %s" % binascii.hexlify(digest))
                        print("Corrupted binary data")
                    else:
                        if self._verbose:
                            print("Data integrity verified OK")
                else:
                    print("No checksum received, cannot verify data integrity")
                self._reset()
                return True
            # get ready for next file
            self._reset()
            return False

        # No MIME data on this line
        if self._state != self.MIME_DATA:
            return False

        # MIME data
        mimmo = self.mimcre.match(string)
        if mimmo:
            data = base64.b64decode(string)
            self._md and self._md.update(data)
            if self._zstream:
                try:
                    zoutput = self._zstream.decompress(data)
                    self._file.write(zoutput)
                except Exception:
                    print("Unable to inflate ZLIB stream, storing raw data",
                          file=sys.stderr)
                    if self._md:
                        print(" SHA-1 digest won't match", file=sys.stderr)
                    # be conservative: disable Zlib inflation and keep data
                    # without any alteration
                    self._zstream = None
                    self._file.write(data)
            else:
                self._file.write(data)
            self._count += len(string)+2 # CR/LF filtered out
            if self._length:
                if self._count < self._length:
                    tc = time.time()
                    elap = tc-self._start
                    tt = (elap*self._length)//self._count
                    eta = self._start+tt-tc
                    if eta < 0:
                        eta = 0
                    etam = int(eta//60)
                    etas = eta-(etam*60)
                else:
                    etam = etas = 0
                if self._verbose:
                    print("\rRX: %02.1f%% ETA %02d'%02d\"" %
                        ((min(100.0,(100*self._count)//self._length)),
                        etam, etas), end=' ')
            else:
                if self._verbose:
                    print("\rRX: %u bytes" % self._count)
            sys.stdout.flush()
            return True
        else:
            print("\nERROR in MIME transfer: [%s]" % string)
            self._reset()
            return False

    def _reset(self):
        """Reset the current state of the filter"""
        if self._file:
            self._file.close()
            self._file = None
        self._state = self.MIME_IDLE
        self._length = 0
        self._md = None
        self._zstream = None

if __name__ == '__main__':
    def unittest():
        """Simple unit test"""
        print("Processing Base64 stream from stdin...")
        filtermime = FilterMime()
        for line in sys.stdin.readlines():
            line = line.strip('\r\n')
            r = filtermime.inject(line)
            if not r:
                print("Unmanaged: [%s]" % line)
    unittest()
