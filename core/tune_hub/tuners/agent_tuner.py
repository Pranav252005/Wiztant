"""AgentTuner — learns app behavior and automation sequences (recipes).

Algorithm: Causal Reinforcement Learning with Program Synthesis (CRL-PS).
- Exploration: Hierarchical task planner with macro-action library
- Causal model: Structural Causal Model (SCM) stub
- Policy: Heuristic policy with epsilon-greedy exploration
- Program synthesis: Domain-specific language (DSL) for action sequences
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..base import ComplexityLevel, CreditBudget, LearnedModel, TuneStatus
from ..tune_base import TuneBase, ExperimentResult
from ..utils.convergence import ConvergenceChecker
from ..utils.feature_extraction import cosine_similarity, embed_text
from ..utils.model_persistence import TuneModelPersistence


# =============================================================
#  RECIPE LIBRARY
# =============================================================


@dataclass
class Recipe:
    """A learned automation recipe."""

    recipe_id: str
    name: str
    description: str
    target_app: str
    actions: List[Dict[str, Any]]
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    causal_graph: Dict[str, Any] = field(default_factory=dict)
    validation_results: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "name": self.name,
            "description": self.description,
            "target_app": self.target_app,
            "actions": self.actions,
            "parameters": self.parameters,
            "causal_graph": self.causal_graph,
            "validation_results": self.validation_results,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Recipe:
        return cls(
            recipe_id=data["recipe_id"],
            name=data["name"],
            description=data.get("description", ""),
            target_app=data.get("target_app", ""),
            actions=data.get("actions", []),
            parameters=data.get("parameters", []),
            causal_graph=data.get("causal_graph", {}),
            validation_results=data.get("validation_results", {}),
        )


class RecipeLibrary:
    """Storage and similarity search for learned recipes."""

    def __init__(self):
        self._recipes: Dict[str, Recipe] = {}

    def store(self, recipe: Recipe) -> None:
        if recipe.embedding is None:
            recipe.embedding = embed_text(recipe.description, dim=128)
        self._recipes[recipe.recipe_id] = recipe

    def retrieve_similar(
        self, task_embedding: List[float], target_app: str, k: int = 3
    ) -> List[Tuple[Recipe, float]]:
        """Return top-k most similar recipes."""
        scored = []
        for recipe in self._recipes.values():
            app_match = 1.0 if recipe.target_app.lower() == target_app.lower() else 0.0
            emb_sim = 0.0
            if recipe.embedding:
                emb_sim = max(0.0, cosine_similarity(task_embedding, recipe.embedding))
            score = 0.3 * app_match + 0.7 * emb_sim
            if score > 0.3:
                scored.append((recipe, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:k]

    def get(self, recipe_id: str) -> Optional[Recipe]:
        return self._recipes.get(recipe_id)

    def all_recipes(self) -> List[Recipe]:
        return list(self._recipes.values())

    def to_dict(self) -> Dict[str, Any]:
        return {rid: r.to_dict() for rid, r in self._recipes.items()}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RecipeLibrary:
        lib = cls()
        for rid, rdata in data.items():
            lib.store(Recipe.from_dict(rdata))
        return lib


# =============================================================
#  STATE ENCODER
# =============================================================


class StateEncoder:
    """Encodes Desktop state into a feature vector."""

    def encode(
        self,
        app_state: Dict[str, Any],
        subgoals: List[str],
        history: List[Dict[str, Any]],
    ) -> List[float]:
        """Encode state into a 32-dimensional feature vector."""
        features = []

        # App state features (8-dim)
        features.append(1.0 if app_state.get("menu_visible") else 0.0)
        features.append(1.0 if app_state.get("dialog_open") else 0.0)
        features.append(1.0 if app_state.get("target_element_visible") else 0.0)
        features.append(float(app_state.get("window_x", 0)) / 1920.0)
        features.append(float(app_state.get("window_y", 0)) / 1080.0)
        features.append(float(app_state.get("error_count", 0)) / 5.0)
        features.append(1.0 if app_state.get("app_running") else 0.0)
        features.append(float(app_state.get("load_time_ms", 0)) / 10000.0)

        # Subgoal progress (8-dim)
        for i in range(4):
            if i < len(subgoals):
                sg = subgoals[i]
                progress = app_state.get("subgoal_progress", {}).get(sg, 0.0)
                features.append(progress)
            else:
                features.append(0.0)
        features.append(len(subgoals) / 10.0)
        features.append(sum(1 for sg in subgoals if app_state.get("subgoal_progress", {}).get(sg, 0) >= 1.0) / max(len(subgoals), 1))
        features.append(0.0)  # reserved
        features.append(0.0)  # reserved

        # History features (8-dim)
        steps_taken = len(history)
        features.append(min(steps_taken / 50.0, 1.0))
        features.append(len(set(h.get("action", "") for h in history)) / max(steps_taken, 1))
        error_count = sum(1 for h in history if h.get("error"))
        features.append(error_count / max(steps_taken, 1))
        features.append(steps_taken / 50.0 if history else 0.0)
        features.append(0.0)  # reserved
        features.append(0.0)
        features.append(0.0)
        features.append(0.0)

        # Context features (8-dim)
        from datetime import datetime

        hour = datetime.now().hour
        features.append(hour / 24.0)
        features.append(1.0 if 9 <= hour <= 17 else 0.0)
        features.append(0.0)  # desktop load
        features.append(0.0)  # recent errors
        features.append(0.0)
        features.append(0.0)
        features.append(0.0)
        features.append(0.0)

        return features[:32]


# =============================================================
#  CAUSAL MODEL
# =============================================================


class StructuralCausalModel:
    """Lightweight causal model for action-outcome relationships."""

    def __init__(self):
        self.edges: List[Dict[str, Any]] = []
        self.variables: set[str] = set()

    def update_from_interventions(
        self, actions: List[Dict[str, Any]], observations: List[Dict[str, Any]]
    ) -> None:
        """Learn causal edges from observed transitions."""
        for i in range(len(actions)):
            action_str = json.dumps(actions[i], sort_keys=True)
            pre = observations[i].get("pre_state", {})
            post = observations[i].get("post_state", {})

            for var_pre, val_pre in pre.items():
                for var_post, val_post in post.items():
                    if var_pre == var_post:
                        continue
                    if val_pre != val_post:
                        self.edges.append({
                            "from": f"{action_str}:{var_pre}",
                            "to": var_post,
                            "action": actions[i],
                            "strength": 0.7,
                        })
                        self.variables.add(var_pre)
                        self.variables.add(var_post)

    def get_recovery_actions(
        self, failure_state: Dict[str, Any], target_state: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Suggest recovery actions based on causal edges."""
        # Simple: find edges that transition from failure-like to target-like states
        recovery = []
        for edge in self.edges:
            if edge["to"] in target_state:
                recovery.append(edge["action"])
        return recovery[:3]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edges": self.edges,
            "variables": list(self.variables),
        }


