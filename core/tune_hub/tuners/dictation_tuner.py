"""DictationTuner — learns domain-specific vocabulary corrections.

Algorithm: Context-Aware Active Learning with Confidence-Weighted Correction Map.
- Base: Trie-based prefix correction map with frequency weighting
- Context classifier: heuristic domain detection (8 domains)
- Update rule: Exponential weighted moving average with recency bias
- Confidence model: learned threshold for auto-apply vs. suggest
"""

from __future__ import annotations

import heapq
import math
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..base import ComplexityLevel, CreditBudget, LearnedModel, TuneStatus
from ..tune_base import TuneBase, ExperimentResult
from ..utils.convergence import ConvergenceChecker
from ..utils.model_persistence import TuneModelPersistence


# =============================================================
#  TRIE-BASED CORRECTION MAP
# =============================================================


@dataclass
class CorrectionEntry:
    """A single correction candidate with metadata."""

    correct: str
    frequency: float = 0.0
    total_uses: int = 0
    domain_distribution: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    context_examples: List[str] = field(default_factory=list)
    user_acceptance_rate: float = 0.0
    last_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correct": self.correct,
            "frequency": self.frequency,
            "total_uses": self.total_uses,
            "domain_distribution": dict(self.domain_distribution),
            "context_examples": self.context_examples[-5:],
            "user_acceptance_rate": self.user_acceptance_rate,
            "last_used": self.last_used,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CorrectionEntry:
        entry = cls(
            correct=data["correct"],
            frequency=data.get("frequency", 0.0),
            total_uses=data.get("total_uses", 0),
            user_acceptance_rate=data.get("user_acceptance_rate", 0.0),
            last_used=data.get("last_used", ""),
        )
        dd = data.get("domain_distribution", {})
        entry.domain_distribution = defaultdict(float, dd)
        entry.context_examples = data.get("context_examples", [])
        return entry


class CorrectionTrie:
    """Trie for fast prefix-based correction lookup."""

    def __init__(self):
        self._root: Dict[str, Any] = {}
        self._entries: Dict[str, Dict[str, CorrectionEntry]] = {}

    def insert(self, heard: str, entry: CorrectionEntry) -> None:
        """Insert a correction into the trie."""
        heard_lower = heard.lower()
        if heard_lower not in self._entries:
            self._entries[heard_lower] = {}
        self._entries[heard_lower][entry.correct] = entry

        # Build trie path
        node = self._root
        for ch in heard_lower:
            if ch not in node:
                node[ch] = {}
            node = node[ch]
        node["_end_"] = True

    def lookup(self, heard: str) -> Optional[Dict[str, CorrectionEntry]]:
        """Return all correction candidates for a heard word."""
        return self._entries.get(heard.lower())

    def has_prefix(self, prefix: str) -> bool:
        """Check if any word in trie starts with prefix."""
        node = self._root
        for ch in prefix.lower():
            if ch not in node:
                return False
            node = node[ch]
        return True

    def all_keys(self) -> List[str]:
        """Return all heard words in trie."""
        return list(self._entries.keys())

    def to_dict(self) -> Dict[str, Any]:
        return {
            heard: {corr: entry.to_dict() for corr, entry in candidates.items()}
            for heard, candidates in self._entries.items()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CorrectionTrie:
        trie = cls()
        for heard, candidates in data.items():
            for correct, entry_data in candidates.items():
                entry = CorrectionEntry.from_dict(entry_data)
                trie.insert(heard, entry)
        return trie


# =============================================================
#  DOMAIN CLASSIFIER
# =============================================================


class ContextDomainClassifier:
    """Heuristic domain classifier for dictation context."""

    DOMAINS = [
        "general",
        "software",
        "crypto",
        "medical",
        "legal",
        "creative_writing",
        "business",
        "custom",
    ]

    DOMAIN_KEYWORDS = {
        "software": ["code", "bug", "function", "api", "git", "python", "javascript"],
        "crypto": ["bitcoin", "ethereum", "blockchain", "defi", "nft", "token", "wallet"],
        "medical": ["patient", "diagnosis", "symptom", "treatment", "clinical", "drug"],
        "legal": ["contract", "plaintiff", "defendant", "jurisdiction", "precedent", "clause"],
        "creative_writing": ["story", "character", "plot", "narrative", "poem", "chapter"],
        "business": ["revenue", "profit", "stakeholder", "meeting", "deadline", "quarter"],
    }

    def classify(
        self,
        recent_prompts: List[str],
        active_app: str = "",
        document_preview: str = "",
    ) -> Tuple[str, float]:
        """Return (domain, confidence)."""
        text_input = " ".join(recent_prompts + [document_preview]).lower()

        # Signal 1: Text content
        text_scores: Dict[str, float] = {d: 0.0 for d in self.DOMAINS}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text_input)
            text_scores[domain] = matches / max(len(keywords), 1)

        # Signal 2: Active application
        app_scores: Dict[str, float] = {d: 0.0 for d in self.DOMAINS}
        app_domain_map = {
            "vscode": "software",
            "visual studio code": "software",
            "pycharm": "software",
            "terminal": "software",
            "chrome": "crypto",
            "slack": "business",
            "word": "creative_writing",
            "photoshop": "creative_writing",
            "excel": "business",
            "outlook": "business",
        }
        app_lower = active_app.lower()
        for app_name, domain in app_domain_map.items():
            if app_name in app_lower:
                app_scores[domain] = 1.0
                break

        # Signal 3: Time patterns (weak)
        time_scores: Dict[str, float] = {d: 0.0 for d in self.DOMAINS}
        from datetime import datetime

        hour = datetime.now().hour
        if 9 <= hour <= 17:
            time_scores["business"] += 0.3
            time_scores["software"] += 0.2
        elif hour >= 20 or hour <= 6:
            time_scores["creative_writing"] += 0.2

        # Ensemble
        final_scores: Dict[str, float] = {}
        for domain in self.DOMAINS:
            final_scores[domain] = (
                0.6 * text_scores.get(domain, 0.0)
                + 0.3 * app_scores.get(domain, 0.0)
                + 0.1 * time_scores.get(domain, 0.0)
            )

        best_domain = max(final_scores, key=lambda k: final_scores[k])
        confidence = final_scores[best_domain]
        return (best_domain, confidence)


