"""
core/stt_refiner.py — AI refinement for STT output

Groq Mixtral-powered refinement system.
Fixes homophones, run-on words, missing punctuation.
Real-time corrections on final transcript (not mid-stream to save tokens).
"""

import json
import logging
import os
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


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

    def __init__(self, model: str = "mixtral-8x7b-32768"):
        self._groq_client = None
        self.vocab_db: Dict[str, str] = {}
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

        # Strict prompt to prevent hallucination
        prompt = f"""TASK: Fix speech-to-text errors in task title. ONLY fix actual errors.

RULES (STRICT):
1. ONLY apply vocabulary replacements below. NO other changes.
2. Fix homophones (their/there), run-on words, missing punctuation.
3. Convert spoken emails: "name at domain dot com" → "name@domain.com"
4. Handle scratch-that: remove everything before "scratch that" / "delete that" / "no wait" / "actually i meant" and keep only what follows.
5. Preserve original intent. No rewording.
6. Keep under 50 words.
7. Return ONLY valid JSON. No markdown. No preamble.

VOCABULARY (apply ONLY these):
{vocab_str}

CONTEXT:
{context_str if context_str else "(no recent tasks)"}

INPUT TEXT:
"{partial_text}"

OUTPUT JSON (no markdown, no backticks):
{{"refined": "...", "changes": ["word1->word2"], "confidence": 0.0}}
"""

        try:
            response = self._client().chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=150,
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

            self.stats["total_refinements"] += 1
            if result.get("changes"):
                self.stats["changes_made"] += len(result["changes"])
            # Rolling average
            n = self.stats["total_refinements"]
            self.stats["avg_latency_ms"] = (
                self.stats["avg_latency_ms"] * (n - 1) + latency
            ) / n

            refined = result.get("refined", partial_text)
            logger.info(
                f"Refined: '{partial_text[:40]}...' -> '{refined[:40]}...' ({latency:.0f}ms)"
            )

            return {
                "refined": refined,
                "changes": result.get("changes", []),
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
