from unittest.mock import patch

import pytest
from httpx import AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_should_build_the_app_correctly():
    assert app is not None
    assert app.title == "Backend Python"


@pytest.mark.asyncio
async def test_should_have_health_and_liveness_endpoints(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "UP"

    response = await client.get("/liveness")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_should_return_401_for_protected_routes_without_token(client: AsyncClient):
    response = await client.get("/v1/user")
    assert response.status_code == 401
    assert response.json()["message"] == "Invalid or expired token"


@pytest.mark.asyncio
async def test_should_return_422_on_validation_error(client: AsyncClient):

    response = await client.post("/v1/auth/login", json={"invalid": "payload"})
    assert response.status_code == 422
    assert response.json()["message"] == "Validation Error"


@pytest.mark.asyncio
async def test_global_exception_handler_direct(client: AsyncClient):
    from unittest.mock import AsyncMock, MagicMock

    from src.shared.middlewares.error_handlers import global_exception_handler

    request = MagicMock()
    request.method = "GET"
    request.url = "http://test"
    request.state.user = {"id": "user-123", "email": "test@test.com"}

    exc = Exception("Test Crash")

    with patch("src.shared.middlewares.error_handlers.audit_service.save_error_log", AsyncMock()) as mock_save:
        response = await global_exception_handler(request, exc)
        assert response.status_code == 500
        mock_save.assert_called_once()

    with patch("src.shared.middlewares.error_handlers.audit_service.save_error_log", AsyncMock(side_effect=Exception("Save Fail"))):
        response = await global_exception_handler(request, exc)
        assert response.status_code == 500


@pytest.mark.asyncio
async def test_audit_middleware_with_unreadable_body(client: AsyncClient):
    response = await client.post("/v1/auth/login", content=b"\xff", headers={"Content-Type": "application/json"})
    assert response.status_code in [400, 422]


@pytest.mark.asyncio
async def test_lifespan_rabbitmq_failure():
    from unittest.mock import AsyncMock, MagicMock

    from src.main import lifespan, rabbitmq_provider

    with patch("src.main.IS_TEST", False):
        with patch("src.main.bootstrap_system", AsyncMock()):
            with patch.object(rabbitmq_provider, "connect", AsyncMock(side_effect=Exception("Lifespan RabbitMQ Error"))):
                async with lifespan(MagicMock()):
                    pass


@pytest.mark.asyncio
async def test_lifespan_metrics_failure():
    from unittest.mock import AsyncMock, MagicMock

    from src.main import lifespan

    with patch("src.main.IS_TEST", False):
        with patch("src.main.bootstrap_system", AsyncMock()):
            with patch("src.main.rabbitmq_provider.connect", AsyncMock()):
                with patch(
                    "src.infra.metrics.metric_service.metric_service._get_or_create_counter", side_effect=Exception("Metrics Init Error")
                ):
                    async with lifespan(MagicMock()):
                        pass


@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient):
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_metrics_endpoint_multiprocess(client: AsyncClient):
    import tempfile
    import os

    tmpdir = tempfile.mkdtemp()
    open(os.path.join(tmpdir, "counter_12345.db"), "w").close()
    with patch.dict("os.environ", {"PROMETHEUS_MULTIPROC_DIR": tmpdir}):
        with patch("src.main.multiprocess.MultiProcessCollector") as mock_collector:
            with patch("src.main.generate_latest", return_value=b"mocked_data"):
                response = await client.get("/metrics")
                assert response.status_code == 200
                assert response.content == b"mocked_data"
                mock_collector.assert_called_once()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.asyncio
async def test_security_headers_on_response(client: AsyncClient):
    response = await client.get("/liveness")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Strict-Transport-Security") is not None


def test_cleanup_stale_multiproc_files():
    import os
    import shutil
    import tempfile

    from src.main import _cleanup_stale_multiproc_files

    temp_dir = tempfile.mkdtemp()

    active_pid = os.getpid()
    dead_pid = 999999
    try:
        os.kill(dead_pid, 0)
        dead_pid = 999998
    except OSError:
        pass

    active_file = os.path.join(temp_dir, f"counter_{active_pid}.db")
    dead_file = os.path.join(temp_dir, f"counter_{dead_pid}.db")
    invalid_file = os.path.join(temp_dir, "invalid_format.db")

    with open(active_file, "w") as f:
        f.write("active")
    with open(dead_file, "w") as f:
        f.write("dead")
    with open(invalid_file, "w") as f:
        f.write("invalid")

    with patch.dict("os.environ", {"PROMETHEUS_MULTIPROC_DIR": temp_dir}):
        with patch("src.main.IS_TEST", False):
            _cleanup_stale_multiproc_files()

            assert os.path.exists(active_file)
            assert os.path.exists(invalid_file)
            assert not os.path.exists(dead_file)

    with patch.dict("os.environ", {}, clear=True):
        with patch("src.main.IS_TEST", False):
            _cleanup_stale_multiproc_files()
            assert os.environ.get("PROMETHEUS_MULTIPROC_DIR") == "/tmp/prometheus_multiproc"

    with patch.dict("os.environ", {"PROMETHEUS_MULTIPROC_DIR": temp_dir}):
        with patch("src.main.IS_TEST", False):
            with patch("os.path.exists", return_value=False):
                _cleanup_stale_multiproc_files()

    with patch.dict("os.environ", {"PROMETHEUS_MULTIPROC_DIR": temp_dir}):
        with patch("src.main.IS_TEST", False):
            with patch("os.path.exists", side_effect=RuntimeError("Mock error")):
                with patch("os.makedirs", side_effect=RuntimeError("Mock makedirs error")):
                    _cleanup_stale_multiproc_files()

    shutil.rmtree(temp_dir, ignore_errors=True)
