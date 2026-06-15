import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.shared.config.settings import settings


class SmtpEmailDriver:
    def __init__(
        self,
        host: str = "",
        port: int = 587,
        user: str = "",
        password: str = "",
        use_tls: bool = True,
    ):
        self.host = host or getattr(settings, "smtp_host", "")
        self.port = port or getattr(settings, "smtp_port", 587)
        self.user = user or getattr(settings, "smtp_user", "")
        self.password = password or getattr(settings, "smtp_password", "")
        self.use_tls = use_tls

    async def send_email(self, to: str, subject: str, body: str, html: str = "") -> None:
        if not self.host:
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["To"] = to
        msg["From"] = self.user

        msg.attach(MIMEText(body, "plain", "utf-8"))
        if html:
            msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(self.host, self.port) as server:
            if self.use_tls:
                server.starttls()
            if self.user:
                server.login(self.user, self.password)
            server.send_message(msg)
