import os
from pathlib import Path


CGROUPS_ROOT = Path("/sys/fs/cgroup")


class Cgroup:
    def __init__(self, name, subsystems=("cpu", "memory")):
        self._subsystems = subsystems
        self._name = name

        for subsystem in self._subsystems:
            os.makedirs(self._subsystem_path(subsystem), exist_ok=True)

    def _subsystem_path(self, subsystem):
        return CGROUPS_ROOT / subsystem / "enki" / self._name

    def set_memory_limit(self, bs):
        assert "memory" in self._subsystems

        bs = bs & 0xfffffffffffff000  # align to the page boundary

        with open(self._subsystem_path("memory") / "memory.limit_in_bytes", "w") as f:
            print(bs, file=f)

    def set_cfs_limits(self, period, quota):
        assert "cpu" in self._subsystems

        with open(self._subsystem_path("cpu") / "cpu.cfs_period_us", "w") as f:
            print(period, file=f)

        with open(self._subsystem_path("cpu") / "cpu.cfs_quota_us", "w") as f:
            print(quota, file=f)

    def attach_me(self):
        pid = os.getpid()
        for subsystem in self._subsystems:
            with open(self._subsystem_path(subsystem) / "tasks", "w") as f:
                print(pid, file=f)

    def remove(self):
        for subsystem in self._subsystems:
            os.rmdir(self._subsystem_path(subsystem))
