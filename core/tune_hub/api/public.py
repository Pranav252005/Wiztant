"""Public REST API for Tune Hub (FastAPI).

Endpoints:
  POST   /tune                    — Initiate learning
  POST   /resolve                 — Hot-path tune resolution
  GET    /tunes/{user_id}         — List user's tunes
  DELETE /tunes/{user_id}/{tune_id} — Delete a tune
  POST   /tunes/{user_id}/{tune_id}/rollback — Rollback (Power only)
  POST   /tunes/{user_id}/{tune_id}/share   — Share tune (Pro/Power)
  GET    /sync/pending            — Pull pending syncs
  GET    /credits/{user_id}/balance — Check credit balance
  GET    /stats/{user_id}         — Tune application stats
"""

from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from fastapi import APIRouter, HTTPException, Request
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    APIRouter = object  # type: ignore

from ..base import LearnedModel, TuneStatus
from ..credit_system.abstract import CreditBalance
from ..orchestrator import TuneHub, TuneRequest, TuneResult


class _FakeRouter:
    """Fallback when FastAPI is not installed."""

    def get(self, path: str, **kwargs):
        return lambda f: f

    def post(self, path: str, **kwargs):
        return lambda f: f

    def delete(self, path: str, **kwargs):
        return lambda f: f


if FASTAPI_AVAILABLE:
    router = APIRouter(prefix="/tunehub", tags=["tunehub"])
else:
    router = _FakeRouter()  # type: ignore


# ── Helper to get TuneHub from app state ──


def _get_hub(request: Any) -> TuneHub:
    if not FASTAPI_AVAILABLE:
        raise RuntimeError("FastAPI not available")
    hub: Optional[TuneHub] = getattr(request.app.state, "tune_hub", None)
    if hub is None:
        raise HTTPException(status_code=503, detail="TuneHub not initialized")
    return hub


# ── Endpoints ──


@router.post("/tune")
async def tune(request: Request, body: Dict[str, Any]):
    """Initiate learning for a feature."""
    hub = _get_hub(request)
    req = TuneRequest(
        user_id=body["user_id"],
        feature_name=body["feature_name"],
        task=body["task"],
        approved_credits=body.get("approved_credits", 100),
        tier=body.get("tier", "free"),
        urgency=body.get("urgency", "normal"),
        context=body.get("context", {}),
    )
    result = hub.tune_feature(req)
    return {
        "success": result.success,
        "credits_used": result.credits_used,
        "credits_remaining": result.credits_remaining,
        "message": result.message,
        "reusable": result.reusable,
        "sync_status": result.sync_status,
        "model": result.model.to_storage_format() if result.model else None,
    }


@router.post("/resolve")
async def resolve(request: Request, body: Dict[str, Any]):
    """Hot-path tune resolution at feature trigger (< 50ms)."""
    hub = _get_hub(request)
    result = hub.resolve_tune(
        user_id=body["user_id"],
        feature_name=body["feature_name"],
        task=body["task"],
        feature_input=body.get("feature_input", {}),
    )
    return result


@router.get("/tunes/{user_id}")
async def list_tunes(request: Request, user_id: str, feature_name: Optional[str] = None):
    """List user's tunes."""
    hub = _get_hub(request)
    tunes = hub.list_tunes(user_id, feature_name)
    return {"tunes": [t.to_storage_format() for t in tunes]}


@router.delete("/tunes/{user_id}/{tune_id}")
async def delete_tune(request: Request, user_id: str, tune_id: str):
    """Delete a tune."""
    hub = _get_hub(request)
    success = hub.delete_tune(user_id, tune_id)
    if not success:
        raise HTTPException(status_code=404, detail="Tune not found")
    return {"deleted": True}


@router.post("/tunes/{user_id}/{tune_id}/rollback")
async def rollback_tune(request: Request, user_id: str, tune_id: str, body: Dict[str, Any]):
    """Rollback to a previous version (Power only)."""
    hub = _get_hub(request)
    to_version = body.get("to_version")
    if to_version is None:
        raise HTTPException(status_code=400, detail="to_version required")
    model = hub.rollback_tune(user_id, tune_id, to_version)
    if model is None:
        raise HTTPException(status_code=404, detail="Tune or version not found")
    return {"model": model.to_storage_format()}


@router.post("/tunes/{user_id}/{tune_id}/share")
async def share_tune(request: Request, user_id: str, tune_id: str, body: Dict[str, Any]):
    """Share tune with another user (Pro/Power)."""
    # Placeholder: actual sharing logic depends on sharing backend
    return {
        "shared": True,
        "tune_id": tune_id,
        "shared_with": body.get("shared_with"),
        "permission": body.get("permission", "read"),
    }


@router.get("/sync/pending")
async def pending_syncs(request: Request, user_id: str):
    """Pull pending syncs for Desktop 1 startup."""
    hub = _get_hub(request)
    if hub.sync_manager is None:
        return {"pending": []}
    pending = hub.sync_manager.pull_pending(user_id)
    return {"pending": pending}


@router.get("/credits/{user_id}/balance")
async def credit_balance(request: Request, user_id: str):
    """Check credit balance."""
    hub = _get_hub(request)
    balance = hub.credit_tracker.get_balance(user_id)
    return {
        "user_id": balance.user_id,
        "available": balance.available,
        "consumed": balance.consumed,
        "reserved": balance.reserved,
    }


@router.get("/stats/{user_id}")
async def tune_stats(request: Request, user_id: str):
    """Get tune application statistics for a user."""
    hub = _get_hub(request)
    tunes = hub.list_tunes(user_id)
    active = [t for t in tunes if t.status == TuneStatus.DEPLOYED]
    return {
        "user_id": user_id,
        "total_tunes": len(tunes),
        "active_tunes": len(active),
        "features_with_tunes": list(set(t.feature_name for t in active)),
        "tunes": [t.to_storage_format() for t in tunes],
    }
