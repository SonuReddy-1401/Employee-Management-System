import httpx
from fastapi import Request, Response
from ems_common.errors import EMSError

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


async def proxy_request(
    client: httpx.AsyncClient, upstream_base_url: str, request: Request
) -> Response:
    # Build target URL
    url = f"{upstream_base_url}{request.url.path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    # Filter request headers
    headers = {}
    for key, value in request.headers.items():
        k_lower = key.lower()
        if k_lower not in HOP_BY_HOP_HEADERS and k_lower != "host":
            headers[key] = value

    body = await request.body()

    try:
        upstream_resp = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
        )
    except httpx.ConnectError:
        raise EMSError(
            code="UPSTREAM_UNAVAILABLE",
            message="Upstream service unavailable",
            status_code=502,
        )
    except httpx.TimeoutException:
        raise EMSError(
            code="UPSTREAM_TIMEOUT",
            message="Upstream service timed out",
            status_code=504,
        )

    # Filter response headers
    resp_headers = {}
    for key, value in upstream_resp.headers.items():
        k_lower = key.lower()
        if (
            k_lower not in HOP_BY_HOP_HEADERS
            and k_lower not in ("content-length", "content-encoding", "transfer-encoding")
        ):
            resp_headers[key] = value

    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=resp_headers,
    )
