"""
FastAPI application entry point for the Retnza retention intelligence platform.

Sets up CORS, rate limiting, model warm-loading on startup, and registers
all API route handlers under the configured version prefix.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.services.ml_service import get_ml_service


settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle handler.

    On startup, triggers a warm load of the champion model bundle so the first
    inference request does not pay a cold-start penalty. Silently continues if
    the model artifacts are not yet present (e.g., during build or test setup).
    """
    try:
        get_ml_service().bundle
    except FileNotFoundError:
        pass
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Telecom churn retention platform API",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
@limiter.limit("60/minute")
async def health(request: Request) -> dict:
    return {"status": "ok", "service": settings.APP_NAME.lower()}
