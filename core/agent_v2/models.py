"""Pydantic models for the Agent v2 Phase Engine."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VerificationType(str, Enum):
    TSC = "tsc"
    ESLINT = "eslint"
    CURL = "curl"
    SCREENSHOT = "screenshot"
    MIGRATION = "migration"
    MANUAL = "manual"


class Subphase(BaseModel):
    """Atomic unit of work within a phase."""
    id: str  # e.g. "3.1.2"
    description: str
    tool: str  # "cursor", "warp", "lovable", "auto"
    status: str = "pending"  # pending | staging | verifying | done | failed | paused
    action: Optional[Dict[str, Any]] = None  # {"type": "prompt", "value": "..."} or {"type": "command", "value": "..."}
    verification: Dict[str, Any] = Field(default_factory=lambda: {"type": VerificationType.TSC, "command": "npx tsc --noEmit"})
    retry_count: int = 0
    artifacts: List[str] = Field(default_factory=list)  # file paths touched
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class Phase(BaseModel):
    """A phase contains subphases."""
    id: str  # e.g. "P3.1"
    name: str
    description: Optional[str] = None
    subphases: List[Subphase] = Field(default_factory=list)
    status: str = "pending"


class Layer(BaseModel):
    """One of the five architectural layers."""
    id: str  # e.g. "L3"
    name: str
    description: Optional[str] = None
    phases: List[Phase] = Field(default_factory=list)
    status: str = "pending"


class MasterPlan(BaseModel):
    """The canonical blueprint for a project build."""
    project_id: str
    project_path: str
    description: str
    stack: List[str]
    layers: List[Layer]
    status: str = "draft"  # draft | approved | running | paused | completed | failed
    current_layer_id: Optional[str] = None
    current_phase_id: Optional[str] = None
    current_subphase_id: Optional[str] = None
    approval_mode: str = "step-by-step"  # approve-all | step-by-step
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    cost_accumulated_usd: float = 0.0
    tool_preferences: Dict[str, str] = Field(default_factory=dict)
