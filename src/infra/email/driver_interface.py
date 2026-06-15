from typing import Protocol


class EmailDriver(Protocol):
    async def send_email(self, to: str, subject: str, body: str, html: str = "") -> None: ...
