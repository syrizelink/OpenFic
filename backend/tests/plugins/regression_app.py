"""Disposable regression server; never use with user data or deploy."""

from starlette.routing import Mount

from tests.plugins.e2e_app import app as app, fastapi_app
from tests.plugins.regression_provider import completion

fastapi_app.post("/_e2e/regression/v1/chat/completions")(completion)
fastapi_app.router.routes.sort(
    key=lambda route: isinstance(route, Mount) and route.path == ""
)