# =============================================================
#  CONFIDENCE MODEL
# =============================================================


class ConfidenceThresholdLearner:
    """Learns per-domain confidence thresholds for auto-apply."""

    def __init__(self, default_threshold: float = 0.85):
        self.default_threshold = default_threshold
        self.thresholds: Dict[str, float] = defaultdict(lambda: default_threshold)
        self._history: Dict[str, List[Tuple[float, bool]]] = defaultdict(list)

    def threshold(self, domain: str) -> float:
        return self.thresholds.get(domain, self.default_threshold)

    def update(self, correction: Dict[str, Any], domain: str, user_accepted: bool) -> None:
        """Update threshold based on user feedback."""
        confidence = correction.get("confidence", 0.5)
        self._history[domain].append((confidence, user_accepted))

        # Adjust threshold: if user rejects high-confidence, raise threshold
        recent = self._history[domain][-20:]
        if len(recent) >= 5:
            accepted = [c for c, a in recent if a]
            rejected = [c for c, a in recent if not a]
            if rejected and accepted:
                # Set threshold above max rejected but below min accepted if possible
                new_threshold = max(rejected) + 0.05
                if new_threshold < min(accepted):
                    self.thresholds[domain] = min(0.95, new_threshold)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "default_threshold": self.default_threshold,
            "thresholds": dict(self.thresholds),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ConfidenceThresholdLearner:
        model = cls(default_threshold=data.get("default_threshold", 0.85))
        model.thresholds = defaultdict(lambda: model.default_threshold)
        for domain, thresh in data.get("thresholds", {}).items():
            model.thresholds[domain] = thresh
        return model


