import ctypes
import os
from functools import wraps


CLONE_NEWCGROUP = 0x02000000
CLONE_NEWIPC = 0x08000000
CLONE_NEWNET = 0x40000000
CLONE_NEWNS = 0x00020000
CLONE_NEWPID = 0x20000000
CLONE_NEWUSER = 0x10000000
CLONE_NEWUTS = 0x04000000
MS_BIND = 4096
MS_RDONLY = 1


_libc = ctypes.CDLL("libc.so.6")
_libc.mount.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p)
_libc.umount.argtypes = (ctypes.c_char_p,)
_libc.sethostname.argtypes = (ctypes.c_char_p, ctypes.c_size_t)
_libc.setns.argtypes = (ctypes.c_int, ctypes.c_int)
_libc.__errno_location.restype = ctypes.POINTER(ctypes.c_int)


def _syscall():
    def _decorator(f):
        @wraps(f)
        def decorated_function(*args, ignore_errno=False, **kwargs):
            ret = f(*args, **kwargs)
            errno = _libc.__errno_location().contents.value
            if not ignore_errno and ret < 0:
                raise OSError(errno, "{}({}, {}): {}".format(f.__name__, args, kwargs, os.strerror(errno)))

        return decorated_function
    return _decorator


@_syscall()
def unshare(flags):
    return _libc.unshare(flags)


@_syscall()
def setns(fd, nstype):
    return _libc.setns(fd, nstype)


@_syscall()
def mount(source, target, fs=None, options=0, data=None):
    if data is not None:
        data = data.encode()
    if fs is not None:
        fs = fs.encode()
    return _libc.mount(source.encode(), target.encode(), fs, options, data)


@_syscall()
def umount(target):
    return _libc.umount(target.encode())


@_syscall()
def sethostname(hostname):
    hostname = hostname.encode()
    return _libc.sethostname(hostname, len(hostname))


def touch(path):
    with open(path, "w") as f:
        pass


UNITS = {
    "t": 2 ** 40,
    "g": 2 ** 30,
    "m": 2 ** 20,
    "k": 2 ** 10,
}


def parse_memory(s):
    if s is None:
        return None

    s = s.lower()
    if s.isdigit():
        return int(s)
    else:
        unit = s[-1:]
        return int(s[:-1]) * UNITS[unit]


def parse_cores(s):
    if s is None:
        return None

    if s[-1] != "c":
        raise ValueError("invalid cores count: '{}'".format(s))

    return float(s[:-1])
