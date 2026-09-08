"""Domain error types + FastAPI translation.

Services raise these; they never import FastAPI. The API layer installs a handler
that turns them into JSON responses with the right status code.
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = 400

    def __init__(self, message: str, *, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__


class NotFound(AppError):
    status_code = 404


class BadRequest(AppError):
    status_code = 400


class Conflict(AppError):
    status_code = 409


class DependencyMissing(AppError):
    """An optional component (e.g. the face engine) is not installed."""

    status_code = 503


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message, "code": exc.code},
        )
