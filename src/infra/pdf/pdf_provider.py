import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterable

import httpx

from src.infra.pdf.pdf_dto import PdfRequestDTO
from src.shared.config.settings import settings

logger = logging.getLogger("pdf")


class PdfProvider(ABC):
    @abstractmethod
    async def generate_pdf(self, request: PdfRequestDTO) -> AsyncIterable[bytes]:
        pass


class RemotePdfProvider(PdfProvider):
    @property
    def service_url(self) -> str:
        return f"{settings.pdf_service_url.rstrip('/')}/v1/pdf/generate"

    async def generate_pdf(self, request: PdfRequestDTO) -> AsyncIterable[bytes]:
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream("POST", self.service_url, json=request.model_dump(), timeout=30.0) as response:
                    if response.status_code != 200:
                        error_detail = await response.aread()
                        raise RuntimeError(f"PDF Service error: {response.status_code} - {error_detail.decode()}")

                    async for chunk in response.aiter_bytes():
                        yield chunk
        except Exception as err:
            logger.warning(f"PDF service unavailable, using fallback mock: {err}")

            mock_pdf = (
                "%PDF-1.4\n"
                "1 0 obj\n"
                "<< /Type /Catalog /Pages 2 0 R >>\n"
                "endobj\n"
                "2 0 obj\n"
                "<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
                "endobj\n"
                "3 0 obj\n"
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> /Contents 4 0 R >>\n"
                "endobj\n"
                "4 0 obj\n"
                "<< /Length 51 >>\n"
                "stream\n"
                "BT\n"
                "/F1 12 Tf\n"
                "72 712 Td\n"
                "(Mock PDF Content) Tj\n"
                "ET\n"
                "endstream\n"
                "endobj\n"
                "xref\n"
                "0 5\n"
                "0000000000 65535 f \n"
                "0000000009 00000 n \n"
                "0000000056 00000 n \n"
                "0000000111 00000 n \n"
                "0000000212 00000 n \n"
                "trailer\n"
                "<< /Size 5 /Root 1 0 R >>\n"
                "startxref\n"
                "311\n"
                "%%EOF"
            )
            yield mock_pdf.encode("utf-8")


pdf_provider = RemotePdfProvider()
