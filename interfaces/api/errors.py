# interfaces/api/errors.py
"""Format d'erreur contractuel — docs/api/CONTRAT.md §3."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    """Erreur HTTP métier ou ressource absente — corps ``{ error: { code, message, details } }``."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def error_payload(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_payload(code, message, details=details),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Enregistre les handlers globaux du contrat v1."""

    @app.exception_handler(ApiError)
    async def _api_error_handler(
        _request: Request,
        exc: ApiError,
    ) -> JSONResponse:
        return error_response(
            exc.status_code,
            exc.code,
            exc.message,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return error_response(
            422,
            "VALIDATION_ERROR",
            "Corps de requête invalide.",
            details={"issues": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def _internal_error_handler(
        _request: Request,
        _exc: Exception,
    ) -> JSONResponse:
        return error_response(
            500,
            "INTERNAL_ERROR",
            "Erreur interne du serveur.",
        )