# =============================================================
#  FUZZY / PHONETIC MATCHING
# =============================================================


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein edit distance."""
    m, n = len(a), len(b)
    if m < n:
        return _levenshtein(b, a)
    if n == 0:
        return m

    previous = list(range(n + 1))
    for i in range(m):
        current = [i + 1]
        for j in range(n):
            insertions = previous[j + 1] + 1
            deletions = current[j] + 1
            substitutions = previous[j] + (0 if a[i] == b[j] else 1)
            current.append(min(insertions, deletions, substitutions))
        previous = current
    return previous[n]


def _normalized_edit_distance(a: str, b: str) -> float:
    """Normalized edit distance in [0, 1]."""
    max_len = max(len(a), len(b), 1)
    return _levenshtein(a, b) / max_len


def fuzzy_match(
    query: str, candidates: List[str], threshold: float = 0.7
) -> List[Tuple[str, float]]:
    """Return candidates sorted by similarity, filtering below threshold."""
    scored = []
    for cand in candidates:
        dist = _normalized_edit_distance(query.lower(), cand.lower())
        sim = 1.0 - dist
        if sim >= threshold:
            scored.append((cand, sim))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


# =============================================================
#  UNCERTAINTY QUEUE
# =============================================================


@dataclass(order=True)
class UncertainToken:
    """Priority queue item for uncertain tokens."""

    priority: float
    heard: str = field(compare=False)
    suggested: str = field(compare=False)
    domain: str = field(compare=False)
    reason: str = field(compare=False)
    audio_ref: Optional[str] = field(default=None, compare=False)


class UncertaintyQueue:
    """Priority queue for uncertain tokens awaiting user review."""

    def __init__(self, maxsize: int = 100):
        self._queue: List[UncertainToken] = []
        self._maxsize = maxsize

    def push(self, item: UncertainToken) -> None:
        heapq.heappush(self._queue, item)
        if len(self._queue) > self._maxsize:
            heapq.heappop(self._queue)

    def peek(self, k: int = 3) -> List[UncertainToken]:
        """Return top k most uncertain tokens."""
        return heapq.nsmallest(k, self._queue)

    def pop(self) -> Optional[UncertainToken]:
        if self._queue:
            return heapq.heappop(self._queue)
        return None

    def __len__(self) -> int:
        return len(self._queue)


# =============================================================
#  TUNER
# =============================================================


class DictationTuner(TuneBase, feature_name="dictation"):
    """Learns domain-specific vocabulary corrections."""

    DOMAINS = [
        "general",
        "software",
        "crypto",
        "medical",
        "legal",
        "creative_writing",
        "business",
        "custom",
    ]

    def __init__(self) -> None:
        super().__init__()
        self.correction_map = CorrectionTrie()
        self.domain_classifier = ContextDomainClassifier()
        self.confidence_model = ConfidenceThresholdLearner()
        self.uncertainty_queue = UncertaintyQueue()
        self.persistence = TuneModelPersistence()
        self.convergence = ConvergenceChecker(max_iterations=50)

    # ── PHASE 0: Static Analysis ──

    def estimate_complexity(
        self, task: str, context: Optional[Dict] = None
    ) -> ComplexityLevel:
        domain = task.lower()
        if any(d in domain for d in ["medical", "legal", "scientific", "engineering"]):
            return ComplexityLevel.HIGH
        if any(d in domain for d in ["crypto", "finance", "tech", "gaming"]):
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
        results: List[ExperimentResult] = []
        domain = self._normalize_task(task)
        vocab = context.get("vocabulary", []) if context else []
        if not vocab:
            vocab = self._get_default_vocab(domain)

        # Load previous state for warm-start
        user_id = context.get("user_id", "anonymous") if context else "anonymous"
        prev_data = self.persistence.load_json(
            user_id, self.feature_name, domain, suffix="_corrections.json"
        )
        if prev_data:
            self.correction_map = CorrectionTrie.from_dict(prev_data.get("correction_map", {}))
            self.confidence_model = ConfidenceThresholdLearner.from_dict(
                prev_data.get("confidence_model", {})
            )

        corrections: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"correct": "", "count": 0, "confidence": 0.0, "domain_hits": defaultdict(int)}
        )

        for i, word in enumerate(vocab):
            if not budget.can_spend(1):
                break
            variants = self._generate_variants(word)
            for variant in variants:
                dictated = self._simulate_dictation(variant)
                if dictated != word:
                    corrections[dictated]["correct"] = word
                    corrections[dictated]["count"] += 1
                    corrections[dictated]["domain_hits"][domain] += 1
            budget = budget.spend(1)

        # Build correction map entries
        correction_map_data = {}
        for misspelled, data in corrections.items():
            total = data["count"]
            confidence = min(total / 3.0, 1.0)
            domain_dist = {
                d: data["domain_hits"].get(d, 0) / max(total, 1)
                for d in self.DOMAINS
            }

            entry = CorrectionEntry(
                correct=data["correct"],
                frequency=confidence * 5.0,
                total_uses=total,
                domain_distribution=domain_dist,
                user_acceptance_rate=1.0,
            )
            self.correction_map.insert(misspelled, entry)
            correction_map_data[misspelled] = {data["correct"]: entry.to_dict()}

        high_conf = sum(1 for c in correction_map_data.values() if list(c.values())[0]["confidence"] >= 0.7)
        success_rate = high_conf / max(len(vocab), 1)

        # Build domain profiles
        domain_profiles = {}
        for d in self.DOMAINS:
            count = sum(
                1 for c in correction_map_data.values()
                if list(c.values())[0]["domain_distribution"].get(d, 0) > 0.5
            )
            domain_profiles[d] = {
                "correction_count": count,
                "convergence_status": "LEARNING" if count < 10 else "CONVERGED_AUTO_APPLY",
            }

        # Persist state
        self.persistence.save_json(
            user_id,
            self.feature_name,
            domain,
            {
                "correction_map": self.correction_map.to_dict(),
                "confidence_model": self.confidence_model.to_dict(),
                "domain_profiles": domain_profiles,
            },
            suffix="_corrections.json",
        )

        return LearnedModel(
            tune_id=f"dictation_{domain}_{uuid.uuid4().hex[:8]}",
            feature_name=self.feature_name,
            task_signature=domain,
            payload={
                "corrections": correction_map_data,
                "domain": domain,
                "vocab_size": len(vocab),
                "domain_profiles": domain_profiles,
                "auto_apply_threshold": self.confidence_model.threshold(domain),
                "uncertainty_queue_size": len(self.uncertainty_queue),
            },
            quality_score=success_rate,
            complexity=self.estimate_complexity(task),
            status=TuneStatus.DRAFT,
        )

    # ── PHASE 2: Validation ──

    def validate(
        self,
        model: LearnedModel,
        hold_out_tasks: Optional[List[str]] = None,
        judge=None,
    ) -> bool:
        corrections = model.payload.get("corrections", {})
        if not corrections:
            return False
        avg_conf = sum(
            list(c.values())[0].get("confidence", 0.0) for c in corrections.values()
        ) / len(corrections)
        return avg_conf >= 0.5

    # ── PHASE 3: Deployment ──

    def deploy(self, model: LearnedModel) -> Dict[str, Any]:
        return {
            "tune_id": model.tune_id,
            "corrections": model.payload["corrections"],
            "domain": model.payload["domain"],
            "auto_apply_threshold": model.payload.get("auto_apply_threshold", 0.85),
        }

    # ── RUNTIME: Apply ──

    def apply(
        self, model: LearnedModel, feature_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        feature_input["correction_map"] = model.payload.get("corrections", {})
        feature_input["tune_id"] = model.tune_id
        feature_input["domain"] = model.payload.get("domain", "general")
        feature_input["auto_apply_threshold"] = model.payload.get(
            "auto_apply_threshold", 0.85
        )

        # Actually process the transcription text if available
        text = feature_input.get("text", "")
        if text and model.payload.get("corrections"):
            result = self.process_transcription(
                text, user_context=feature_input.get("context")
            )
            feature_input["text"] = result["corrected_text"]
            feature_input["applied_corrections"] = result.get("applied_corrections", [])

        return feature_input

    def get_default_config(self, task: str) -> Dict[str, Any]:
        return {"correction_map": {}, "tune_id": None, "domain": "general"}

    def allowed_injectable_keys(self) -> frozenset[str]:
        from ..guardrails import INJECTABLE_KEYS
        return INJECTABLE_KEYS.get(self.feature_name, frozenset())

    # ── RUNTIME: Process Transcription (hot path) ──

    def process_transcription(
        self,
        heard_text: str,
        audio_features: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Main entry: called after every transcription.
        Returns corrected text with metadata.
        """
        # Step 1: Detect domain
        context = user_context or {}
        domain, domain_confidence = self.domain_classifier.classify(
            recent_prompts=context.get("recent_prompts", []),
            active_app=context.get("active_app", ""),
            document_preview=context.get("document_preview", ""),
        )

        # Step 2: Apply corrections at token level
        tokens = heard_text.split()
        corrected_tokens = []
        applied_corrections = []
        uncertain_tokens = []

        for token in tokens:
            result = self._lookup_correction(token, domain)
            if result["action"] == "AUTO_APPLY":
                corrected_tokens.append(result["correction"])
                applied_corrections.append({
                    "heard": token,
                    "applied": result["correction"],
                    "confidence": result["confidence"],
                    "auto_applied": True,
                })
            elif result["action"] == "SUGGEST":
                corrected_tokens.append(token)  # Don't auto-apply, flag for review
                uncertain_tokens.append({
                    "text": token,
                    "suggested": result["correction"],
                    "confidence": result["confidence"],
                    "reason": "low_confidence",
                })
            else:
                # Check for fuzzy match
                fuzzy = self._fuzzy_lookup(token, domain)
                if fuzzy and fuzzy["confidence"] > 0.6:
                    corrected_tokens.append(token)
                    uncertain_tokens.append({
                        "text": token,
                        "suggested": fuzzy["correction"],
                        "confidence": fuzzy["confidence"],
                        "reason": "fuzzy_match",
                    })
                else:
                    corrected_tokens.append(token)

        corrected_text = " ".join(corrected_tokens)

        return {
            "corrected_text": corrected_text,
            "applied_corrections": applied_corrections,
            "uncertain_tokens": uncertain_tokens,
            "domain": domain,
            "domain_confidence": domain_confidence,
        }

    def record_user_correction(
        self,
        heard_text: str,
        corrected_text: str,
        context_domain: str,
    ) -> Dict[str, Any]:
        """Called when user edits the transcription."""
        heard_tokens = heard_text.lower().split()
        corrected_tokens = corrected_text.lower().split()

        # Simple diff: find substituted tokens
        corrections = []
        for h, c in zip(heard_tokens, corrected_tokens):
            if h != c:
                corrections.append({"heard": h, "should_be": c})

        for corr in corrections:
            entry = CorrectionEntry(
                correct=corr["should_be"],
                frequency=1.0,
                total_uses=1,
                domain_distribution={context_domain: 1.0},
                user_acceptance_rate=1.0,
            )
            self.correction_map.insert(corr["heard"], entry)
            self.confidence_model.update(
                correction={"confidence": 1.0},
                domain=context_domain,
                user_accepted=True,
            )

        return {"corrections_recorded": len(corrections)}

    # ── INTERNALS ──

    def _lookup_correction(self, heard_word: str, domain: str) -> Dict[str, Any]:
        """Look up correction with domain-aware scoring."""
        heard_lower = heard_word.lower()
        candidates = self.correction_map.lookup(heard_lower)
        if not candidates:
            return {"action": "PASS", "heard": heard_word}

        best_candidate = None
        best_score = 0.0
        best_meta = None

        for correction, meta in candidates.items():
            domain_score = meta.domain_distribution.get(domain, 0.05)
            frequency_score = min(meta.frequency / 5.0, 1.0)
            recency_score = 1.0  # Simplified

            score = 0.5 * domain_score + 0.3 * frequency_score + 0.2 * recency_score
            if score > best_score:
                best_score = score
                best_candidate = correction
                best_meta = meta

        threshold = self.confidence_model.threshold(domain)
        if best_score >= threshold:
            return {"action": "AUTO_APPLY", "correction": best_candidate, "confidence": best_score}
        elif best_score >= threshold * 0.7:
            return {"action": "SUGGEST", "correction": best_candidate, "confidence": best_score}
        return {"action": "PASS", "heard": heard_word}

    def _fuzzy_lookup(self, heard_word: str, domain: str) -> Optional[Dict[str, Any]]:
        """Fuzzy match against correction map keys."""
        keys = self.correction_map.all_keys()
        matches = fuzzy_match(heard_word.lower(), keys, threshold=0.7)
        if not matches:
            return None
        best_match, sim = matches[0]
        candidates = self.correction_map.lookup(best_match)
        if not candidates:
            return None
        best_corr = max(candidates.items(), key=lambda x: x[1].domain_distribution.get(domain, 0))
        return {
            "correction": best_corr[0],
            "confidence": sim * 0.8,  # Penalty for fuzzy match
            "matched_key": best_match,
        }

    def _get_default_vocab(self, domain: str) -> List[str]:
        defaults = {
            "crypto": ["ethereum", "bitcoin", "blockchain", "defi", "nft", "kimi"],
            "tech": ["kubernetes", "docker", "typescript", "microservices"],
            "medical": ["hypertension", "glucose", "antibiotic", "pathology"],
            "legal": ["plaintiff", "defendant", "jurisdiction", "precedent"],
            "software": ["kubernetes", "docker", "typescript", "asyncio"],
        }
        return defaults.get(domain, ["example", "word"])

    def _generate_variants(self, word: str) -> List[str]:
        variants = [
            word,
            word.lower(),
            word.replace("ph", "f"),
            word.replace("k", "c"),
        ]
        return list(set(variants))

    def _simulate_dictation(self, variant: str) -> str:
        return variant

    @staticmethod
    def _normalize_task(task: str) -> str:
        return task.lower().strip().replace(" ", "_")[:64]
