import base64
import hmac
from hashlib import sha256

from django.conf import settings
from django.http import JsonResponse


class GatewayOnlyMiddleware:
    """
    Require every health-service API request to be signed by api-gateway.
    This prevents clients from bypassing the gateway and calling port 8100 directly.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/"):
            encoded_payload = request.headers.get("X-User-Context")
            signature = request.headers.get("X-User-Context-Signature")

            if encoded_payload is None or not self._is_valid_signature(encoded_payload, signature):
                return JsonResponse(
                    {
                        "message": "Health-service must be accessed through api-gateway",
                    },
                    status=403,
                )

        return self.get_response(request)

    @staticmethod
    def _is_valid_signature(encoded_payload: str, signature: str | None) -> bool:
        if not signature:
            return False

        expected = base64.b64encode(
            hmac.new(
                settings.GATEWAY_INTERNAL_SECRET.encode("utf-8"),
                encoded_payload.encode("utf-8"),
                sha256,
            ).digest()
        ).decode("utf-8")

        return hmac.compare_digest(expected, signature)
