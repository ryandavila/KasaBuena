import asyncio
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from kasa.exceptions import AuthenticationError

from api import kasa_service
from api.kasa_service import DeviceRegistry
from api.routers import diagnostics as routes
from api.testing.fake_devices import FakeDevice, FakeDiscover


def client_for(reg, monkeypatch):
    monkeypatch.setattr(routes, "registry", reg)
    app = FastAPI()
    app.include_router(routes.router)
    return TestClient(app)


def test_ready_distinguishes_startup_failure_from_completion(monkeypatch):
    reg = DeviceRegistry()
    client = client_for(reg, monkeypatch)
    assert client.get("/api/ready").status_code == 503
    reg.discover_all = AsyncMock(side_effect=RuntimeError("private"))
    asyncio.run(reg.run_startup_discovery())
    assert reg.startup_complete
    assert client.get("/api/ready").status_code == 503
    body = client.get("/api/diagnostics").json()
    assert body["startup_error"] == "RuntimeError"
    assert "private" not in str(body)
    reg.discover_all = AsyncMock()
    reg.attach_cloud = AsyncMock()
    asyncio.run(reg.run_startup_discovery())
    assert client.get("/api/ready").status_code == 200


def test_health_failure_recovery_and_latest_scan(monkeypatch):
    fake = FakeDiscover()
    device = FakeDevice("10.0.0.1")
    fake.targets[device.host] = {device.host: device}
    monkeypatch.setattr(kasa_service, "Discover", fake)
    reg = DeviceRegistry()
    asyncio.run(reg.discover_target(device.host))
    device._fail_update = AuthenticationError("private password")
    asyncio.run(reg._refresh(device))
    asyncio.run(reg._refresh(device))
    client = client_for(reg, monkeypatch)
    body = client.get("/api/diagnostics").json()
    health = body["devices"][0]
    assert health["consecutive_failures"] == 2
    assert health["error_class"] == "AuthenticationError"
    assert health["last_seen"] and health["last_error_at"]
    assert body["last_scan_at"]
    assert body["last_scan"]["stats"]["responded"] == 1
    assert "private password" not in str(body)
    device._fail_update = False
    asyncio.run(reg._refresh(device))
    recovered = client.get("/api/diagnostics").json()["devices"][0]
    assert recovered["consecutive_failures"] == 0
    assert recovered["last_error_at"] == health["last_error_at"]


def test_client_errors_opt_in_and_limits(monkeypatch, caplog):
    from api.config import Settings

    settings = Settings(_env_file=None)
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    client = client_for(DeviceRegistry(), monkeypatch)
    payload = {"kind": "error", "message": "Something broke\nsecond line"}
    assert client.post("/api/client-errors", json=payload).status_code == 404
    settings.kasa_client_errors = True
    assert client.post("/api/client-errors", json=payload).status_code == 204
    assert "Something broke\\nsecond line" in caplog.text
    payload["message"] = "x" * 1001
    assert client.post("/api/client-errors", json=payload).status_code == 422


def test_diagnostics_exposes_history_and_schedule_warnings(monkeypatch):
    from api.config import Settings
    from api.run_history import RunHistory

    history = RunHistory()
    with history.track("schedule", "timer", "rule-1") as run:
        run.result = "missed"
    monkeypatch.setattr(routes, "run_history", history)
    monkeypatch.setattr(routes, "get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(
        routes.schedules,
        "list_rules",
        lambda: [
            {"id": "rule-1", "last_fired": {"result": "missed"}},
            {"id": "sun", "enabled": True, "kind": "sunrise"},
        ],
    )
    body = client_for(DeviceRegistry(), monkeypatch).get("/api/diagnostics").json()
    assert body["recent_runs"][0]["result"] == "missed"
    assert any("location" in warning for warning in body["warnings"])
    assert any("rule-1" in warning for warning in body["warnings"])


def test_absent_energy_meter_does_not_degrade_device_health(caplog):
    import pytest

    from api.kasa_service import EnergyUnsupportedError

    reg = DeviceRegistry()
    device = FakeDevice("10.0.0.1", has_energy=False)
    reg._devices[device.host] = device
    asyncio.run(reg._refresh(device))
    with caplog.at_level("INFO"), pytest.raises(EnergyUnsupportedError):
        asyncio.run(reg.read_energy_snapshot(device.host))
    assert reg.device_health[device.host].consecutive_failures == 0
    assert reg.device_health[device.host].last_error is None
    assert not caplog.records
