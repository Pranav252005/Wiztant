"""
core/credit_system.py — Dynamic credit engine for Bistent.

Calculates credit costs based on model choice and token usage.
Deducts credits atomically before expensive operations.
Supports Supabase primary storage with local JSON fallback.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# =============================================================
#  PATHS & CONSTANTS
# =============================================================

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MODEL_PRICES_PATH = _PROJECT_ROOT / "data" / "model_prices.json"
_CREDITS_LOCAL_PATH = _PROJECT_ROOT / "data" / "credits.json"

# Default fallback values if registry is missing
_DEFAULT_MARKUP = 5
_DEFAULT_COST_PER_CREDIT = 0.006

# =============================================================
#  TIER DEFAULTS
# =============================================================

# Monthly credit allocations per tier
TIER_ALLOCATIONS: Dict[str, int] = {
    "free": 50,
    "pro": 1_000,
    "power": 5_000,
    "trial": 50,
}

# How many days before a monthly reset happens
_RESET_DAYS = 30


def get_default_tier() -> str:
    """Return the default tier for new users.

    - If WIZTANT_DEV_MODE=true, default to 'power' for developer testing.
    - If CURRENT_TIER is set explicitly, use that.
    - Otherwise default to 'free' (published app behaviour).
    """
    dev_mode = os.getenv("WIZTANT_DEV_MODE", "").lower().strip()
    if dev_mode in ("1", "true", "yes"):
        return "power"
    env_tier = os.getenv("CURRENT_TIER", "").lower().strip()
    if env_tier in TIER_ALLOCATIONS:
        return env_tier
    return "free"


def _parse_iso(dt_str: str) -> Optional[datetime]:
    """Safely parse an ISO datetime string."""
    if not dt_str:
        return None
    try:
        # Handle both with and without timezone
        s = str(dt_str).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _is_reset_due(reset_at_str: Optional[str]) -> bool:
    """Check if 30 days have passed since the last reset."""
    if not reset_at_str:
        return True
    reset_at = _parse_iso(reset_at_str)
    if reset_at is None:
        return True
    now = datetime.now(timezone.utc)
    # Make reset_at timezone-aware if it isn't
    if reset_at.tzinfo is None:
        reset_at = reset_at.replace(tzinfo=timezone.utc)
    return (now - reset_at).days >= _RESET_DAYS


# =============================================================
#  MODEL PRICE REGISTRY
# =============================================================

@dataclass(frozen=True)
class ModelPrice:
    """Price info for a single model."""

    input_per_million: float
    output_per_million: float
    category: str
    speed: str

    @property
    def input_per_token(self) -> float:
        return self.input_per_million / 1_000_000

    @property
    def output_per_token(self) -> float:
        return self.output_per_million / 1_000_000


class ModelRegistry:
    """Loads and serves model prices from data/model_prices.json"""

    def __init__(self, path: Path = _MODEL_PRICES_PATH) -> None:
        self._path = path
        self._data: Dict[str, Any] = {}
        self._models: Dict[str, ModelPrice] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            print(f"[CreditSystem] Model registry not found at {self._path}, using empty defaults")
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except Exception as e:
            print(f"[CreditSystem] Failed to load model registry: {e}")
            return

        for model_id, info in self._data.get("models", {}).items():
            self._models[model_id] = ModelPrice(
                input_per_million=info.get("input", 0.0),
                output_per_million=info.get("output", 0.0),
                category=info.get("category", "unknown"),
                speed=info.get("speed", "unknown"),
            )

    def get_price(self, model_id: str) -> Optional[ModelPrice]:
        return self._models.get(model_id)

    def get_markup(self) -> int:
        return self._data.get("markup_multiplier", _DEFAULT_MARKUP)

    def get_cost_per_credit(self, tier: str = "pro") -> float:
        rates = self._data.get("cost_per_credit", {})
        return rates.get(tier.lower(), _DEFAULT_COST_PER_CREDIT)

    def get_default_model(self, feature: str) -> str:
        defaults = self._data.get("defaults", {})
        key = f"{feature}_model" if not feature.endswith("_model") else feature
        return defaults.get(key, "google/gemini-3-flash-preview")

    def get_tunehub_iterations(self, complexity: str) -> int:
        iters = self._data.get("tunehub_iterations", {"LOW": 3, "MEDIUM": 10, "HIGH": 30})
        return iters.get(complexity.upper(), 3)

    def get_token_estimate(self, feature: str) -> Tuple[int, int]:
        estimates = self._data.get("token_estimates", {})
        est = estimates.get(feature, {"input": 3000, "output": 2000})
        return (est.get("input", 3000), est.get("output", 2000))

    def list_models(self) -> Dict[str, ModelPrice]:
        return dict(self._models)


# Singleton registry
_registry: Optional[ModelRegistry] = None


def _get_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


# =============================================================
#  CREDIT CALCULATION
# =============================================================

def calculate_api_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate raw API cost in dollars for a model + token usage.
    Returns 0.0 if model is not found in registry.
    """
    registry = _get_registry()
    price = registry.get_price(model_id)
    if price is None:
        print(f"[CreditSystem] Warning: unknown model '{model_id}', assuming $0 cost")
        return 0.0
    return (input_tokens * price.input_per_token) + (output_tokens * price.output_per_token)


