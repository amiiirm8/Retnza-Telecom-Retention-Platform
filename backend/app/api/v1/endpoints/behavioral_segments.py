"""
Behavioral Segments endpoint — serves data-driven subscriber segments.

Pipeline position:
  Serves the output of the analytics behavioral segmentation module to the frontend.

Workflow stage:
  GET /api/v1/behavioral-segments/summary — overall metrics, cluster profiles.

Security:
  All endpoints require authentication via CurrentUser dependency.
"""

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.core.deps import CurrentUser

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SEGMENTS_JSON_PATH = PROJECT_ROOT / "outputs" / "analytics" / "behavioral_segments_summary.json"


@router.get("/summary")
async def behavioral_segments_summary(_user: CurrentUser) -> dict[str, Any]:
    """
    Return the behavioral segments summary, including cluster profiles and metrics.

    Args:
        _user: Authenticated user.

    Returns:
        Dict representing the behavioral segments.
    """
    if not SEGMENTS_JSON_PATH.exists():
        return {
            "error": "Behavioral segments summary not found.",
            "metrics": {},
            "profiles": [],
            "n_clusters": 0
        }
    
    data = json.loads(SEGMENTS_JSON_PATH.read_text(encoding="utf-8"))
    
    # Optional: Format the data structure for frontend convenience
    return data
