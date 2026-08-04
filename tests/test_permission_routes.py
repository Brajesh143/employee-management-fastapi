from fastapi.routing import APIRoute

from routers.employee import router


def test_employee_create_route_requires_permission_dependency():
    for route in router.routes:
        if isinstance(route, APIRoute) and route.name == "create_employee_api":
            dependency_calls = [dep.call for dep in route.dependant.dependencies]
            assert any(getattr(dep, "__name__", None) == "permission_checker" for dep in dependency_calls)
            return

    raise AssertionError("Employee create route was not found")
