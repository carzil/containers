import uuid
import os
import setproctitle
import pyroute2
from pyroute2 import IPRoute
from pathlib import Path
from .utils import *


DATA_DIR = Path("/var/lib/enki")
CONTAINERS_DIR = DATA_DIR / "containers"
IMAGES_DIR = DATA_DIR / "images"


class ContainerError(Exception):
    pass


def _get_parent_image(image):
    image_dir = IMAGES_DIR / image
    with open(image_dir / "parent") as f:
        return f.read().strip()


class Container:
    def __init__(self, id):
        self._id = id
        self._dir = CONTAINERS_DIR / self._id
        self._rootfs = self._dir / "rootfs"
        self._work_dir = self._dir / "workdir"
        self._upper_dir = self._dir / "image"
        self._netns = "enki_{}".format(self._id[:8])

        a = int(self._id[:2], 16)
        b = int(self._id[2:4], 16)
        self._ip = "172.16.{}.{}".format(a, b)

    @staticmethod
    def get_all():
        for container_id in os.listdir(CONTAINERS_DIR):
            yield Container(container_id)

    @staticmethod
    def create(self):
        return Container(id=str(uuid.uuid4()))

    def exists(self):
        return self._dir.exists()

    def active(self):
        return (self._dir / "pid").exists()

    def _mount_image(self, image_id):
        curr = image_id
        lowerdir_layers = [image_id]
        while True:
            parent = _get_parent_image(curr)
            if parent == "none":
                break
            lowerdir_layers.append(parent)
            curr = parent

        lowerdir_layers = map(lambda image_id: os.path.abspath(IMAGES_DIR / image_id / "data"), lowerdir_layers)
        lowerdir = ":".join(lowerdir_layers)

        mount(
            source="none",
            fs="overlay",
            target=os.path.abspath(self._rootfs),
            data="lowerdir={},upperdir={},workdir={}".format(
                lowerdir,
                os.path.abspath(self._upper_dir),
                os.path.abspath(self._work_dir),
            )
        )

    def _do_execve(self, command, args):
        os.execve(command, (os.path.basename(command),) + args, {})

    def _setup_net_on_host(self):
        pyroute2.netns.create(self._netns)
        ip = IPRoute()

        host_bridge = ip.link_lookup(ifname="enki0")
        if len(host_bridge) == 0:
            raise ContainerError("no enki0 bridge found on host device")
        host_bridge = host_bridge[0]

        host_veth_name = "veth0@{}".format(self._id[:8])
        self._container_veth_name = "veth1@{}".format(self._id[:8])

        ip.link("add", ifname=host_veth_name, peer=self._container_veth_name, kind="veth")

        self._host_veth_idx = ip.link_lookup(ifname=host_veth_name)[0]
        container_veth_idx = ip.link_lookup(ifname=self._container_veth_name)[0]
        ip.link("set", index=self._host_veth_idx, state="up")
        ip.link("set", index=self._host_veth_idx, master=host_bridge)
        ip.link("set", index=container_veth_idx, net_ns_fd=self._netns)

    def _setup_net_in_container(self):
        pyroute2.netns.setns(self._netns)
        ip = IPRoute()

        loopback = ip.link_lookup(ifname="lo")[0]
        ip.link("set", index=loopback, state="up")

        container_veth = ip.link_lookup(ifname=self._container_veth_name)[0]
        ip.link("set", index=container_veth, address="02:42:ac:11:00:{}".format(self._id[:2]))
        ip.addr("add", index=container_veth, address=self._ip, broadcast="172.16.0.255", prefixlen=16)
        ip.link("set", index=container_veth, state="up")
        ip.route("add", dst="default", gateway="172.16.0.1")

    def _setup_net_in_chroot(self):
        with open("/etc/resolv.conf", "w") as f:
            print("nameserver 8.8.8.8", file=f)

        with open("/etc/hosts", "w") as f:
            print("127.0.0.1 localhost", file=f)
            print("{} {}".format(self._ip, self._id), file=f)

    def _cleanup_host_net(self):
        ip = IPRoute()
        ip.link("del", index=self._host_veth_idx)

    def _container_trampoline(self, image_id, command, args, detach):
        if detach:
            fd = os.open(self._dir / "logs", os.O_WRONLY | os.O_CREAT, 0o600)

            try:
                os.dup2(fd, 1)
                os.dup2(fd, 2)
            finally:
                os.close(fd)

        rootfs = os.path.abspath(self._rootfs)

        self._mount_image(image_id)

        dev_dir = self._rootfs / "dev"
        pts_dir = dev_dir / "pts"
        os.makedirs(pts_dir, exist_ok=True)
        mount(source="devtmpfs", target=os.path.abspath(dev_dir), fs="devtmpfs")
        mount(source="devpts", target=os.path.abspath(pts_dir), fs="devpts")

        os.chroot(rootfs)
        os.chdir("/")

        os.makedirs("/proc", exist_ok=True)
        os.makedirs("/sys", exist_ok=True)
        mount("none", "/proc", "proc")
        mount("none", "/sys", "sysfs")

        sethostname(self._id)

        self._setup_net_in_chroot()

        self._do_execve(command, args)

    def run(self, image_id, command, args, detach):
        image_dir = IMAGES_DIR / image_id / "data"
        if not image_dir.exists():
            raise ContainerError("no such image: {}".format(image_id))

        os.makedirs(os.path.abspath(self._dir))
        os.makedirs(self._work_dir, exist_ok=True)
        os.makedirs(self._upper_dir, exist_ok=True)
        os.makedirs(self._rootfs, exist_ok=True)

        with open(self._dir / "image_id", "w") as f:
            print(image_id, file=f)

        self._setup_net_on_host()

        if detach:
            if os.fork() == 0:
                os.close(0)
            else:
                return

        unshare(CLONE_NEWCGROUP | CLONE_NEWIPC | CLONE_NEWNS | CLONE_NEWPID | CLONE_NEWUTS)
        self._pid = os.fork()
        if self._pid == 0:
            self._setup_net_in_container()
            self._container_trampoline(image_id, command, args, detach)
            exit(1)
        else:
            with open(str(self._dir / "pid"), "w") as f:
                print(self._pid, file=f)

            try:
                setproctitle.setproctitle("enki: watcher for {}".format(self._id))
                os.waitpid(self._pid, 0)
                if detach:
                    exit(0)
            finally:
                self._cleanup()

    def _setns_from_pid(self, ns, pid):
        with open("/proc/{}/ns/{}".format(pid, ns)) as f:
            setns(f.fileno(), 0)

    def exec(self, command, args, detach):
        if not self.exists():
            raise ContainerError("no such container: {}".format(self._id))

        if not (self._dir / "pid").exists():
            raise ContainerError("container {} is not running".format(self._id))

        with open(self._dir / "pid") as f:
            container_pid = int(f.read().strip())

        for ns in ("cgroup", "ipc", "mnt", "net", "pid", "uts"):
            self._setns_from_pid(ns, container_pid)

        command_pid = os.fork()
        if command_pid == 0:
            pyroute2.netns.setns(self._netns)
            os.chroot(os.path.abspath(self._rootfs))
            os.chdir("/")
            self._do_execve(command, args)
        else:
            os.waitpid(command_pid, 0)


    def _cleanup(self):
        umount(str(self._rootfs / "dev" / "pts"), ignore_errno=True)
        umount(str(self._rootfs / "dev"), ignore_errno=True)
        umount(str(self._rootfs / "sys"), ignore_errno=True)
        umount(str(self._rootfs / "proc"), ignore_errno=True)
        umount(str(self._rootfs), ignore_errno=True)

        try:
            os.unlink(str(self._dir / "pid"))
        except OSError:
            pass

        self._cleanup_host_net()
        pyroute2.netns.remove(self._netns)

    @property
    def id(self):
        return self._id

    def logs_file(self):
        if not self.exists():
            raise ContainerError("no such container: {}".format(self._id))
        try:
            return open(self._dir / "logs", "rb")
        except FileNotFoundError:
            raise ContainerError("not logs found for container {}, is it running detached?".format(self._id))
