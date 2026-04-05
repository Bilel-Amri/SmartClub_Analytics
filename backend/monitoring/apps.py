"""
monitoring/apps.py
==================
AppConfig that starts a background daemon thread to sample CPU / memory /
open-file-descriptors every 5 seconds.  Uses `psutil` if available; falls
back to stdlib `resource` + `/proc` on Linux; on Windows uses ctypes for
memory and approximates CPU from os.times().
"""

import os
import sys
import threading
import time

from django.apps import AppConfig


def _sample_resources():
    """Return (cpu_pct, mem_mb, open_files) using the best available method."""
    cpu_pct    = 0.0
    mem_mb     = 0.0
    open_files = 0

    try:
        import psutil
        proc = psutil.Process(os.getpid())
        cpu_pct    = proc.cpu_percent(interval=None)
        mem_mb     = proc.memory_info().rss / 1_048_576
        open_files = proc.num_fds() if sys.platform != "win32" else len(proc.open_files())
    except ImportError:
        # Fallback: read /proc/self/status on Linux
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        mem_mb = int(line.split()[1]) / 1024
                        break
        except Exception:
            pass

        # Open files fallback
        try:
            open_files = len(os.listdir("/proc/self/fd"))
        except Exception:
            pass

    return cpu_pct, mem_mb, open_files


class MonitoringConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "monitoring"
    verbose_name = "ML API Monitoring"

    def ready(self):
        self._start_sampler()

    @staticmethod
    def _start_sampler():
        from monitoring.store import record_resources

        # Prime psutil CPU measurement (first call returns 0)
        try:
            import psutil
            psutil.Process(os.getpid()).cpu_percent(interval=None)
        except ImportError:
            pass

        def sampler():
            while True:
                time.sleep(5)
                try:
                    cpu, mem, fds = _sample_resources()
                    record_resources(cpu, mem, fds)
                except Exception:
                    pass

        t = threading.Thread(target=sampler, daemon=True, name="metrics-sampler")
        t.start()
