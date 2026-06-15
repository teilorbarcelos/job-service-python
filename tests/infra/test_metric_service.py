from unittest.mock import patch

import pytest
from prometheus_client import REGISTRY

from src.infra.metrics.metric_service import MetricService


def test_metric_service_instance():
    service = MetricService()
    assert isinstance(service, MetricService)
    assert hasattr(service, "increment_counter")


def test_metric_service_counter_creation_and_caching():
    service = MetricService()
    name = "test_custom_counter_total"

    if name in service._metrics:
        del service._metrics[name]

    collector = REGISTRY._names_to_collectors.get(name)
    if collector:
        REGISTRY.unregister(collector)

    service.increment_counter(name, method="GET", status="200")
    assert name in service._metrics

    service.increment_counter(name, method="GET", status="200")

    del service._metrics[name]
    service.increment_counter(name, method="GET", status="200")
    assert name in service._metrics


def test_metric_service_histogram_creation_and_caching():
    service = MetricService()
    name = "test_custom_histogram_seconds"

    if name in service._metrics:
        del service._metrics[name]

    collector = REGISTRY._names_to_collectors.get(name)
    if collector:
        REGISTRY.unregister(collector)

    service.record_timer(name, 12.34, route="/test")
    assert name in service._metrics

    service.record_timer(name, 5.67, route="/test")

    del service._metrics[name]
    service.record_timer(name, 8.90, route="/test")
    assert name in service._metrics


def test_metric_service_counter_exception_safety():
    service = MetricService()
    name = "test_exception_counter_total"

    service.increment_counter(name, label_a="val")

    service.increment_counter(name, label_b="val")


def test_metric_service_histogram_exception_safety():
    service = MetricService()
    name = "test_exception_histogram_seconds"

    service.record_timer(name, 100.0, label_a="val")
    service.record_timer(name, 200.0, label_b="val")


def test_metric_service_gauge_creation_and_caching():
    service = MetricService()
    name = "test_custom_gauge_bytes"

    if name in service._metrics:
        del service._metrics[name]

    collector = REGISTRY._names_to_collectors.get(name)
    if collector:
        REGISTRY.unregister(collector)

    gauge = service._get_or_create_gauge(name, [])
    assert name in service._metrics

    gauge2 = service._get_or_create_gauge(name, [])
    assert gauge is gauge2

    del service._metrics[name]
    gauge3 = service._get_or_create_gauge(name, [])
    assert gauge3 is gauge


def test_start_process_metrics_tracker():
    service = MetricService()
    with patch("asyncio.create_task") as mock_create_task:
        service.start_process_metrics_tracker()
        mock_create_task.assert_called_once()


@pytest.mark.asyncio
async def test_track_process_metrics_loop():
    import asyncio
    from unittest.mock import mock_open, patch

    service = MetricService()

    test_metrics = [
        "process_resident_memory_bytes",
        "process_virtual_memory_bytes",
        "process_open_fds",
        "process_cpu_seconds_total",
        "python_gc_collections_total",
        "python_gc_objects_collected_total",
    ]
    for m in test_metrics:
        if m in service._metrics:
            del service._metrics[m]
        col = REGISTRY._names_to_collectors.get(m)
        if col:
            REGISTRY.unregister(col)

    with patch.dict("os.environ", {}, clear=True):
        await service._track_process_metrics_loop()

    mock_status_content = "VmRSS:      12345 kB\nVmSize:     67890 kB\n"

    sleep_calls = 0

    async def mock_sleep(seconds):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 2:
            raise asyncio.CancelledError()

    stat_calls = 0

    def my_open(path, mode="r"):
        nonlocal stat_calls
        if "status" in path:
            return mock_open(read_data=mock_status_content)()
        elif "stat" in path:
            stat_calls += 1
            if stat_calls == 1:
                return mock_open(read_data="1 2 3 4 5 6 7 8 9 10 11 12 13 100 200 16\n")()
            elif stat_calls == 2:
                return mock_open(read_data="1 2 3 4 5 6 7 8 9 10 11 12 13 150 250 16\n")()
            else:
                raise RuntimeError("Stat error")
        return mock_open()()

    fd_calls = 0

    def mock_listdir(path):
        nonlocal fd_calls
        fd_calls += 1
        if fd_calls > 2:
            raise RuntimeError("Listdir error")
        return ["fd1", "fd2"]

    gc_calls = 0

    def mock_gc():
        nonlocal gc_calls
        gc_calls += 1
        if gc_calls == 1:
            return [
                {"collections": 10, "collected": 100, "uncollectable": 0},
                {"collections": 5, "collected": 50, "uncollectable": 0},
                {"collections": 1, "collected": 10, "uncollectable": 0},
            ]
        elif gc_calls == 2:
            return [
                {"collections": 15, "collected": 150, "uncollectable": 0},
                {"collections": 5, "collected": 50, "uncollectable": 0},
                {"collections": 1, "collected": 10, "uncollectable": 0},
            ]
        else:
            raise RuntimeError("GC error")

    with patch.dict("os.environ", {"PROMETHEUS_MULTIPROC_DIR": "/tmp/test_multiproc"}):
        with patch("os.path.exists", return_value=True):
            with patch("os.listdir", side_effect=mock_listdir):
                with patch("os.sysconf", return_value=100):
                    with patch("gc.get_stats", side_effect=mock_gc):
                        with patch("asyncio.sleep", side_effect=mock_sleep):
                            with patch("builtins.open", side_effect=my_open):
                                with pytest.raises(asyncio.CancelledError):
                                    await service._track_process_metrics_loop()

        with patch("os.path.exists", return_value=False):
            with patch("asyncio.sleep", side_effect=asyncio.CancelledError()):
                with pytest.raises(asyncio.CancelledError):
                    await service._track_process_metrics_loop()

        with patch("os.path.exists", side_effect=RuntimeError("Mock outer exception")):
            with patch("asyncio.sleep", side_effect=asyncio.CancelledError()):
                with pytest.raises(asyncio.CancelledError):
                    await service._track_process_metrics_loop()


def test_unregistration_guards():
    service = MetricService()

    for name in ["process_resident_memory_bytes", "python_gc_collections_total"]:
        col = REGISTRY._names_to_collectors.get(name)
        if col:
            try:
                REGISTRY.unregister(col)
            except KeyError:
                pass

    class ProcessCollector:
        def collect(self):
            return []

    pc = ProcessCollector()
    REGISTRY._names_to_collectors["process_resident_memory_bytes"] = pc
    REGISTRY._collector_to_names[pc] = ["process_resident_memory_bytes"]

    if "process_resident_memory_bytes" in service._metrics:
        del service._metrics["process_resident_memory_bytes"]

    with patch("prometheus_client.REGISTRY.unregister", side_effect=KeyError("Mock key error")):
        try:
            service._get_or_create_gauge("process_resident_memory_bytes", [])
        except ValueError:
            pass

    if pc in REGISTRY._collector_to_names:
        del REGISTRY._collector_to_names[pc]

    class GCCollector:
        def collect(self):
            return []

    gcc = GCCollector()
    REGISTRY._names_to_collectors["python_gc_collections_total"] = gcc
    REGISTRY._collector_to_names[gcc] = ["python_gc_collections_total"]

    if "python_gc_collections_total" in service._metrics:
        del service._metrics["python_gc_collections_total"]

    with patch("prometheus_client.REGISTRY.unregister", side_effect=KeyError("Mock key error")):
        try:
            service._get_or_create_counter("python_gc_collections_total", ["generation"])
        except ValueError:
            pass

    if gcc in REGISTRY._collector_to_names:
        del REGISTRY._collector_to_names[gcc]
