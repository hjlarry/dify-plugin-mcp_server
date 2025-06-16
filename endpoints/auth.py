import json
from typing import Mapping, Optional

from werkzeug import Request, Response

def validate_bearer_token(r: Request, settings: Mapping) -> Optional[Response]:
    """
    Validates the bearer token from the request.
    Returns a Response object if validation fails, otherwise None.
    """
    if settings.get("auth-token"):
        auth_header = r.headers.get("Authorization")
        token = None
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()

        if settings.get("auth-token") != token:
            req_id = r.json.get("id") if r.is_json else None
            error_response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32000, "message": "Invalid or missing token"},
            }
            return Response(
                json.dumps(error_response),
                status=401,
                content_type="application/json",
            )
    return None