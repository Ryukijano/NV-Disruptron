from __future__ import annotations

import os
from urllib.parse import urljoin

import httpx
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route as StarletteRoute

STREAMLIT_PORT = int(os.environ.get("STREAMLIT_PORT", "8501"))
FASTAPI_PORT = int(os.environ.get("FASTAPI_PORT", "8010"))
PROXY_PORT = int(os.environ.get("PORT", "7860"))

GITHUB_PAGES_ORIGINS = [
    "https://ryukijano.github.io",
    "https://ryukijano.github.io/NV-Disruptron",
    "https://ryukijano.github.io/NV-Disruptron/",
]


def _build_response(
    client_resp: httpx.Response,
    *,
    drop_headers: set[str] | None = None,
) -> Response:
    drop_headers = drop_headers or {"content-encoding", "transfer-encoding", "content-length"}
    headers = {
        k: v
        for k, v in client_resp.headers.items()
        if k.lower() not in drop_headers
    }
    return Response(
        content=client_resp.content,
        status_code=client_resp.status_code,
        headers=headers,
    )


async def _proxy_request(request: Request, target_port: int, prefix: str) -> Response:
    base_url = f"http://127.0.0.1:{target_port}"
    target_path = request.url.path
    if prefix and target_path.startswith(prefix):
        target_path = target_path[len(prefix):]
    target_url = urljoin(base_url + "/", target_path.lstrip("/"))

    client: httpx.AsyncClient = request.app.state.client
    method = request.method
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("accept-encoding", None)

    body = await request.body()
    params = dict(request.query_params)

    try:
        resp = await client.request(
            method,
            target_url,
            headers=headers,
            params=params,
            content=body,
            timeout=300.0,
            follow_redirects=True,
        )
        return _build_response(resp)
    except httpx.RequestError:
        return Response("Upstream service unavailable", status_code=503)


async def api_proxy(request: Request) -> Response:
    return await _proxy_request(request, FASTAPI_PORT, "/api")


async def streamlit_proxy(request: Request) -> Response:
    return await _proxy_request(request, STREAMLIT_PORT, "")


routes = [
    StarletteRoute("/api/{path:path}", api_proxy, methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]),
    StarletteRoute("/{path:path}", streamlit_proxy, methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]),
    StarletteRoute("/", streamlit_proxy, methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"]),
]

app = Starlette(routes=routes)

app.add_middleware(
    CORSMiddleware,
    allow_origins=GITHUB_PAGES_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    app.state.client = httpx.AsyncClient(timeout=300.0)


@app.on_event("shutdown")
async def _shutdown() -> None:
    await app.state.client.aclose()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PROXY_PORT)
