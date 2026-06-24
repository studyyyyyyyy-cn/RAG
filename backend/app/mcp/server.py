"""MCP Server implementation using SSE transport."""

import json
import logging
import asyncio
from typing import Any, AsyncGenerator
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.mcp.tools import TOOL_DEFINITIONS, TOOL_HANDLERS

logger = logging.getLogger(__name__)

router = APIRouter()


class MCPServerSSE:
    """MCP Server handling JSON-RPC protocol over SSE."""

    def __init__(self):
        self.tools = TOOL_DEFINITIONS
        self.handlers = TOOL_HANDLERS

    def handle_request(self, request: dict) -> dict:
        """Handle incoming JSON-RPC request."""
        method = request.get("method")
        request_id = request.get("id")

        try:
            if method == "initialize":
                return self._handle_initialize(request_id)
            elif method == "notifications/initialized":
                return None
            elif method == "tools/list":
                return self._handle_list_tools(request_id)
            elif method == "tools/call":
                # tools/call should be handled via POST /message for async execution
                return self._error_response(request_id, -32601,
                    "tools/call must use POST /mcp/message endpoint")
            else:
                return self._error_response(request_id, -32601, f"Unknown method: {method}")
        except Exception as e:
            logger.error(f"Error handling request: {e}", exc_info=True)
            return self._error_response(request_id, -32603, str(e))

    def _handle_initialize(self, request_id: Any) -> dict:
        """Handle initialize request."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": "ragapp-mcp",
                    "version": "1.0.0",
                },
            },
        }

    def _handle_list_tools(self, request_id: Any) -> dict:
        """Handle tools/list request."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": self.tools,
            },
        }

    async def handle_call_tool(self, request_id: Any, params: dict) -> dict:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.handlers:
            return self._error_response(request_id, -32601, f"Unknown tool: {tool_name}")

        handler = self.handlers[tool_name]

        try:
            if tool_name == "list_knowledge_bases":
                result = await handler()
            elif tool_name == "rag_chat":
                result = await handler(
                    query=arguments.get("query"),
                    kb_id=arguments.get("kb_id"),
                    history=arguments.get("history"),
                    top_k=arguments.get("top_k", 5),
                    enable_agent=arguments.get("enable_agent", True),
                )
            else:
                result = await handler(**arguments)

            content = [
                {
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False),
                }
            ]

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": content,
                },
            }
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}", exc_info=True)
            return self._error_response(request_id, -32603, str(e))

    def _error_response(self, request_id: Any, code: int, message: str) -> dict:
        """Create error response."""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": code,
                "message": message,
            },
        }


mcp_server = MCPServerSSE()


@router.get("/sse")
async def mcp_sse_endpoint(request: Request):
    """MCP SSE endpoint for receiving messages via query parameter."""
    return EventSourceResponse(mcp_sse_generator(request))


async def mcp_sse_generator(request: Request) -> AsyncGenerator[dict, None]:
    """Generate SSE events for MCP protocol."""
    yield {
        "event": "endpoint",
        "data": "/mcp/message"
    }

    # Keep connection alive with periodic heartbeat comments
    heartbeat_interval = 30  # seconds
    elapsed = 0
    while True:
        if await request.is_disconnected():
            break
        await asyncio.sleep(1)
        elapsed += 1
        if elapsed >= heartbeat_interval:
            yield {"comment": ""}  # SSE comment as heartbeat
            elapsed = 0


@router.post("/message")
async def mcp_message_endpoint(request: Request):
    """MCP message endpoint for sending JSON-RPC requests."""
    body = await request.json()
    
    method = body.get("method")
    request_id = body.get("id")
    params = body.get("params", {})
    
    if method == "tools/call":
        response = await mcp_server.handle_call_tool(request_id, params)
    else:
        response = mcp_server.handle_request(body)
    
    if response is None:
        return {"status": "ok"}
    
    return response


def get_mcp_sse_url(host: str = "localhost", port: int = 8000) -> str:
    """Get the MCP SSE connection URL."""
    return f"http://{host}:{port}/mcp/sse"
