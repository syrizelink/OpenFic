"""Test-only balance provider; never imported by the production application."""

import httpx
from fastapi import Request
from starlette.routing import Mount

from tests.plugins.e2e_app import app as app, fastapi_app, drive

balance = {"total": "100.00", "currency": "CNY", "status": 200, "requests": 0}


def transport(request):
    if request.url.host != "api.deepseek.com":
        return drive(request)
    balance["requests"] += 1
    assert request.url.path == "/user/balance"
    assert request.headers["Authorization"].startswith("Bearer whale-test-")
    return httpx.Response(
        balance["status"],
        json={
            "balance_infos": [
                {
                    "currency": balance["currency"],
                    "total_balance": balance["total"],
                    "granted_balance": "0.00",
                    "topped_up_balance": balance["total"],
                }
            ]
        },
    )


fastapi_app.state.plugin_host.http_transport = httpx.MockTransport(transport)


@fastapi_app.post("/_e2e/whale/balance")
async def update_balance(request: Request):
    changes = await request.json()
    for key in ["total", "currency", "status"]:
        if key in changes:
            balance[key] = changes[key]
    return balance


fastapi_app.router.routes.sort(
    key=lambda route: isinstance(route, Mount) and route.path == ""
)
