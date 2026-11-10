"""Route httpx2 requests (used by the Anthropic SDK) through plain httpx, so respx mocks them.

respx patches httpx only. This transport converts each httpx2 request into an httpx request
sent by an httpx.AsyncClient (intercepted by respx), then converts the response back.
"""

from __future__ import annotations

import httpx
import httpx2


class RespxBridgeTransport(httpx2.AsyncBaseTransport):
    def __init__(self) -> None:
        self._client = httpx.AsyncClient()

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        body = await request.aread()
        resp = await self._client.request(
            request.method,
            str(request.url),
            headers=[(k.decode(), v.decode()) for k, v in request.headers.raw],
            content=body,
        )
        return httpx2.Response(
            resp.status_code,
            headers=[(k.decode(), v.decode()) for k, v in resp.headers.raw],
            content=resp.content,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
