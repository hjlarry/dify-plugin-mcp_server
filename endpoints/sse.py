import uuid
import time
import json
import logging

from typing import Mapping
from werkzeug import Request, Response
from dify_plugin import Endpoint
from dify_plugin.config.logger_format import plugin_logger_handler

from .auth import validate_bearer_token

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)

def create_sse_message(event, data):
    return f"event: {event}\ndata: {json.dumps(data) if isinstance(data, (dict, list)) else data}\n\n"


class SSEEndpoint(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        """
        Invokes the endpoint with the given request.
        """
        logger.info(f"SSEEndpoint request headers: {r.headers}")

        auth_error = validate_bearer_token(r, settings)
        if auth_error:
            return auth_error
        
        session_id = str(uuid.uuid4()).replace("-", "")

        def generate():
            endpoint = f"messages/?session_id={session_id}"
            yield create_sse_message("endpoint", endpoint)

            while True:
                message = None
                if self.session.storage.exist(session_id):
                    message = self.session.storage.get(session_id)
                    message = message.decode()
                    self.session.storage.delete(session_id)
                    yield create_sse_message("message", message)
                time.sleep(0.5)    

        return Response(generate(), status=200, content_type="text/event-stream")
