import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.infra.pdf.pdf_provider import RemotePdfProvider
from src.infra.pdf.pdf_dto import PdfRequestDTO
import httpx


@pytest.mark.asyncio
async def test_remote_pdf_provider_generate_pdf_success():
    provider = RemotePdfProvider()

    request = PdfRequestDTO(template="test", data={"foo": "bar"})

    async def mock_aiter_bytes():
        for chunk in [b"chunk1", b"chunk2"]:
            yield chunk

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.aiter_bytes = mock_aiter_bytes
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient.stream", return_value=mock_response):
        chunks = []
        async for chunk in provider.generate_pdf(request):
            chunks.append(chunk)

        assert chunks == [b"chunk1", b"chunk2"]


@pytest.mark.asyncio
async def test_remote_pdf_provider_generate_pdf_error():
    provider = RemotePdfProvider()

    request = PdfRequestDTO(template="test", data={"foo": "bar"})

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.aread = AsyncMock(return_value=b"Internal Error")
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient.stream", return_value=mock_response):
        chunks = []
        async for chunk in provider.generate_pdf(request):
            chunks.append(chunk)
        assert len(chunks) == 1
        assert chunks[0].startswith(b"%PDF")


@pytest.mark.asyncio
async def test_remote_pdf_provider_connect_error():
    provider = RemotePdfProvider()
    request = PdfRequestDTO(template="test", data={})

    with patch("httpx.AsyncClient.stream", side_effect=httpx.ConnectError("Connection failed")):
        chunks = []
        async for chunk in provider.generate_pdf(request):
            chunks.append(chunk)
        assert len(chunks) == 1
        assert chunks[0].startswith(b"%PDF")


@pytest.mark.asyncio
async def test_remote_pdf_provider_timeout_error():
    provider = RemotePdfProvider()
    request = PdfRequestDTO(template="test", data={})

    with patch("httpx.AsyncClient.stream", side_effect=httpx.TimeoutException("Timeout")):
        chunks = []
        async for chunk in provider.generate_pdf(request):
            chunks.append(chunk)
        assert len(chunks) == 1
        assert chunks[0].startswith(b"%PDF")


@pytest.mark.asyncio
async def test_remote_pdf_provider_unexpected_error():
    provider = RemotePdfProvider()
    request = PdfRequestDTO(template="test", data={})

    with patch("httpx.AsyncClient.stream", side_effect=ValueError("Unexpected")):
        chunks = []
        async for chunk in provider.generate_pdf(request):
            chunks.append(chunk)
        assert len(chunks) == 1
        assert chunks[0].startswith(b"%PDF")


@pytest.mark.asyncio
async def test_pdf_provider_base_class():
    from src.infra.pdf.pdf_provider import PdfProvider

    class ConcreteProvider(PdfProvider):
        async def generate_pdf(self, request):
            await super().generate_pdf(request)
            yield b""

    provider = ConcreteProvider()
    async for _ in provider.generate_pdf(None):
        pass
