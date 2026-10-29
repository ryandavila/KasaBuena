"""Read-only, in-memory diagnostics."""

from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config import get_settings
from ..kasa_service import registry
from ..logging_config import request_id
from ..schedule_store import schedules
from ..schemas import Diagnostics

router = APIRouter(prefix="/api")


def package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "unknown"


@router.get("/ready")
async def ready():
    if registry.ready:
        return {"status": "ready"}
    return JSONResponse(
        {"status": "not_ready", "request_id": request_id.get()},
        status_code=503,
    )


@router.get("/diagnostics", response_model=Diagnostics)
async def diagnostics(request: Request) -> Diagnostics:
    tasks = getattr(request.app.state, "background_tasks", {})
    states = {}
    for name, task in tasks.items():
        states[name] = (
            "cancelled"
            if task.cancelled()
            else "running"
            if not task.done()
            else "failed"
            if task.exception()
            else "finished"
        )
    warnings = []
    rules = schedules.list_rules()
    if registry.startup_error:
        warnings.append(
            f"Startup discovery failed ({registry.startup_error}). Restart to retry initialization."
        )
    if get_settings().location is None and any(
        rule.get("enabled") and rule.get("kind") in ("sunrise", "sunset")
        for rule in rules
    ):
        warnings.append(
            "Sunrise/sunset schedules cannot run until a location is configured."
        )
    warnings.extend(
        f"Background task {name} {state}."
        for name, state in states.items()
        if state in ("failed", "cancelled")
    )
    return Diagnostics(
        app_version=package_version("kasabuena"),
        python_kasa_version=package_version("python-kasa"),
        ready=registry.ready,
        startup_error=registry.startup_error,
        discovering=registry.discovering,
        last_scan_at=registry.last_scan_at,
        last_scan=registry.last_scan if registry.last_scan_at else None,
        devices=list(registry.device_health.values()),
        unreadable_hosts=sorted(registry._unreadable_hosts),
        unsupported_hosts=sorted(
            h.host
            for h in registry.device_health.values()
            if h.error_class == "UnsupportedDeviceError" and h.consecutive_failures
        ),
        cloud_fallback_enabled=registry._cloud_client is not None,
        cloud_device_count=len(registry._cloud_devices),
        background_tasks=states,
        warnings=warnings,
    )
