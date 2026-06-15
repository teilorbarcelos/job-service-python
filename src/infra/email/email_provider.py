from src.infra.email.drivers.smtp_driver import SmtpEmailDriver
from src.shared.config.settings import settings


class EmailProvider:
    def __init__(self):
        self._driver = None

    def _get_driver(self):
        if self._driver is None:
            self._driver = SmtpEmailDriver()
        return self._driver

    async def send_email(self, to: str, subject: str, body: str, html: str = "") -> None:
        driver = self._get_driver()
        try:
            await driver.send_email(to=to, subject=subject, body=body, html=html)
        except Exception:
            pass

    def set_driver(self, driver) -> None:
        self._driver = driver


email_provider = EmailProvider()
