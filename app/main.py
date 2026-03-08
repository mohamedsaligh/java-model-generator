"""FastAPI application for the Java Model Generator."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from .api.routes import router
from .mcp_server import mcp

# Initialize MCP session manager
session_manager = StreamableHTTPSessionManager(
    app=mcp._mcp_server,
    event_store=mcp._event_store,
    json_response=mcp.settings.json_response,
    stateless=mcp.settings.stateless_http,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage MCP session manager lifecycle."""
    async with session_manager.run():
        yield


app = FastAPI(
    title="Java Model Generator",
    description=(
        "Generate Java DTO model classes from XSD, JSON Schema, and other schema formats. "
        "Supports Lombok annotations, Jakarta validation constraints, and Jackson serialization. "
        "MCP endpoint available at POST /mcp via JSON-RPC (Streamable HTTP)."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.api_route("/mcp", methods=["GET", "POST", "DELETE"], include_in_schema=True, tags=["MCP"])
async def mcp_endpoint(request: Request):
    """MCP JSON-RPC endpoint (Streamable HTTP transport).

    - POST: Send JSON-RPC requests (initialize, tools/list, tools/call, etc.)
    - GET: Open SSE stream for server-to-client notifications
    - DELETE: Terminate an MCP session
    """
    return await _handle_mcp(request)


async def _handle_mcp(request: Request):
    """Forward request to MCP session manager via raw ASGI."""
    from starlette.responses import Response as StarletteResponse

    scope = request.scope
    receive = request.receive

    status_code = 200
    response_headers: list[tuple[bytes, bytes]] = []
    body_parts: list[bytes] = []

    async def send(message):
        nonlocal status_code
        if message["type"] == "http.response.start":
            status_code = message["status"]
            response_headers.extend(message.get("headers", []))
        elif message["type"] == "http.response.body":
            body_parts.append(message.get("body", b""))

    await session_manager.handle_request(scope, receive, send)

    headers_dict = {k.decode(): v.decode() for k, v in response_headers}
    return StarletteResponse(
        content=b"".join(body_parts),
        status_code=status_code,
        headers=headers_dict,
    )


@app.get("/manifest.json", tags=["MCP"], summary="MCP server manifest for client discovery")
async def manifest():
    """Return MCP server manifest for client auto-discovery.

    Dynamically generated from registered MCP tools.
    """
    tools = mcp._tool_manager.list_tools()
    return {
        "schema_version": "1.0",
        "name": mcp.name,
        "description": mcp._mcp_server.instructions or "",
        "version": app.version,
        "mcp": {
            "transport": "streamable-http",
            "url": "/mcp",
        },
        "tools": [
            {
                "name": t.name,
                "description": (t.description or "").split("\n")[0],
                "parameters": t.parameters,
            }
            for t in tools
        ],
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "java-model-generator", "mcp_endpoint": "/mcp"}


def run():
    """Entry point for running the server."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8100,
        reload=True,
    )


if __name__ == "__main__":
    run()