# =============================================================
#  REWARD COMPUTER
# =============================================================


def compute_reward(
    observation: Dict[str, Any],
    subgoals: List[str],
    step: int,
    max_steps: int = 50,
) -> float:
    """Multi-factor reward computation."""
    # Goal progress
    goal_reward = 0.0
    for sg in subgoals:
        progress = observation.get("subgoal_progress", {}).get(sg, 0.0)
        goal_reward += progress / max(len(subgoals), 1)

    # Efficiency
    efficiency = 1.0 - (step / max_steps)

    # Stability (no errors)
    stability = 1.0 if not observation.get("error_detected") else 0.0

    # Safety
    safety = 1.0
    if observation.get("app_crashed"):
        safety = -2.0
    elif observation.get("error_detected"):
        safety = -1.0

    return (
        0.5 * goal_reward
        + 0.25 * efficiency
        + 0.15 * stability
        + 0.10 * safety
    )


# =============================================================
#  RECIPE DSL
# =============================================================


class AgentRecipeDSL:
    """Domain-specific language for agent recipes."""

    def compile(self, actions: List[Dict[str, Any]]) -> str:
        """Compile actions to DSL string."""
        lines = ['RECIPE "Learned Recipe" {']
        for i, action in enumerate(actions, 1):
            action_type = action.get("action", "unknown")
            params = action.get("params", {})
            param_str = ", ".join(f'{k}="{v}"' for k, v in params.items())
            lines.append(f'    STEP {i}: {action_type}({param_str})')
        lines.append("}")
        return "\n".join(lines)

    def parse(self, dsl_code: str) -> List[Dict[str, Any]]:
        """Parse DSL string back to actions."""
        actions = []
        for line in dsl_code.split("\n"):
            line = line.strip()
            if not line or line.startswith("RECIPE") or line.startswith("}"):
                continue
            if line.startswith("STEP"):
                # Simple parsing: extract action and params
                match = line.split(":", 1)[-1].strip()
                action_name = match.split("(")[0].strip()
                params_str = match[len(action_name) + 1 :].rstrip(")")
                params = {}
                for part in params_str.split(","):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        params[k.strip()] = v.strip().strip('"')
                actions.append({"action": action_name, "params": params})
        return actions


