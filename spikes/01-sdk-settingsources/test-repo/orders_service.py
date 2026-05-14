"""Bob's orders microservice — minimal HTTP API.

Endpoints:
    POST /orders        Create a new order. Requires Bearer JWT scope=orders:write.
    GET  /orders/{id}   Fetch one order. Requires Bearer JWT scope=orders:read.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Order:
    id: str
    user_id: str
    line_items: list[dict[str, Any]] = field(default_factory=list)
    status: str = "pending"


_orders: dict[str, Order] = {}


def create_order(jwt_claims: dict[str, Any], payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Handle POST /orders.

    Status codes:
        201 Created       — order accepted, body returns the new order.
        401 Unauthorized  — JWT missing or invalid scope.
        400 Bad Request   — payload validation failed.
    """
    if "orders:write" not in jwt_claims.get("scopes", []):
        return 401, {"error": "missing scope orders:write"}

    if not payload.get("line_items"):
        return 400, {"error": "line_items required"}

    order_id = f"ord_{len(_orders) + 1:06d}"
    order = Order(id=order_id, user_id=jwt_claims["sub"], line_items=payload["line_items"])
    _orders[order_id] = order
    return 201, {"id": order.id, "status": order.status}


def get_order(jwt_claims: dict[str, Any], order_id: str) -> tuple[int, dict[str, Any]]:
    """Handle GET /orders/{id}.

    Status codes:
        200 OK            — order found, body returns it.
        401 Unauthorized  — JWT missing or invalid scope.
        404 Not Found     — order does not exist or is not owned by caller.
    """
    if "orders:read" not in jwt_claims.get("scopes", []):
        return 401, {"error": "missing scope orders:read"}

    order = _orders.get(order_id)
    if not order or order.user_id != jwt_claims["sub"]:
        return 404, {"error": "not found"}

    return 200, {"id": order.id, "status": order.status, "line_items": order.line_items}
