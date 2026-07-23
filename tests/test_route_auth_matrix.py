"""Structural guard against accidentally publishing a Bud API route."""

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from app.main import app

PUBLIC_ENDPOINTS = {
    "root",
    "health_check",
    "readiness_check",
    "get_version",
    "prometheus_metrics",
    "login",
    "refresh",
    "logout",
    "get_invite_info",
    "accept_invite",
    "verify_email",
    "forgot_password",
    "reset_password",
    "confirm_email_change",
    "register_runner",
    "register_teststation",
}

AUTH_DEPENDENCIES = {
    "get_current_active_entity",
    "get_current_runner",
    "get_current_teststation",
    "get_current_user",
    "get_uploader_entity",
    "require_admin",
    "require_runner_api_key",
    "require_teststation_api_key",
    "role_checker",
}


def _dependency_names(dependant: Dependant) -> set[str]:
    names: set[str] = set()
    pending = list(dependant.dependencies)
    while pending:
        dependency = pending.pop()
        call = dependency.call
        name = getattr(call, "__name__", None)
        if name:
            names.add(name)
        pending.extend(dependency.dependencies)
    return names


def _api_routes(router, prefix: str = ""):
    """Yield included routes across both flattened and nested FastAPI routers."""
    for route in router.routes:
        if isinstance(route, APIRoute):
            path = f"{prefix}{route.path}"
            if path.startswith("/api"):
                yield path, route
            continue

        original_router = getattr(route, "original_router", None)
        include_context = getattr(route, "include_context", None)
        if original_router is not None and include_context is not None:
            yield from _api_routes(
                original_router,
                f"{prefix}{include_context.prefix}",
            )


def test_every_non_public_api_route_has_an_authentication_boundary():
    unprotected: list[str] = []
    for path, route in _api_routes(app):
        if route.endpoint.__name__ in PUBLIC_ENDPOINTS:
            continue
        dependencies = _dependency_names(route.dependant)
        if dependencies.isdisjoint(AUTH_DEPENDENCIES):
            methods = ",".join(sorted(route.methods or set()))
            unprotected.append(f"{methods} {path} ({route.endpoint.__name__})")

    assert not unprotected, "Routes without an authentication boundary:\n" + "\n".join(unprotected)


def test_route_guard_detects_an_unprotected_dependency_tree():
    synthetic = Dependant()

    assert _dependency_names(synthetic).isdisjoint(AUTH_DEPENDENCIES)