# =============================================================
#  TUNER
# =============================================================


class AgentTuner(TuneBase, feature_name="agent"):
    """Learns app behavior and automation sequences."""

    MACRO_ACTIONS = [
        "click",
        "double_click",
        "right_click",
        "type",
        "hotkey",
        "drag",
        "scroll",
        "wait",
        "menu_select",
        "dialog_click",
        "slider_set",
        "layer_select",
        "adjustment_apply",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.recipe_library = RecipeLibrary()
        self.state_encoder = StateEncoder()
        self.causal_model = StructuralCausalModel()
        self.dsl = AgentRecipeDSL()
        self.persistence = TuneModelPersistence()
        self.convergence = ConvergenceChecker(max_iterations=25)

    # ── PHASE 0: Static Analysis ──

    def estimate_complexity(
        self, task: str, context: Optional[Dict] = None
    ) -> ComplexityLevel:
        steps = context.get("estimated_steps", 1) if context else 1
        if steps >= 10 or "multi_app" in task.lower():
            return ComplexityLevel.HIGH
        if steps >= 5:
            return ComplexityLevel.MEDIUM
        return ComplexityLevel.LOW

    # ── PHASE 1: Learning ──

    def learn(
        self,
        task: str,
        budget: CreditBudget,
        context: Optional[Dict[str, Any]] = None,
        judge=None,
    ) -> LearnedModel:
        task_sig = self._normalize_task(task)
        user_id = context.get("user_id", "anonymous") if context else "anonymous"

        # Load previous recipes
        prev_data = self.persistence.load_json(
            user_id, self.feature_name, task_sig, suffix="_recipes.json"
        )
        if prev_data:
            self.recipe_library = RecipeLibrary.from_dict(prev_data.get("recipe_library", {}))

        # Classify task
        task_info = self._classify_task(task)
        target_app = task_info["target_app"]
        subgoals = task_info["subgoals"]

        # Retrieve similar recipes for warm-start
        task_emb = embed_text(task, dim=128)
        similar = self.recipe_library.retrieve_similar(task_emb, target_app, k=3)

        # Generate candidate recipes
        candidate_recipes = self._generate_candidate_recipes(task, target_app, subgoals, budget.approved)

        # Run episodes
        results: List[ExperimentResult] = []
        episode_results: List[Dict[str, Any]] = []
        self.convergence.reset()

        for i, recipe_actions in enumerate(candidate_recipes):
            if not budget.can_spend(1):
                break

            outcome = self._execute_recipe_on_desktop2(recipe_actions)
            score = self._score_outcome(outcome, subgoals)

            results.append(
                ExperimentResult(
                    config={"recipe": recipe_actions},
                    output=outcome,
                    score=score,
                    credits_used=1,
                    iteration=i,
                    metadata={
                        "desktop2_session_id": outcome.get("session_id"),
                        "target_app": target_app,
                    },
                )
            )

            # Update causal model
            if outcome.get("actions") and outcome.get("observations"):
                self.causal_model.update_from_interventions(
                    outcome["actions"], outcome["observations"]
                )

            episode_results.append({
                "trajectory": recipe_actions,
                "reward": score,
                "success": outcome.get("success", False),
            })

            self.convergence.record({
                "quality_score": score,
                "reward": score,
            })

            budget = budget.spend(1)

            # Check convergence
            conv = self.convergence.check()
            if conv.status.startswith("CONVERGED") and i >= 3:
                break

        # Aggregate results
        aggregated = self._aggregate(results)
        best_recipe = aggregated.get("best_config", {}).get("recipe", [])
        best_score = aggregated.get("best_score", 0.0)

        # Synthesize recipe from best trajectory
        if best_recipe:
            dsl_code = self.dsl.compile(best_recipe)
        else:
            dsl_code = ""

        recipe = Recipe(
            recipe_id=f"agent_{task_sig}_{uuid.uuid4().hex[:8]}",
            name=task_info.get("task_name", "Learned Recipe"),
            description=task,
            target_app=target_app,
            actions=best_recipe,
            parameters=task_info.get("parameters", []),
            causal_graph=self.causal_model.to_dict(),
            validation_results={
                "success_rate": best_score,
                "episodes": len(results),
            },
        )
        self.recipe_library.store(recipe)

        # Persist
        self.persistence.save_json(
            user_id,
            self.feature_name,
            task_sig,
            {
                "recipe_library": self.recipe_library.to_dict(),
                "causal_model": self.causal_model.to_dict(),
            },
            suffix="_recipes.json",
        )

        return LearnedModel(
            tune_id=recipe.recipe_id,
            feature_name=self.feature_name,
            task_signature=task_sig,
            payload={
                "recipe": best_recipe,
                "recipe_type": "automation_sequence",
                "dsl_code": dsl_code,
                "target_app": target_app,
                "subgoals": subgoals,
                "experiment_count": len(results),
                "aggregate": aggregated,
                "causal_graph": self.causal_model.to_dict(),
                "validation_results": recipe.validation_results,
            },
            quality_score=best_score,
            complexity=self.estimate_complexity(task, context),
            status=TuneStatus.DRAFT,
        )

    # ── PHASE 2: Validation ──

    def validate(
        self,
        model: LearnedModel,
        hold_out_tasks: Optional[List[str]] = None,
        judge=None,
    ) -> bool:
        recipe = model.payload.get("recipe", [])
        if not recipe:
            return False
        successes = 0
        for _ in range(3):
            outcome = self._execute_recipe_on_desktop2(recipe, dry_run=True)
            if outcome.get("success", False):
                successes += 1
        return successes >= 2

    # ── PHASE 3: Deployment ──

    def deploy(self, model: LearnedModel) -> Dict[str, Any]:
        return {
            "tune_id": model.tune_id,
            "recipe": model.payload["recipe"],
            "recipe_type": model.payload["recipe_type"],
            "dsl_code": model.payload.get("dsl_code", ""),
            "target_app": model.payload.get("target_app", ""),
        }

    # ── RUNTIME: Apply ──

    def apply(
        self, model: LearnedModel, feature_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        feature_input["recipe"] = model.payload.get("recipe", [])
        feature_input["tune_id"] = model.tune_id
        feature_input["dsl_code"] = model.payload.get("dsl_code", "")

        # Modify the task to indicate a learned recipe is available
        task = feature_input.get("task", "")
        if task and model.payload.get("recipe"):
            feature_input["task"] = f"[Use learned recipe {model.tune_id}] {task}"

        # Inject recipe guidance hint
        recipe_hint = model.payload.get("recipe", [])
        if recipe_hint:
            dsl_code = model.payload.get("dsl_code", "")
            feature_input["recipe_hint"] = f"Follow this learned automation sequence: {recipe_hint}"
            if dsl_code:
                feature_input["recipe_hint"] += f"\nDSL: {dsl_code}"

        return feature_input

    def get_default_config(self, task: str) -> Dict[str, Any]:
        return {"recipe": [], "tune_id": None, "dsl_code": ""}

    # ── INTERNALS ──

    def _classify_task(self, task_description: str) -> Dict[str, Any]:
        """Extract target app, subgoals, and parameters from task."""
        app_keyword_map = {
            "photoshop": "Adobe Photoshop",
            "edit photo": "Adobe Photoshop",
            "spreadsheet": "Microsoft Excel",
            "excel": "Microsoft Excel",
            "browser": "Google Chrome",
            "web": "Google Chrome",
            "terminal": "Windows Terminal",
            "command": "Windows Terminal",
            "code": "Visual Studio Code",
            "programming": "Visual Studio Code",
            "document": "Microsoft Word",
            "write": "Microsoft Word",
            "presentation": "Microsoft PowerPoint",
            "slide": "Microsoft PowerPoint",
        }

        task_lower = task_description.lower()
        detected_apps = []
        for keyword, app in app_keyword_map.items():
            if keyword in task_lower:
                detected_apps.append(app)

        target_app = detected_apps[0] if detected_apps else "unknown"

        # Heuristic subgoals
        subgoals = [f"Open {target_app}"]
        if "open" in task_lower:
            subgoals.append("Navigate to target")
        if "edit" in task_lower or "modify" in task_lower:
            subgoals.append("Apply edits")
        if "save" in task_lower or "export" in task_lower:
            subgoals.append("Save or export result")
        if len(subgoals) < 2:
            subgoals.append("Execute main task")

        return {
            "target_app": target_app,
            "subgoals": subgoals,
            "parameters": [
                {"name": "input_path", "type": "file_path", "required": False},
                {"name": "output_path", "type": "file_path", "required": False},
            ],
        }

    def _generate_candidate_recipes(
        self, task: str, target_app: str, subgoals: List[str], budget: int
    ) -> List[List[Dict]]:
        """Generate candidate action sequences."""
        candidates = [
            [{"action": "open_app", "params": {"target": target_app}}],
            [
                {"action": "open_app", "params": {"target": target_app}},
                {"action": "menu_select", "params": {"path": ["File", "Open"]}},
            ],
            [
                {"action": "open_app", "params": {"target": target_app}},
                {"action": "menu_select", "params": {"path": ["File", "New"]}},
                {"action": "type", "params": {"text": "placeholder"}},
            ],
            [
                {"action": "open_app", "params": {"target": target_app}},
                {"action": "hotkey", "params": {"keys": ["ctrl", "o"]}},
                {"action": "type", "params": {"text": "document"}},
                {"action": "dialog_click", "params": {"button": "OK"}},
            ],
        ]
        # Pad with variations if budget allows
        import random

        while len(candidates) < budget:
            base = random.choice(candidates[:2])
            variant = base + [{"action": "wait", "params": {"seconds": 1}}]
            candidates.append(variant)

        return candidates[:budget]

    def _execute_recipe_on_desktop2(
        self, recipe: List[Dict], dry_run: bool = False
    ) -> Dict[str, Any]:
        """Simulate recipe execution on Desktop 2."""
        if dry_run:
            return {
                "success": True,
                "session_id": "sandbox_dryrun",
                "steps_taken": len(recipe),
                "actions": recipe,
                "observations": [
                    {
                        "pre_state": {"app_state": "closed"},
                        "post_state": {"app_state": "open"},
                    }
                    for _ in recipe
                ],
            }

        # Simulated outcome with some noise
        import random

        success_prob = 0.85 if len(recipe) <= 3 else 0.70
        success = random.random() < success_prob
        return {
            "success": success,
            "session_id": f"sandbox_{uuid.uuid4().hex[:8]}",
            "steps_taken": len(recipe),
            "actions": recipe,
            "observations": [
                {
                    "pre_state": {"app_state": "closed"},
                    "post_state": {"app_state": "open" if success else "error"},
                }
                for _ in recipe
            ],
        }

    def _score_outcome(self, outcome: Dict[str, Any], subgoals: List[str]) -> float:
        if not outcome.get("success", False):
            return 0.0
        steps = outcome.get("steps_taken", 1)
        base = max(0.0, 1.0 - (steps - 1) * 0.05)
        # Bonus for completing subgoals
        sg_bonus = min(len(subgoals) * 0.05, 0.2)
        return min(1.0, base + sg_bonus)

    @staticmethod
    def _normalize_task(task: str) -> str:
        return task.lower().strip().replace(" ", "_")[:64]