def calculate_credits(
    api_cost: float,
    tier: str = "pro",
    minimum: int = 1,
) -> int:
    """
    Convert API cost to credits using the formula:
    credits = ceil(api_cost * markup / cost_per_credit)
    """
    registry = _get_registry()
    markup = registry.get_markup()
    cost_per_credit = registry.get_cost_per_credit(tier)

    if cost_per_credit <= 0:
        cost_per_credit = _DEFAULT_COST_PER_CREDIT

    credits = math.ceil(api_cost * markup / cost_per_credit)
    return max(minimum, credits)


def calculate_reprompt_credits(
    model_id: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    tier: str = "pro",
) -> int:
    """
    Calculate RePrompt credits.
    Uses defaults from registry if args not provided.
    """
    registry = _get_registry()
    model = model_id or registry.get_default_model("reprompt")
    in_tok, out_tok = registry.get_token_estimate("reprompt")
    if input_tokens is not None:
        in_tok = input_tokens
    if output_tokens is not None:
        out_tok = output_tokens

    api_cost = calculate_api_cost(model, in_tok, out_tok)
    return calculate_credits(api_cost, tier)


def calculate_judge_credits(
    model_id: Optional[str] = None,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    tier: str = "pro",
) -> int:
    """Calculate LLM Judge credits."""
    registry = _get_registry()
    model = model_id or registry.get_default_model("tunehub_judge")
    in_tok, out_tok = registry.get_token_estimate("judge")
    if input_tokens is not None:
        in_tok = input_tokens
    if output_tokens is not None:
        out_tok = output_tokens

    api_cost = calculate_api_cost(model, in_tok, out_tok)
    return calculate_credits(api_cost, tier)


def calculate_tunehub_credits(
    complexity: str,
    feature_model: Optional[str] = None,
    judge_model: Optional[str] = None,
    feature_tokens: Optional[Tuple[int, int]] = None,
    judge_tokens: Optional[Tuple[int, int]] = None,
    tier: str = "pro",
) -> int:
    """
    Calculate TuneHub credits.
    Total = iterations × (feature_credits_per_iter + judge_credits_per_iter)
    """
    registry = _get_registry()
    iterations = registry.get_tunehub_iterations(complexity)

    # Feature cost per iteration
    f_model = feature_model or registry.get_default_model("reprompt")
    f_in, f_out = feature_tokens or registry.get_token_estimate("reprompt")
    feature_api_cost = calculate_api_cost(f_model, f_in, f_out)
    feature_credits = calculate_credits(feature_api_cost, tier)

    # Judge cost per iteration
    j_model = judge_model or registry.get_default_model("tunehub_judge")
    j_in, j_out = judge_tokens or registry.get_token_estimate("judge")
    judge_api_cost = calculate_api_cost(j_model, j_in, j_out)
    judge_credits = calculate_credits(judge_api_cost, tier)

    per_iteration = feature_credits + judge_credits
    return per_iteration * iterations


def calculate_dictation_credits() -> int:
    """Dictation is a fixed 1 credit (Whisper is extremely cheap)."""
    return 1


