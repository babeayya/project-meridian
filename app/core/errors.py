"""Error taxonomy → RFC 7807 problem+json responses."""
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    title: str = "Internal error"

    def __init__(self, detail: str = "", **extra: Any) -> None:
        super().__init__(detail or self.title)
        self.detail = detail or self.title
        self.extra = extra


class EntityNotFound(AppError):
    status_code = 404
    code = "entity_not_found"
    title = "Entity not found"


class EntityNotResolved(AppError):
    status_code = 404
    code = "entity_not_resolved"
    title = "Could not resolve company from query"


class DataUnavailable(AppError):
    status_code = 503
    code = "data_unavailable"
    title = "No data provider could serve this request"

    def __init__(self, capability: str, providers_tried: list[str]) -> None:
        super().__init__(
            f"All providers failed for '{capability}'",
            capability=capability,
            providers_tried=providers_tried,
        )


class ModelNotApplicable(AppError):
    status_code = 422
    code = "model_not_applicable"
    title = "Valuation model not applicable to this company"


class AuthFailed(AppError):
    status_code = 401
    code = "auth_failed"
    title = "Missing or invalid API key"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        body = {
            "type": f"https://errors.equity-research/{exc.code}",
            "title": exc.title,
            "status": exc.status_code,
            "detail": exc.detail,
            **exc.extra,
        }
        return JSONResponse(body, status_code=exc.status_code,
                            media_type="application/problem+json")
