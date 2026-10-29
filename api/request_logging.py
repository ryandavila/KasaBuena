"""ASGI request correlation, including streaming responses and error bodies."""

import json
import re
from uuid import uuid4

from fastapi import Request
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders

from .logging_config import get_logger, request_id

logger = get_logger(__name__)
_VALID_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}\Z")


class RequestIDMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        supplied = Headers(scope=scope).get("x-request-id", "")
        correlation = supplied if _VALID_ID.fullmatch(supplied) else uuid4().hex
        token = request_id.set(correlation)
        started = False

        async def send_response(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                MutableHeaders(scope=message)["X-Request-ID"] = correlation
            await send(message)

        try:
            await self.app(scope, receive, send_response)
        except Exception as error:  # noqa: BLE001 - return correlated, sanitized 500s
            logger.exception("Request failed (%s)", type(error).__name__)
            if started:
                # A streaming response has already sent headers: it cannot become JSON.
                raise
            await JSONResponse(
                {"detail": "Internal server error", "request_id": correlation},
                status_code=500,
            )(scope, receive, send_response)
        finally:
            request_id.reset(token)


async def correlated_http_error(request: Request, exc):
    response = await http_exception_handler(request, exc)
    if response.body:
        return _with_request_id(response)
    return response


def _with_request_id(response):
    body = json.loads(response.body)
    body["request_id"] = request_id.get()
    headers = dict(response.headers)
    headers.pop("content-length", None)
    return JSONResponse(body, status_code=response.status_code, headers=headers)


async def correlated_validation_error(request: Request, exc):
    return _with_request_id(await request_validation_exception_handler(request, exc))
