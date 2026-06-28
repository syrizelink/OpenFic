import inspect
import logging

from starlette.requests import Request

from app.api.middleware.access_log import format_access_log, get_endpoint_location


def test_uvicorn_access_log_is_disabled() -> None:
    assert logging.getLogger("uvicorn.access").disabled is True


def test_format_access_log_uses_real_path_and_status_phrase() -> None:
    message = format_access_log(
        "GET",
        "/api/v1/projects/GTcu5ZHSSWXTJ97mtkbOI/chapter-context/context",
        200,
        6.44,
    )

    assert (
        message
        == "GET /api/v1/projects/GTcu5ZHSSWXTJ97mtkbOI/chapter-context/context 200 OK 6.44ms"
    )


def test_format_access_log_handles_unknown_status_code() -> None:
    message = format_access_log("GET", "/api/v1/projects", 599, 1)

    assert message == "GET /api/v1/projects 599  1.00ms"


async def sample_endpoint() -> None:
    return None


def test_get_endpoint_location_uses_request_endpoint() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/projects/project-id",
            "headers": [],
            "endpoint": sample_endpoint,
        }
    )

    location = get_endpoint_location(request)

    assert location is not None
    assert location.name == __name__
    assert location.function == "sample_endpoint"
    assert location.line == inspect.getsourcelines(sample_endpoint)[1]
