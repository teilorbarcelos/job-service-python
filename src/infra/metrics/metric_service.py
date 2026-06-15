import asyncio
import logging
from typing import Any

from prometheus_client import REGISTRY, Counter, Gauge, Histogram

logger = logging.getLogger("metrics")


class MetricService:
    _metrics: dict[str, Any] = {}

    def _get_or_create_counter(self, name: str, labelnames: list[str]) -> Counter:
        if name not in self._metrics:
            collector = REGISTRY._names_to_collectors.get(name)
            if collector and type(collector).__name__ not in ("ProcessCollector", "GCCollector", "PlatformCollector"):
                self._metrics[name] = collector
            else:
                if collector:
                    try:
                        REGISTRY.unregister(collector)
                    except KeyError:
                        pass
                self._metrics[name] = Counter(name, f"Total count of {name}", labelnames=labelnames)
        return self._metrics[name]

    def _get_or_create_histogram(self, name: str, labelnames: list[str]) -> Histogram:
        if name not in self._metrics:
            collector = REGISTRY._names_to_collectors.get(name)
            if collector:
                self._metrics[name] = collector
            else:
                self._metrics[name] = Histogram(name, f"Duration of {name}", labelnames=labelnames)
        return self._metrics[name]

    def set_db_pool_metrics(self, pool):
        gauge_size = self._get_or_create_gauge("db_pool_size", [])
        gauge_checked_out = self._get_or_create_gauge("db_pool_checked_out", [])
        gauge_overflow = self._get_or_create_gauge("db_pool_overflow", [])
        try:
            gauge_size.set(pool.size())
            gauge_checked_out.set(pool.checkedout())
            gauge_overflow.set(pool.overflow())
        except Exception:
            pass

    def _get_or_create_gauge(self, name: str, labelnames: list[str], multiprocess_mode: str = "all") -> Gauge:
        if name not in self._metrics:
            collector = REGISTRY._names_to_collectors.get(name)
            if collector and type(collector).__name__ not in ("ProcessCollector", "GCCollector", "PlatformCollector"):
                self._metrics[name] = collector
            else:
                if collector:
                    try:
                        REGISTRY.unregister(collector)
                    except KeyError:
                        pass
                self._metrics[name] = Gauge(name, f"Gauge {name}", labelnames=labelnames, multiprocess_mode=multiprocess_mode)
        return self._metrics[name]

    def increment_counter(self, name: str, **labels):
        try:
            label_names = sorted(labels.keys())
            counter = self._get_or_create_counter(name, label_names)
            if labels:
                counter.labels(**labels).inc()
            else:
                counter.inc()
        except Exception as e:
            logger.warning(f"Failed to increment counter {name}: {e}")

    def record_timer(self, name: str, duration_ms: float, **labels):
        try:
            label_names = sorted(labels.keys())
            histogram = self._get_or_create_histogram(name, label_names)
            if labels:
                histogram.labels(**labels).observe(duration_ms)
            else:
                histogram.observe(duration_ms)
        except Exception as e:
            logger.warning(f"Failed to record timer {name}: {e}")

    def start_process_metrics_tracker(self):
        import asyncio

        asyncio.create_task(self._track_process_metrics_loop())

    def _track_memory_metrics(self):
        import os

        rss, vms = 0, 0
        if os.path.exists("/proc/self/status"):
            with open("/proc/self/status") as f:
                for line in f.read().splitlines():
                    if line.startswith("VmRSS:"):
                        rss = int(line.split()[1]) * 1024
                    elif line.startswith("VmSize:"):
                        vms = int(line.split()[1]) * 1024

        if rss > 0:
            self._get_or_create_gauge("process_resident_memory_bytes", [], multiprocess_mode="liveall").set(rss)
        if vms > 0:
            self._get_or_create_gauge("process_virtual_memory_bytes", [], multiprocess_mode="liveall").set(vms)

    def _track_fd_metrics(self):
        import os

        if os.path.exists("/proc/self/fd"):
            try:
                open_fds = len(os.listdir("/proc/self/fd"))
                self._get_or_create_gauge("process_open_fds", [], multiprocess_mode="liveall").set(open_fds)
            except Exception:
                pass

    def _track_cpu_metrics(self, last_cpu_seconds):
        import os

        if os.path.exists("/proc/self/stat"):
            try:
                with open("/proc/self/stat") as f:
                    fields = f.read().split()
                    utime = int(fields[13])
                    stime = int(fields[14])
                    ticks = utime + stime
                    clk_tck = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
                    current_cpu_seconds = ticks / clk_tck

                    if last_cpu_seconds > 0.0:
                        diff = current_cpu_seconds - last_cpu_seconds
                        if diff > 0:
                            self._get_or_create_counter("process_cpu_seconds_total", []).inc(diff)
                    return current_cpu_seconds
            except Exception:
                pass
        return last_cpu_seconds

    def _track_gc_metrics(self, last_gc_collections, last_gc_collected):
        import gc

        try:
            gc_stats = gc.get_stats()
            for gen in range(3):
                stats = gc_stats[gen]
                collections = stats["collections"]
                collected = stats["collected"]

                last_coll = last_gc_collections[gen]
                if last_coll > 0:
                    diff = collections - last_coll
                    if diff > 0:
                        self._get_or_create_counter("python_gc_collections_total", ["generation"]).labels(generation=str(gen)).inc(diff)
                last_gc_collections[gen] = collections

                last_coll_obj = last_gc_collected[gen]
                if last_coll_obj > 0:
                    diff = collected - last_coll_obj
                    if diff > 0:
                        self._get_or_create_counter("python_gc_objects_collected_total", ["generation"]).labels(generation=str(gen)).inc(
                            diff
                        )
                last_gc_collected[gen] = collected
        except Exception:
            pass

    def _track_pool_metrics(self):
        try:
            from src.infra.database.db import get_engine

            engine = get_engine()
            if hasattr(engine, "pool"):
                self.set_db_pool_metrics(engine.pool)
        except Exception:
            pass

    async def _track_process_metrics_loop(self):
        import os

        if not os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
            return

        last_cpu_seconds = 0.0
        last_gc_collections = [0, 0, 0]
        last_gc_collected = [0, 0, 0]

        while True:
            try:
                self._track_memory_metrics()
                self._track_fd_metrics()
                last_cpu_seconds = self._track_cpu_metrics(last_cpu_seconds)
                self._track_gc_metrics(last_gc_collections, last_gc_collected)
                self._track_pool_metrics()
            except Exception as e:
                logger.warning(f"Error in process metrics tracker loop: {e}")

            await asyncio.sleep(5)


metric_service = MetricService()
