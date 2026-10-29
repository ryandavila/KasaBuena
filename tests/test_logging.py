import asyncio
import io
import json
import logging
from contextlib import contextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.logging_config import (
    ContextFilter,
    JsonFormatter,
    device_context,
    log_context,
    request_id,
    setup_logging,
)
from api.request_logging import (
    RequestIDMiddleware,
    correlated_http_error,
    correlated_validation_error,
)


@contextmanager
def capture_json():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(ContextFilter())
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    level = root.level
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)
    try:
        yield stream
    finally:
        root.removeHandler(handler)
        root.setLevel(level)


def test_logging_configuration(tmp_path):
    root = logging.getLogger()
    previous = root.handlers[:]
    level = root.level
    uvicorn_state = {
        name: (
            logging.getLogger(name).handlers[:],
            logging.getLogger(name).level,
            logging.getLogger(name).propagate,
        )
        for name in ("uvicorn", "uvicorn.access", "uvicorn.error")
    }
    try:
        setup_logging("DEBUG", "json", logs_dir=tmp_path)
        setup_logging("DEBUG", "json", logs_dir=tmp_path)
        token = request_id.set("test-request")
        try:
            with log_context(device_id="plug", host="10.0.0.1"):
                logging.getLogger("uvicorn.access").info("test access")
        finally:
            request_id.reset(token)
        rows = [
            json.loads(line)
            for line in (tmp_path / "kasabuena.log").read_text().splitlines()
        ]
        assert len(rows) == 1
        assert rows[0]["request_id"] == "test-request"
        assert rows[0]["device_id"] == "plug"
        assert rows[0]["host"] == "10.0.0.1"
        assert rows[0]["logger"] == "uvicorn.access"
        setup_logging("WARNING", "text", logs_dir=tmp_path)
        logging.getLogger("api.test").info("hidden")
        logging.getLogger("api.test").warning("visible")
        text = (tmp_path / "kasabuena.log").read_text()
        assert "hidden" not in text
        assert "request_id=None" in text
        assert "visible" in text
    finally:
        for handler in root.handlers[:]:
            if handler not in previous:
                root.removeHandler(handler)
                handler.close()
        root.handlers = previous
        root.setLevel(level)
        for name, (handlers, log_level, propagate) in uvicorn_state.items():
            logger = logging.getLogger(name)
            logger.handlers, logger.level, logger.propagate = (
                handlers,
                log_level,
                propagate,
            )


def make_app():
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.add_exception_handler(StarletteHTTPException, correlated_http_error)
    app.add_exception_handler(RequestValidationError, correlated_validation_error)

    @app.get("/work")
    async def work(value: int = 1):
        await asyncio.sleep(0)
        logging.getLogger("api.test").info("working")
        return {"id": request_id.get()}

    @app.get("/handled")
    async def handled():
        raise HTTPException(409, "Conflict", headers={"X-Example": "kept"})

    @app.get("/broken")
    async def broken():
        raise RuntimeError("secret detail")

    return app


def test_correlated_errors_and_generated_ids():
    client = TestClient(make_app())
    for path, status in [
        ("/handled", 409),
        ("/work?value=bad", 422),
        ("/missing", 404),
        ("/broken", 500),
    ]:
        response = client.get(path, headers={"X-Request-ID": "caller-123"})
        assert response.status_code == status
        assert response.headers["X-Request-ID"] == "caller-123"
        assert response.json()["request_id"] == "caller-123"
        assert int(response.headers["content-length"]) == len(response.content)
        assert "secret detail" not in response.text
    assert client.get("/handled").headers["X-Example"] == "kept"
    a = client.get("/work")
    b = client.get("/work", headers={"X-Request-ID": "bad id"})
    assert a.headers["X-Request-ID"] != b.headers["X-Request-ID"]
    assert len(b.headers["X-Request-ID"]) == 32
    assert request_id.get() is None


def test_parallel_requests_and_device_operations_are_isolated():
    from api.kasa_service import DeviceRegistry
    from api.testing.fake_devices import FakeDevice

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=make_app()), base_url="http://test"
        ) as client:
            responses = await asyncio.gather(
                *[
                    client.get("/work", headers={"X-Request-ID": f"req-{i}"})
                    for i in range(5)
                ]
            )
        assert [r.json()["id"] for r in responses] == [f"req-{i}" for i in range(5)]
        registry = DeviceRegistry()
        registry._devices = {
            host: FakeDevice(host) for host in ("10.0.0.1", "10.0.0.2")
        }
        await asyncio.gather(
            *(registry.set_power(host, True) for host in registry._devices)
        )
        assert device_context.get() is None
        assert request_id.get() is None

    with capture_json() as stream:
        asyncio.run(run())
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    requests = [r for r in records if r["message"] == "working"]
    assert {r["request_id"] for r in requests} == {f"req-{i}" for i in range(5)}
    devices = [r for r in records if r["message"] == "Device operation completed"]
    assert len(devices) == 2
    assert all(
        r["host"] == r["device_id"] and r["operation"] == "set_power" for r in devices
    )


def test_background_task_context_drops_request_identity():
    from api.logging_config import background_context

    async def run():
        async def read():
            return request_id.get(), device_context.get()

        token = request_id.set("stream-opener")
        try:
            with log_context(device_id="plug"):
                task = asyncio.create_task(read(), context=background_context())
                assert await task == (None, None)
                assert request_id.get() == "stream-opener"
        finally:
            request_id.reset(token)

    asyncio.run(run())
