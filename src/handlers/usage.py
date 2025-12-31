import asyncio
import os
import time
import shutil


class UsageHandler:
    def __init__(self):
        # Auto-detect cgroup version
        self.cgroup_v2 = os.path.isfile("/sys/fs/cgroup/cgroup.controllers")

        # State for CPU calculation
        self._cpu_last_usage = 0
        self._cpu_last_system_time = 0
        self._first_run = True

    @staticmethod
    def _read_file_sync(path):
        """Blocking file read helper to be run in a thread."""
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except FileNotFoundError:
            return None

    async def get_cpu_percent(self) -> float:
        """
        Returns CPU usage percentage relative to 1 core.
        (e.g., 50.0 = 0.5 cores, 200.0 = 2 cores)
        """
        current_time = time.time() * 1e9  # nanoseconds

        # 1. Read current usage from cgroups
        if self.cgroup_v2:
            content = await asyncio.to_thread(self._read_file_sync, "/sys/fs/cgroup/cpu.stat")
            if not content: return 0.0

            # Parse 'usage_usec' key
            total_usage = 0
            for line in content.split('\n'):
                if line.startswith("usage_usec"):
                    total_usage = int(line.split()[1]) * 1000  # Convert to nanoseconds
                    break
        else:
            content = await asyncio.to_thread(self._read_file_sync, "/sys/fs/cgroup/cpuacct/cpuacct.usage")
            total_usage = int(content) if content else 0

        # 2. Calculate Delta
        usage_delta = total_usage - self._cpu_last_usage
        time_delta = current_time - self._cpu_last_system_time

        # 3. Update State
        self._cpu_last_usage = total_usage
        self._cpu_last_system_time = current_time

        # Handle first run or division by zero
        if self._first_run:
            self._first_run = False
            return 0.0
        if time_delta == 0:
            return 0.0

        # 4. Calculate Percentage
        # (Usage Delta / Time Delta) * 100
        return round((usage_delta / time_delta) * 100, 2)

    async def get_memory_usage(self) -> dict:
        """Returns dict with usage_mb, limit_mb, and percent."""
        if self.cgroup_v2:
            usage_path = "/sys/fs/cgroup/memory.current"
            limit_path = "/sys/fs/cgroup/memory.max"
        else:
            usage_path = "/sys/fs/cgroup/memory/memory.usage_in_bytes"
            limit_path = "/sys/fs/cgroup/memory/memory.limit_in_bytes"

        # Read files in thread pool
        usage_str = await asyncio.to_thread(self._read_file_sync, usage_path)
        limit_str = await asyncio.to_thread(self._read_file_sync, limit_path)

        if not usage_str:
            return {"usage_mb": 0, "limit_mb": 0, "percent": 0}

        usage_bytes = int(usage_str)
        limit_bytes = 0

        # Handle "max" or unlimited values
        if limit_str and limit_str != "max":
            val = int(limit_str)
            # Filter out standard "unlimited" large integers
            if val < 10 ** 15:
                limit_bytes = val

        usage_mb = usage_bytes / (1024 * 1024)
        limit_mb = limit_bytes / (1024 * 1024) if limit_bytes else 0

        percent = 0.0
        if limit_bytes > 0:
            percent = (usage_bytes / limit_bytes) * 100

        return {
            "usage_mb": round(usage_mb, 2),
            "limit_mb": round(limit_mb, 2) if limit_bytes else "Unlimited",
            "percent": round(percent, 2)
        }

    async def get_disk_usage(self) -> dict:
        """Returns disk usage for the container's root filesystem."""
        # shutil.disk_usage is blocking, run in thread
        total, used, free = await asyncio.to_thread(shutil.disk_usage, "/")

        return {
            "used_gb": round(used / (1024 ** 3), 2),
            "total_gb": round(total / (1024 ** 3), 2),
            "percent": round((used / total) * 100, 2)
        }
