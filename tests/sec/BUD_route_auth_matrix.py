"""
* @file     ${tests/sec/BUD_route_auth_matrix.py}
* @copyright © EmbedLabs, Aachen ${2026} - all rights reserved
* @brief    Every Bud API route outside the public list depends on an authentication guard.
* @author   Amine El Omari
* @date     2026-11-10
* @version  1.0.0
* @note     This module tests the app's routes; the first-run setup endpoints are public.
"""

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from app import main
from tests.sec.route_auth_matrix import RouteAuthMatrixBase


def dependency_names(dependant):
    """The names of every callable in a dependency tree."""
    names = set()
    pending = list(dependant.dependencies)
    while pending:
        dependency = pending.pop()
        name = getattr(dependency.call, "__name__", None)
        if name:
            names.add(name)
        pending.extend(dependency.dependencies)
    return names


def api_routes(router, api_prefix, prefix=""):
    """The API routes of a router with their full paths, across nested routers."""
    for route in router.routes:
        if isinstance(route, APIRoute):
            path = f"{prefix}{route.path}"
            if path.startswith(api_prefix):
                yield path, route
            continue
        original_router = getattr(route, "original_router", None)
        include_context = getattr(route, "include_context", None)
        if original_router is not None and include_context is not None:
            yield from api_routes(original_router, api_prefix, f"{prefix}{include_context.prefix}")


class RouteAuthMatrixTest(RouteAuthMatrixBase):

    def setUpClass(self):
        super().setUpClass()
        routes = list(api_routes(main.app, self.parameters.API_PREFIX))
        self.tc_route_count = len(routes)
        self.tc_unprotected = [
            f"{','.join(sorted(route.methods or set()))} {path} ({route.endpoint.__name__})"
            for path, route in routes
            if route.endpoint.__name__ not in self.parameters.PUBLIC_ENDPOINTS
            and dependency_names(route.dependant).isdisjoint(self.parameters.AUTH_DEPENDENCIES)
        ]
        self.tc_empty_tree = dependency_names(Dependant())

    def tearDownClass(self):
        super().tearDownClass()


if __name__ == "__main__":
    RouteAuthMatrixTest().run()