def calculate_agent_credits(
    estimated_steps: int = 1,
    tier: str = "pro",
) -> int:
    """
    Calculate Agent task credits.
    Base fee + per-step cost. Minimum 5 credits for any task.
    """
    base = 5
    per_step = 2
    total = base + (max(0, estimated_steps - 1) * per_step)
    return max(5, total)


# =============================================================
#  BALANCE MANAGEMENT
# =============================================================

class CreditBalanceManager:
    """Manages user credit balances: Supabase primary, local JSON fallback."""

    def __init__(self, local_path: Path = _CREDITS_LOCAL_PATH) -> None:
        self._local_path = local_path
        self._cache: Dict[str, Dict[str, Any]] = {}

    # -- Local JSON helpers --

    def _load_local(self) -> Dict[str, Any]:
        if not self._local_path.exists():
            return {}
        try:
            with open(self._local_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_local(self, data: Dict[str, Any]) -> None:
        self._local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self._local_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[CreditSystem] Failed to save local credits: {e}")

    def _get_user_data(self, user_id: str) -> Dict[str, Any]:
        if user_id in self._cache:
            return self._cache[user_id]
        data = self._load_local()
        user_data = data.get(user_id, {})
        self._cache[user_id] = user_data
        return user_data

    def _set_user_data(self, user_id: str, user_data: Dict[str, Any]) -> None:
        self._cache[user_id] = user_data
        all_data = self._load_local()
        all_data[user_id] = user_data
        self._save_local(all_data)

    def _broadcast_update(self, user_id: str) -> None:
        """Broadcast credit balance to overlay via WebSocket."""
        try:
            from core.ws_bridge import send_credits_update
            balance = self.get_balance(user_id)
            tier = self.get_tier(user_id)
            allocation = self.get_tier_credits(tier)
            send_credits_update(balance, tier, allocation)
        except Exception:
            pass

    # -- Balance operations --

    def _check_monthly_reset(self, user_id: str, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Reset balance if 30 days have passed since last reset. Returns possibly-mutated user_data."""
        reset_at = user_data.get("reset_at")
        if _is_reset_due(reset_at):
            tier = self.get_tier(user_id)
            allocation = self.get_tier_credits(tier)
            old_balance = user_data.get("balance", allocation)
            user_data["balance"] = allocation
            user_data["tier"] = tier
            user_data["reset_at"] = datetime.now(timezone.utc).isoformat()
            # Record the reset as a transaction for auditability
            transactions = user_data.get("transactions", [])
            transactions.append({
                "feature": "monthly_reset",
                "model": None,
                "amount": 0,
                "balance_after": allocation,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "note": f"Monthly reset: {old_balance} → {allocation} ({tier} plan)",
            })
            user_data["transactions"] = transactions[-100:]
            self._set_user_data(user_id, user_data)
            self._broadcast_update(user_id)
            print(f"[CreditSystem] Monthly reset applied for {user_id}: {old_balance} → {allocation} ({tier})")
        return user_data

    def get_balance(self, user_id: str) -> int:
        """Get current credit balance for a user. Initializes new users with full tier allocation.
        Automatically applies monthly reset if 30 days have passed."""
        # Try Supabase first
        try:
            from core.supabase_client import is_configured, get_client
            if is_configured():
                client = get_client()
                if client:
                    result = (
                        client.table("credits")
                        .select("balance, reset_at, tier")
                        .eq("user_id", user_id)
                        .execute()
                    )
                    if result.data:
                        row = result.data[0]
                        reset_at = row.get("reset_at")
                        if _is_reset_due(reset_at):
                            tier = self.get_tier(user_id)
                            allocation = self.get_tier_credits(tier)
                            client.table("credits").update({
                                "balance": allocation,
                                "reset_at": datetime.now(timezone.utc).isoformat(),
                            }).eq("user_id", user_id).execute()
                            self._broadcast_update(user_id)
                            print(f"[CreditSystem] Monthly reset applied (Supabase) for {user_id}: {row.get('balance')} → {allocation} ({tier})")
                            return allocation
                        return row.get("balance", 0)
                    else:
                        # Auto-init new Supabase user with tier allocation
                        tier = self.get_tier(user_id)
                        allocation = self.get_tier_credits(tier)
                        self.initialize_user(user_id, tier)
                        return allocation
        except Exception:
            pass

        # Fallback to local
        user_data = self._get_user_data(user_id)
        # Check monthly reset BEFORE returning balance
        user_data = self._check_monthly_reset(user_id, user_data)
        balance = user_data.get("balance")
        if balance is None:
            # Initialize new user with full tier allocation
            tier = self.get_tier(user_id)
            allocation = self.get_tier_credits(tier)
            user_data["balance"] = allocation
            user_data["tier"] = tier
            user_data["reset_at"] = datetime.now(timezone.utc).isoformat()
            self._set_user_data(user_id, user_data)
            return allocation
        return balance

    def get_tier(self, user_id: str) -> str:
        """Get user's tier. Checks env var first, then Supabase, then local."""
        env_tier = os.getenv("CURRENT_TIER", "").lower().strip()
        if env_tier in TIER_ALLOCATIONS:
            return env_tier

        try:
            from core.supabase_client import is_configured, get_client
            if is_configured():
                client = get_client()
                if client:
                    result = (
                        client.table("credits")
                        .select("tier")
                        .eq("user_id", user_id)
                        .execute()
                    )
                    if result.data:
                        return result.data[0].get("tier", get_default_tier())
        except Exception:
            pass

        user_data = self._get_user_data(user_id)
        return user_data.get("tier", get_default_tier())

    def get_tier_credits(self, tier: str) -> int:
        """Get monthly credit allocation for a tier."""
        return TIER_ALLOCATIONS.get(tier.lower(), 0)

    def can_afford(self, user_id: str, amount: int) -> bool:
        """Check if user has enough credits."""
        return self.get_balance(user_id) >= amount

    def deduct(
        self,
        user_id: str,
        feature: str,
        amount: int,
        model: Optional[str] = None,
    ) -> bool:
        """
        Atomically deduct credits. Returns True if successful.
        Syncs to Supabase if available, falls back to local JSON.
        """
        if amount <= 0:
            return True

        current = self.get_balance(user_id)
        if current < amount:
            print(f"[CreditSystem] Insufficient credits for {user_id}: need {amount}, have {current}")
            return False

        new_balance = current - amount

        # Try Supabase first
        try:
            from core.supabase_client import is_configured, get_client
            if is_configured():
                client = get_client()
                if client:
                    client.table("credits").update({"balance": new_balance}).eq(
                        "user_id", user_id
                    ).execute()

                    client.table("credit_transactions").insert({
                        "user_id": user_id,
                        "feature": feature,
                        "model": model,
                        "amount": amount,
                        "balance_after": new_balance,
                    }).execute()

                    # Update cache
                    self._cache[user_id] = {"balance": new_balance, "tier": self.get_tier(user_id)}
                    self._broadcast_update(user_id)
                    # Broadcast consumption event (exclude dictation from visibility)
                    if feature != "dictation":
                        try:
                            from core.ws_bridge import send_credit_consumed
                            send_credit_consumed(feature, amount, new_balance, model)
                        except Exception:
                            pass
                    return True
        except Exception as e:
            print(f"[CreditSystem] Supabase deduct failed, falling back to local: {e}")

        # Fallback to local
        user_data = self._get_user_data(user_id)
        user_data["balance"] = new_balance
        transactions = user_data.get("transactions", [])
        transactions.append({
            "feature": feature,
            "model": model,
            "amount": amount,
            "balance_after": new_balance,
            "created_at": datetime.utcnow().isoformat(),
        })
        user_data["transactions"] = transactions[-100:]  # Keep last 100
        self._set_user_data(user_id, user_data)
        self._broadcast_update(user_id)
        # Broadcast consumption event (exclude dictation from visibility)
        if feature != "dictation":
            try:
                from core.ws_bridge import send_credit_consumed
                send_credit_consumed(feature, amount, new_balance, model)
            except Exception:
                pass
        return True

    def refill(self, user_id: str, amount: int, source: str = "manual") -> None:
        """Add credits to a user's balance."""
        current = self.get_balance(user_id)
        new_balance = current + amount

        try:
            from core.supabase_client import is_configured, get_client
            if is_configured():
                client = get_client()
                if client:
                    client.table("credits").update({"balance": new_balance}).eq(
                        "user_id", user_id
                    ).execute()
                    self._cache[user_id] = {"balance": new_balance, "tier": self.get_tier(user_id)}
                    return
        except Exception:
            pass

        user_data = self._get_user_data(user_id)
        user_data["balance"] = new_balance
        self._set_user_data(user_id, user_data)

    def reset_monthly(self, user_id: str) -> None:
        """Reset credits to tier allocation (call on billing anniversary)."""
        tier = self.get_tier(user_id)
        allocation = self.get_tier_credits(tier)
        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            from core.supabase_client import is_configured, get_client
            if is_configured():
                client = get_client()
                if client:
                    client.table("credits").update({
                        "balance": allocation,
                        "reset_at": now_iso,
                    }).eq("user_id", user_id).execute()
                    self._cache[user_id] = {"balance": allocation, "tier": tier}
                    self._broadcast_update(user_id)
                    return
        except Exception:
            pass

        user_data = self._get_user_data(user_id)
        user_data["balance"] = allocation
        user_data["tier"] = tier
        user_data["reset_at"] = now_iso
        self._set_user_data(user_id, user_data)
        self._broadcast_update(user_id)

    def initialize_user(self, user_id: str, tier: str = "free") -> None:
        """Set up a new user with their tier allocation."""
        allocation = self.get_tier_credits(tier)
        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            from core.supabase_client import is_configured, get_client
            if is_configured():
                client = get_client()
                if client:
                    client.table("credits").upsert({
                        "user_id": user_id,
                        "balance": allocation,
                        "tier": tier,
                        "reset_at": now_iso,
                    }).execute()
                    self._cache[user_id] = {"balance": allocation, "tier": tier}
                    return
        except Exception:
            pass

        user_data = self._get_user_data(user_id)
        if user_data.get("balance", 0) == 0:
            user_data["balance"] = allocation
            user_data["tier"] = tier
            user_data["reset_at"] = now_iso
            self._set_user_data(user_id, user_data)


# Singleton manager instance
_manager: Optional[CreditBalanceManager] = None


def _get_manager() -> CreditBalanceManager:
    global _manager
    if _manager is None:
        _manager = CreditBalanceManager()
    return _manager


# =============================================================
#  PUBLIC API
# =============================================================

def get_balance(user_id: str) -> int:
    return _get_manager().get_balance(user_id)


def get_tier(user_id: str) -> str:
    return _get_manager().get_tier(user_id)


def get_tier_credits(tier: str) -> int:
    return _get_manager().get_tier_credits(tier)


def can_afford(user_id: str, amount: int) -> bool:
    return _get_manager().can_afford(user_id, amount)


def deduct(
    user_id: str,
    feature: str,
    amount: int,
    model: Optional[str] = None,
) -> bool:
    return _get_manager().deduct(user_id, feature, amount, model)


def refill(user_id: str, amount: int, source: str = "manual") -> None:
    _get_manager().refill(user_id, amount, source)


def reset_monthly(user_id: str) -> None:
    _get_manager().reset_monthly(user_id)


def initialize_user(user_id: str, tier: str = "free") -> None:
    _get_manager().initialize_user(user_id, tier)


def get_reset_at(user_id: str) -> Optional[str]:
    """Return the ISO datetime of the last monthly reset for a user."""
    user_data = _get_manager()._get_user_data(user_id)
    return user_data.get("reset_at")


def check_monthly_reset(user_id: str) -> bool:
    """Explicitly check and apply monthly reset if due. Returns True if reset was applied."""
    user_data = _get_manager()._get_user_data(user_id)
    old_reset = user_data.get("reset_at")
    updated = _get_manager()._check_monthly_reset(user_id, user_data)
    return updated.get("reset_at") != old_reset


def true_up_credits(
    user_id: str,
    feature: str,
    estimated_credits: int,
    actual_input_tokens: int,
    actual_output_tokens: int,
    model: str,
) -> int:
    """
    Adjust credit deduction based on actual token usage.
    Refunds difference if actual < estimate, charges more if actual > estimate.
    Returns the final actual credits charged.
    """
    actual_api_cost = calculate_api_cost(model, actual_input_tokens, actual_output_tokens)
    actual_credits = calculate_credits(actual_api_cost)
    diff = actual_credits - estimated_credits

    if diff < 0:
        # Refund the difference
        _get_manager().refill(user_id, abs(diff), f"{feature}_true_up_refund")
        print(f"[CreditSystem] {feature} true-up: refunded {abs(diff)} credits (estimated {estimated_credits}, actual {actual_credits})")
    elif diff > 0:
        # Charge additional credits
        if not _get_manager().deduct(user_id, feature, diff, model):
            print(f"[CreditSystem] {feature} true-up: could not charge additional {diff} credits")
        else:
            print(f"[CreditSystem] {feature} true-up: charged additional {diff} credits (estimated {estimated_credits}, actual {actual_credits})")
    else:
        print(f"[CreditSystem] {feature} true-up: no difference (actual = estimated = {actual_credits})")

    return actual_credits


# =============================================================
#  COST PREVIEW HELPERS (for UI)
# =============================================================

def preview_reprompt_cost(model_id: Optional[str] = None) -> Dict[str, Any]:
    """Return a cost preview dict for the UI."""
    registry = _get_registry()
    model = model_id or registry.get_default_model("reprompt")
    credits = calculate_reprompt_credits(model)
    price = registry.get_price(model)
    return {
        "feature": "reprompt",
        "model": model,
        "credits": credits,
        "model_category": price.category if price else "unknown",
        "model_speed": price.speed if price else "unknown",
    }


def preview_tunehub_cost(
    complexity: str,
    feature_model: Optional[str] = None,
    judge_model: Optional[str] = None,
) -> Dict[str, Any]:
    """Return a cost preview dict for the UI."""
    registry = _get_registry()
    f_model = feature_model or registry.get_default_model("reprompt")
    j_model = judge_model or registry.get_default_model("tunehub_judge")

    iterations = registry.get_tunehub_iterations(complexity)
    f_in, f_out = registry.get_token_estimate("reprompt")
    j_in, j_out = registry.get_token_estimate("judge")

    f_api = calculate_api_cost(f_model, f_in, f_out)
    f_credits = calculate_credits(f_api)
    j_api = calculate_api_cost(j_model, j_in, j_out)
    j_credits = calculate_credits(j_api)

    total = (f_credits + j_credits) * iterations

    return {
        "feature": "tunehub",
        "complexity": complexity,
        "iterations": iterations,
        "feature_model": f_model,
        "feature_credits_per_iter": f_credits,
        "judge_model": j_model,
        "judge_credits_per_iter": j_credits,
        "per_iteration": f_credits + j_credits,
        "total_credits": total,
    }


def preview_dictation_cost() -> Dict[str, Any]:
    return {"feature": "dictation", "credits": 1, "model": "whisper-large-v3-turbo"}


def get_current_user_id() -> str:
    """Return a stable user id for credit tracking."""
    try:
        from core.supabase_client import get_current_user
        user = get_current_user()
        if user and hasattr(user, "user") and user.user:
            return user.user.id
    except Exception:
        pass
    import hashlib
    user = os.environ.get("USER", os.environ.get("USERNAME", "local"))
    host = os.environ.get("HOSTNAME", "unknown")
    return hashlib.sha256(f"{user}@{host}".encode()).hexdigest()[:16]


def get_all_model_options() -> Dict[str, Any]:
    """Return all available models with their credit costs for UI dropdowns."""
    registry = _get_registry()
    models = registry.list_models()

    reprompt_options = []
    judge_options = []

    for model_id, price in models.items():
        reprompt_credits = calculate_reprompt_credits(model_id)
        judge_credits = calculate_judge_credits(model_id)

        reprompt_options.append({
            "id": model_id,
            "category": price.category,
            "speed": price.speed,
            "reprompt_credits": reprompt_credits,
            "input_price": price.input_per_million,
            "output_price": price.output_per_million,
        })

        judge_options.append({
            "id": model_id,
            "category": price.category,
            "speed": price.speed,
            "judge_credits": judge_credits,
            "input_price": price.input_per_million,
            "output_price": price.output_per_million,
        })

    # Sort by credit cost ascending
    reprompt_options.sort(key=lambda x: x["reprompt_credits"])
    judge_options.sort(key=lambda x: x["judge_credits"])

    return {
        "reprompt_models": reprompt_options,
        "judge_models": judge_options,
        "defaults": {
            "reprompt": registry.get_default_model("reprompt"),
            "judge": registry.get_default_model("tunehub_judge"),
        },
    }
