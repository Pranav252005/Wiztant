"""
core/stt_refiner.py — AI refinement for STT output

Groq-powered surgical refinement. The model never returns rewritten text —
it returns a list of single-word replacements which we validate and apply
ourselves, so nothing outside the flagged words can change.
"""

import json
import logging
import os
import re
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEFAULT_MODEL = os.getenv("WIZTANT_REFINER_MODEL", "llama-3.3-70b-versatile")

# A proposed replacement not targeting a known dictionary/vocab word must be
# at least this similar to the original (homophone/typo territory).
_MIN_FREE_SIMILARITY = 0.6


class STTRefiner:
    """
    AI-powered refinement engine using Groq Mixtral.

    Fixes STT errors:
    - Homophones (their/there)
    - Run-on words (manytasks -> many tasks)
    - Missing punctuation
    - Common typos specific to audio

    Preserves user intent (no hallucination).
    """

    def __init__(self, model: str = DEFAULT_MODEL):
        self._groq_client = None
        self.vocab_db: Dict[str, str] = {}
        self.dictionary_words: List[str] = []
        self.context_history: List[str] = []
        self.model = model
        self.stats = {
            "total_refinements": 0,
            "changes_made": 0,
            "avg_latency_ms": 0.0,
            "errors": 0,
        }

    def _client(self):
        if self._groq_client is None:
            from groq import Groq
            self._groq_client = Groq(api_key=GROQ_API_KEY)
        return self._groq_client

    def set_vocab(self, vocab_dict: Dict[str, str]):
        """Inject vocabulary database (from vocab.py)."""
        self.vocab_db = vocab_dict.copy()
        logger.info(f"Loaded vocab: {len(vocab_dict)} entries")

    def set_dictionary(self, words: List[str]):
        """Inject the user dictionary (plain words from vocab.py)."""
        self.dictionary_words = [w for w in words if w and w.strip()]

    def add_context(self, recent_task: str):
        """Add recent task for context window."""
        self.context_history.append(recent_task)
        if len(self.context_history) > 5:
            self.context_history.pop(0)

    def refine_transcript(
        self, partial_text: str, context: str = "", timeout: int = 8
    ) -> Dict:
        """
        Refine partial transcript using Groq Mixtral.

        Args:
            partial_text: Raw STT output
            context: Optional background info
            timeout: Max seconds to wait for response

        Returns:
            {
                "refined": str,               # Corrected text
                "changes": List[str],         # ["from->to", ...]
                "confidence": float,          # 0.0-1.0
                "latency_ms": float,
                "error": Optional[str]
            }
        """
        start_time = time.time()

        if not partial_text or not partial_text.strip():
            return {
                "refined": partial_text,
                "changes": [],
                "confidence": 1.0,
                "latency_ms": 0.0,
                "error": None,
            }

        if not GROQ_API_KEY:
            return {
                "refined": partial_text,
                "changes": [],
                "confidence": 0.5,
                "latency_ms": 0.0,
                "error": "GROQ_API_KEY not set",
            }

        # Build context
        context_str = ""
        if self.context_history:
            context_str = "Recent tasks:\n" + "\n".join(
                f"- {t}" for t in self.context_history[-3:]
            )

        vocab_str = json.dumps(self.vocab_db, indent=2) if self.vocab_db else "{}"
        dict_str = json.dumps(self.dictionary_words) if self.dictionary_words else "[]"

        # Replacement lists are short; no need to scale with input length.
        max_tokens = 500

        # The model only proposes word-level replacements; we apply them ourselves.
        prompt = f"""TASK: Find speech-to-text errors in the transcript. Propose word replacements ONLY — never rewrite the text.

RULES (STRICT):
1. Each replacement is a single word or short phrase that appears VERBATIM in the input, plus its correction.
2. Fix: homophones (their/there), run-on words (manytasks -> many tasks), words that are likely mis-hearings of a USER DICTIONARY word, and vocabulary pairs below.
3. The user dictionary lists words the speaker actually uses. If an input word sounds like one of them, replace it with the dictionary word.
4. Do NOT reword, summarize, restyle, or fix grammar. If unsure, propose nothing.
5. Return ONLY valid JSON. No markdown. No preamble.

USER DICTIONARY:
{dict_str}

VOCABULARY PAIRS (heard -> correct):
{vocab_str}

CONTEXT:
{context_str if context_str else "(no recent tasks)"}

INPUT TEXT:
"{partial_text}"

OUTPUT JSON (no markdown, no backticks):
{{"replacements": [{{"from": "exact word in text", "to": "correction"}}], "confidence": 0.0}}
"""

        try:
            response = self._client().chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=max_tokens,
                timeout=timeout,
            )

            response_text = response.choices[0].message.content.strip()

            # Clean markdown fences if model ignored instructions
            if "```" in response_text:
                start_idx = response_text.find("{")
                end_idx = response_text.rfind("}") + 1
                if start_idx >= 0 and end_idx > start_idx:
                    response_text = response_text[start_idx:end_idx]

            result = json.loads(response_text)
            latency = (time.time() - start_time) * 1000

            refined, changes = self._apply_replacements(
                partial_text, result.get("replacements", [])
            )

            self.stats["total_refinements"] += 1
            self.stats["changes_made"] += len(changes)
            # Rolling average
            n = self.stats["total_refinements"]
            self.stats["avg_latency_ms"] = (
                self.stats["avg_latency_ms"] * (n - 1) + latency
            ) / n

            if changes:
                logger.info(f"Refined: {changes} ({latency:.0f}ms)")

            return {
                "refined": refined,
                "changes": changes,
                "confidence": float(result.get("confidence", 0.7)),
                "latency_ms": latency,
                "error": None,
            }

        except Exception as e:
            logger.error(f"Refiner error: {e}")
            self.stats["errors"] += 1
            return {
                "refined": partial_text,
                "changes": [],
                "confidence": 0.3,
                "latency_ms": (time.time() - start_time) * 1000,
                "error": str(e),
            }

    def _apply_replacements(
        self, text: str, replacements: List[dict]
    ) -> "tuple[str, List[str]]":
        """Validate and apply model-proposed word replacements.

        A replacement is applied only when:
          - `from` actually occurs in the text as a whole word/phrase, and
          - `to` is a known dictionary/vocab word, OR is similar enough to
            `from` to be a homophone/run-on fix (blocks hallucinated rewrites).
        """
        from core.vocab import _similarity

        known_targets = {w.lower() for w in self.dictionary_words}
        known_targets.update(v.lower() for v in self.vocab_db.values())

        changes: List[str] = []
        for rep in replacements or []:
            if not isinstance(rep, dict):
                continue
            src = str(rep.get("from", "")).strip()
            dst = str(rep.get("to", "")).strip()
            if not src or not dst or src.lower() == dst.lower():
                continue
            pattern = re.compile(r"\b" + re.escape(src) + r"\b", re.IGNORECASE)
            if not pattern.search(text):
                continue
            if dst.lower() not in known_targets and _similarity(src, dst) < _MIN_FREE_SIMILARITY:
                logger.info(f"Refiner: rejected replacement '{src}' -> '{dst}'")
                continue
            text = pattern.sub(dst, text)
            changes.append(f"{src}->{dst}")
        return text, changes

    def refine_batch(self, transcripts: List[str]) -> List[Dict]:
        """Refine multiple transcripts."""
        return [self.refine_transcript(t) for t in transcripts]

    def get_stats(self) -> Dict:
        """Return performance stats."""
        return self.stats.copy()

    def reset_stats(self):
        """Reset statistics."""
        self.stats = {
            "total_refinements": 0,
            "changes_made": 0,
            "avg_latency_ms": 0.0,
            "errors": 0,
        }


# Test standalone
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    refiner = STTRefiner()

    tests = [
        "create a task for their important project",
        "call john smith about the deadline",
        "setup the queue four database config",
    ]

    for test in tests:
        result = refiner.refine_transcript(test)
        print(f"\nInput:  {test}")
        print(f"Output: {result['refined']}")
        print(f"Changes: {result['changes']}")
        print(f"Latency: {result['latency_ms']:.0f}ms")
