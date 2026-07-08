import base64
import hmac
import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

import jwt
from django.conf import settings
from rest_framework import authentication, exceptions


@dataclass
class GatewayUser:
    id: int | None
    email: str
    roles: list[str]
    token_id: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def is_staff(self) -> bool:
        return self.has_role("ADMIN")

    def has_role(self, role: str) -> bool:
        normalized = role.replace("ROLE_", "").upper()
        return normalized in {item.replace("ROLE_", "").upper() for item in self.roles}


class GatewayOrJwtAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        context = request.headers.get("X-User-Context")
        signature = request.headers.get("X-User-Context-Signature")

        if context is not None:
            return self._authenticate_gateway_context(context, signature)

        auth_header = authentication.get_authorization_header(request).decode("utf-8")
        if not auth_header.lower().startswith("bearer "):
            return None

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return None

        return self._authenticate_bearer_token(token)

    def _authenticate_gateway_context(self, encoded_payload: str, signature: str | None):
        expected = base64.b64encode(
            hmac.new(
                settings.GATEWAY_INTERNAL_SECRET.encode("utf-8"),
                encoded_payload.encode("utf-8"),
                sha256,
            ).digest()
        ).decode("utf-8")

        if not signature or not hmac.compare_digest(expected, signature):
            raise exceptions.AuthenticationFailed("Invalid gateway signature")

        if not encoded_payload:
            return None

        try:
            payload = json.loads(base64.b64decode(encoded_payload).decode("utf-8"))
        except Exception as exc:
            raise exceptions.AuthenticationFailed("Invalid user context") from exc

        return self._build_user(payload), None

    def _authenticate_bearer_token(self, token: str):
        try:
            key = base64.b64decode(settings.JWT_ACCESS_SECRET)
            payload = jwt.decode(token, key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError as exc:
            raise exceptions.AuthenticationFailed("Token is expired") from exc
        except Exception as exc:
            raise exceptions.AuthenticationFailed("Invalid JWT token") from exc

        return self._build_user(payload), None

    def _build_user(self, payload: dict[str, Any]) -> GatewayUser:
        user_id = payload.get("user_id") or payload.get("userId")
        email = payload.get("email") or payload.get("username") or payload.get("sub") or ""
        roles = payload.get("roles") or []
        if not isinstance(roles, list):
            roles = [roles]

        try:
            user_id = int(user_id) if user_id is not None else None
        except (TypeError, ValueError) as exc:
            raise exceptions.AuthenticationFailed("Authenticated token contains an invalid user_id") from exc

        if not user_id:
            raise exceptions.AuthenticationFailed("Authenticated token does not include a valid user_id")

        return GatewayUser(
            id=user_id,
            email=str(email),
            roles=[str(role) for role in roles],
            token_id=payload.get("tokenId") or payload.get("jti"),
        )
