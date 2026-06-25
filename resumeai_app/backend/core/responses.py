"""
backend/core/responses.py — Standardized JSON response schema for Phase 4 endpoints.

Every Phase 4 API endpoint returns:
    Success: {"success": true,  "message": "...", "data": {...}, "meta": {...}}
    Error:   {"success": false, "message": "...", "errors": ...}

NOTE: Existing Phase 1–3 endpoints (/api/*, /ai/*) retain their original response
format to preserve backward compatibility with the frontend and existing tests.
"""
from __future__ import annotations

from typing import Any, Optional
from fastapi.responses import JSONResponse


def success(
    data: Any = None,
    message: str = "OK",
    meta: Optional[dict] = None,
    status_code: int = 200,
) -> JSONResponse:
    """Return a standardized success response."""
    payload: dict = {"success": True, "message": message, "data": data}
    if meta:
        payload["meta"] = meta
    return JSONResponse(content=payload, status_code=status_code)


def error(
    message: str,
    errors: Any = None,
    status_code: int = 400,
) -> JSONResponse:
    """Return a standardized error response."""
    payload: dict = {"success": False, "message": message}
    if errors is not None:
        payload["errors"] = errors
    return JSONResponse(content=payload, status_code=status_code)


def paginated(
    items: list,
    total: int,
    page: int,
    page_size: int,
    message: str = "OK",
) -> JSONResponse:
    """Return paginated data with total_pages and total_records metadata."""
    import math
    total_pages = math.ceil(total / page_size) if page_size else 1
    return success(
        data=items,
        message=message,
        meta={
            "page": page,
            "page_size": page_size,
            "total_records": total,
            "total_pages": total_pages,
        },
    )
