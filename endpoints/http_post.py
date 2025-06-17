import uuid
import json
from typing import Mapping
import logging

from werkzeug import Request, Response
from dify_plugin import Endpoint
from dify_plugin.config.logger_format import plugin_logger_handler

from .auth import validate_bearer_token

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)

class HTTPPostEndpoint(Endpoint):
    def _invoke(self, r: Request, values: Mapping, settings: Mapping) -> Response:
        """
        the simplest Streamable HTTP mcp protocol implementation.

        1. not valid session id
        2. not support SSE
        3. not support streaming
        4. only basic logic
        """
        logger.info(f"HTTPPostEndpoint request headers: {r.headers}")
        logger.info(f"HTTPPostEndpoint request json: {r.json}")

        auth_error = validate_bearer_token(r, settings)
        if auth_error:
            return auth_error

        app_id = settings.get("app").get("app_id")
        try:
            tool = json.loads(settings.get("app-input-schema"))
        except json.JSONDecodeError:
            logger.error(f'Invalid app-input-schema: {settings.get("app-input-schema")}')
            raise ValueError("Invalid app-input-schema")

        session_id = r.args.get("session_id")
        data = r.json

        if data.get("method") == "initialize":
            session_id = str(uuid.uuid4()).replace("-", "")
            response = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                    },
                    "serverInfo": {"name": "Dify", "version": "0.0.1"},
                },
            }
            headers = {"mcp-session-id": session_id}
            return Response(
                json.dumps(response),
                status=200,
                content_type="application/json",
                headers=headers,
            )
        elif data.get("method") == "ping":
            response = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {},
            }
            return Response(
                json.dumps(response),
                status=200,
                content_type="application/json",
            )

        elif data.get("method") == "notifications/initialized":
            return Response("", status=202, content_type="application/json")

        elif data.get("method") == "tools/list":
            response = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "result": {"tools": [tool]},
            }

        elif data.get("method") == "tools/call":
            tool_name = data.get("params", {}).get("name")
            arguments = data.get("params", {}).get("arguments", {})

            try:
                if tool_name == tool.get("name"):
                    if settings.get("app-type") == "chat":
                        result = self.session.app.chat.invoke(
                            app_id=app_id,
                            query=arguments.get("query", "empty query"),
                            inputs=arguments,
                            response_mode="blocking",
                        )
                    else:
                        result = self.session.app.workflow.invoke(
                            app_id=app_id, inputs=arguments, response_mode="blocking"
                        )
                    logger.info(f"Invoke dify app result: {json.dumps(result, ensure_ascii=False)}")
                else:
                    raise ValueError(f"Unknown tool: {tool_name}")

                if settings.get("app-type") == "chat":
                    final_result = {"type": "text", "text": result.get("answer")}
                else:
                    outputs = result.get("data", {}).get("outputs", {})
                    text_list = []
                    for v in outputs.values():
                        if isinstance(v, str):
                            text_list.append(v)
                        elif isinstance(v, dict) or isinstance(v, list):
                            text_list.append(json.dumps(v, ensure_ascii=False))
                        else:
                            text_list.append(str(v))
                    final_result = {"type": "text", "text": "\n".join(text_list)}

                response = {
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "result": {"content": [final_result], "isError": False},
                }
            except Exception as e:
                logger.error(f"HTTPPostEndpoint tool call error: {e}")
                response = {
                    "jsonrpc": "2.0",
                    "id": data.get("id"),
                    "error": {"code": -32000, "message": str(e)},
                }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "error": {"code": -32001, "message": "unsupported method"},
            }

        return Response(
            json.dumps(response), status=200, content_type="application/json"
        )
