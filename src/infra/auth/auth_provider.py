import datetime
import uuid

import jwt


class JWTAuthProvider:
    def __init__(self, secret: str = "secret", expires_in_hours: int = 24):
        self.secret = secret
        self.expires_in_hours = expires_in_hours
        self.key_id = "default"

    def generate_token(self, payload: dict, expires_in_hours: int = None, extra_claims: dict = None) -> str:
        hours = expires_in_hours or self.expires_in_hours
        now = datetime.datetime.now(datetime.UTC)
        to_encode = payload.copy()
        to_encode.update(
            {
                "exp": now + datetime.timedelta(hours=hours),
                "iat": now,
                "nbf": now,
                "jti": str(uuid.uuid4()),
            }
        )
        if extra_claims:
            to_encode.update(extra_claims)
        headers = {"kid": self.key_id}
        return jwt.encode(to_encode, self.secret, algorithm="HS256", headers=headers)

    def generate_token_pair(self, payload: dict, ver: int = 1) -> dict:
        token = self.generate_token(payload, self.expires_in_hours, {"ver": ver, "type": "access"})
        refresh_token = self.generate_token(payload, 24 * 7, {"ver": ver, "type": "refresh"})
        return {"token": token, "refreshToken": refresh_token}

    def verify_token(self, token: str) -> dict | None:
        try:
            from src.shared.config.settings import settings

            decode_options = {
                "verify_iss": settings.environment == "production",
                "verify_aud": settings.environment == "production",
            }
            return jwt.decode(
                token,
                self.secret,
                algorithms=["HS256"],
                options=decode_options,
                issuer=settings.jwt_issuer,
                audience=settings.jwt_audience,
            )
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, Exception):
            return None


from src.shared.config.settings import settings

auth_provider = JWTAuthProvider(secret=settings.jwt_secret)
