from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import id_token


class OIDCAuthenticationError(ValueError):
    pass


class OIDCAuthorizationError(PermissionError):
    pass


TokenVerifier = Callable[[str, Request, str], dict[str, Any]]


@dataclass(frozen=True)
class OIDCValidator:
    audience: str
    expected_email: str
    verifier: TokenVerifier = id_token.verify_oauth2_token

    def validate(self, authorization: str | None) -> dict[str, Any]:
        if not authorization:
            raise OIDCAuthenticationError("missing bearer token")
        scheme, separator, token = authorization.partition(" ")
        if separator != " " or scheme.lower() != "bearer" or not token:
            raise OIDCAuthenticationError("invalid authorization header")
        try:
            claims = self.verifier(token, Request(), self.audience)
        except (GoogleAuthError, ValueError) as exc:
            raise OIDCAuthenticationError("invalid OIDC token") from exc
        issuer = claims.get("iss")
        if issuer not in ("accounts.google.com", "https://accounts.google.com"):
            raise OIDCAuthenticationError("invalid token issuer")
        if claims.get("email") != self.expected_email or claims.get("email_verified") is not True:
            raise OIDCAuthorizationError("unexpected task identity")
        return claims

