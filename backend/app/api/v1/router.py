"""
API v1 route registry.

Aggregates all endpoint routers under a single `api_router` instance mounted
by the FastAPI application. Each feature domain registers its own router with
a versioned prefix and Swagger tag.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    dashboard,
    ecosystem,
    model_monitoring,
    predict,
    recommendations,
    reports,
    shap,
    subscribers,
    behavioral_segments,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(predict.router, tags=["scoring"])
api_router.include_router(subscribers.router, prefix="/subscribers", tags=["subscribers"])
api_router.include_router(subscribers.router, prefix="/subscriber", tags=["subscribers"])  # Backward-compatible alias
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["recommendations"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(ecosystem.router, prefix="/ecosystem", tags=["ecosystem"])
api_router.include_router(shap.router, prefix="/shap", tags=["explainability"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(model_monitoring.router, prefix="/model", tags=["model"])
api_router.include_router(behavioral_segments.router, prefix="/behavioral-segments", tags=["behavioral-segments"])
