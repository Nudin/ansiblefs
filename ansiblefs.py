#!/usr/bin/env python

#    Copyright (C) 2001  Jeff Epler  <jepler@unpythonic.dhs.org>
#    Copyright (C) 2006  Csaba Henk  <csaba.henk@creo.hu>
#
#    This program can be distributed under the terms of the GNU LGPL.
#    See the file COPYING.
#

from __future__ import print_function

import getpass
import inspect
import logging
import os
import sys
import traceback
from errno import EACCES, EINVAL, EOPNOTSUPP
from stat import *

from ansible_vault import Vault

logging.basicConfig(filename="ansiblefs.log", level=logging.WARNING)


def my_handler(type, value, tb):
    for line in traceback.TracebackException(type, value, tb).format(chain=True):
        logging.exception(line)
    logging.exception(value)
    logging.exception(inspect.currentframe())
    # logging.exception("Uncaught exception: {0}".format(str(value)))


# Install exception handler
sys.excepthook = my_handler


# pull in some spaghetti to make this stuff work without fuse-py being installed
try:
    import _find_fuse_parts
except ImportError:
    pass
import fuse
from fuse import Fuse

if not hasattr(fuse, "__version__"):
    raise RuntimeError(
        "your fuse-py doesn't know of fuse.__version__, probably it's too old."
    )

fuse.fuse_python_api = (0, 2)

fuse.feature_assert("stateful_files", "has_init")


def flag2mode(flags):
    md = {os.O_RDONLY: "rb", os.O_WRONLY: "wb", os.O_RDWR: "wb+"}
    m = md[flags & (os.O_RDONLY | os.O_WRONLY | os.O_RDWR)]

    if flags & os.O_APPEND:
        m = m.replace("w", "a", 1)

    return m


class AnsibleFS(Fuse):
    def __init__(self, root, *args, **kw):
        Fuse.__init__(self, *args, **kw)
        self.root = os.path.abspath(root)

    def getattr(self, path):
        return os.lstat("." + path)

    def readlink(self, path):
        return os.readlink("." + path)

    def readdir(self, path, offset):
        for e in os.listdir("." + path):
            yield fuse.Direntry(e)

    def unlink(self, path):
        os.unlink("." + path)

    def rmdir(self, path):
        os.rmdir("." + path)

    def symlink(self, path, path1):
        os.symlink(path, "." + path1)

    def rename(self, path, path1):
        os.rename("." + path, "." + path1)

    def link(self, path, path1):
        os.link("." + path, "." + path1)

    def chmod(self, path, mode):
        os.chmod("." + path, mode)

    def chown(self, path, user, group):
        os.chown("." + path, user, group)

    # TODO
    def truncate(self, path, length):
        f = open("." + path, "a", encoding="UTF-8")
        f.truncate(length)
        f.close()

    def mknod(self, path, mode, dev):
        os.mknod("." + path, mode, dev)

    def mkdir(self, path, mode):
        os.mkdir("." + path, mode)

    def utime(self, path, times):
        os.utime("." + path, times)

    def access(self, path, mode):
        if not os.access("." + path, mode):
            return -EACCES

    def statfs(self):
        """
        Should return an object with statvfs attributes (f_bsize, f_frsize...).
        Eg., the return value of os.statvfs() is such a thing (since py 2.2).
        If you are not reusing an existing statvfs object, start with
        fuse.StatVFS(), and define the attributes.

        To provide usable information (ie., you want sensible df(1)
        output, you are suggested to specify the following attributes:

            - f_bsize - preferred size of file blocks, in bytes
            - f_frsize - fundamental size of file blcoks, in bytes
                [if you have no idea, use the same as blocksize]
            - f_blocks - total number of blocks in the filesystem
            - f_bfree - number of free blocks
            - f_files - total number of file inodes
            - f_ffree - nunber of free file inodes
        """

        return os.statvfs(".")

    def fsinit(self):
        os.chdir(self.root)

    class XmpFile:
        def __init__(self, path, flags, *mode):
            self.flags = flags
            self.mode = mode
            self.path = path
            self.file_path = "." + path
            logging.debug(
                "# New file object %s %s %s %s", path, flags, *mode, flag2mode(flags)
            )
            self.file = os.fdopen(
                os.open(self.file_path, flags, *mode), flag2mode(flags)
            )
            self.fd = self.file.fileno()

        def read(self, length, offset):
            logging.debug(
                "read file %s %s %s", self.file, self.file.name, self.file.mode
            )
            if length:
                end = offset + length
            else:
                end = None
            self.file.seek(0)
            encrypted = self.file.read()
            self.file.seek(0)
            logging.debug("Read encrypted: %s…", encrypted[:10])
            content = self.vault.load_raw(encrypted)
            logging.debug("Read raw: %s…", content[:10])
            return content[slice(offset, end)]

        def write(self, buf, offset):
            try:
                logging.debug(
                    "write %s %s %s %s(%s)",
                    buf,
                    offset,
                    self.mode,
                    self.flags,
                    flag2mode(self.flags),
                )
                if "a" in self.file.mode:
                    flags = (self.flags - os.O_APPEND) & ~os.O_WRONLY | os.O_RDWR
                    mode = flag2mode(flags)
                    f = os.open(self.file_path, flags)
                    file = os.fdopen(f, mode)
                    self.file.close()
                    self.file = file

                if offset != 0:
                    old_plaintext = self.read(None, 0)
                    logging.debug(" old content: %s", old_plaintext)
                else:
                    old_plaintext = b""
                new_plaintext = old_plaintext + buf
                logging.debug(" new content: %s", new_plaintext)
                encrypted = self.vault.dump_raw(new_plaintext).encode()
                logging.debug(" new encrypted: %s…", encrypted[0:50])
                self.file.seek(0)
                rc = self.file.write(encrypted)
                logging.debug("end write rc: %s", rc)
                return len(buf)
            except Exception as e:
                logging.error(e)

        def release(self, _flags):
            self.file.close()

        def _fflush(self):
            if "w" in self.file.mode or "a" in self.file.mode:
                self.file.flush()

        def fsync(self, isfsyncfile):
            self._fflush()
            if isfsyncfile and hasattr(os, "fdatasync"):
                os.fdatasync(self.fd)
            else:
                os.fsync(self.fd)

        def flush(self):
            self._fflush()
            # cf. xmp_flush() in fusexmp_fh.c
            os.close(os.dup(self.fd))

        def fgetattr(self):
            return os.fstat(self.fd)

        # TODO
        def ftruncate(self, length):
            logging.debug("ftruncate")
            logging.debug(inspect.currentframe())
            self.file.truncate(length)

    def main(self, *a, **kw):
        self.vault = Vault(self.password)
        self.file_class = self.XmpFile
        self.file_class.vault = self.vault

        return Fuse.main(self, *a, **kw)


def main():

    usage = (
        """
Userspace nullfs-alike: mirror the filesystem tree from some point on.

"""
        + Fuse.fusage
    )

    vault_dir = sys.argv[1]
    server = AnsibleFS(
        vault_dir,
        version="%prog " + fuse.__version__,
        usage=usage,
        dash_s_do="setsingle",
    )

    server.parser.add_option(
        mountopt="password",
        metavar="PASSWORD",
        help="Password of the vaults",
    )
    server.parse(values=server, errex=1)
    if "password" not in dir(server):
        server.password = getpass.getpass()

    try:
        if server.fuse_args.mount_expected():
            os.chdir(server.root)
    except OSError:
        print("can't enter root of underlying filesystem", file=sys.stderr)
        sys.exit(1)

    server.main()


if __name__ == "__main__":
    main()
