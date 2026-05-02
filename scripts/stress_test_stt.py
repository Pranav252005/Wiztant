#!/usr/bin/env python3
"""STRESS TEST: Run refiner, vocab, paste 100+ times."""

import asyncio
import random
import logging
from core.stt_refiner import STTRefiner
from core.smart_paste import SmartPasteEngine
from core.vocab import VocabManager

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

TEST_PHRASES = [
    "call john smith about the deadline",
    "create a task for the Q4 planning",
    "setup groq integration for python",
    "organize the meeting for tomorrow at two PM",
    "send email to the team about the project",
    "update the database with new configs",
    "review the queue for pending items",
    "book a call with the client next week",
    "check the status of the current project",
    "fix the bug in the api endpoint",
    "write documentation for the new feature",
    "setup the staging environment",
    "run tests on the main branch",
    "merge the pull request to production",
    "deploy the new version to live",
    "create a backup of the database",
    "monitor the system performance metrics",
    "optimize the code for better speed",
    "refactor the old legacy code",
    "implement the new authentication system",
]

VOCAB_CORRECTIONS = {
    "groq": "Groq",
    "python": "Python",
    "queue": "Q",
    "john": "John",
    "api": "API",
}


class STTStressTest:
    def __init__(self):
        self.refiner = STTRefiner()
        self.paste = SmartPasteEngine()
        self.vocab = VocabManager()
        self.vocab.vocab_db = VOCAB_CORRECTIONS.copy()
        self.refiner.set_vocab(VOCAB_CORRECTIONS)
        self.results = {
            "total_tests": 0,
            "refiner_errors": 0,
            "paste_errors": 0,
            "vocab_errors": 0,
            "refiner_latencies": [],
            "paste_latencies": [],
            "vocab_latencies": [],
            "total_latencies": [],
        }

    def test_single_pipeline(self, phrase: str) -> bool:
        import time
        start = time.time()

        try:
            # 1. Refine
            t1 = time.time()
            refined_result = self.refiner.refine_transcript(phrase)
            refine_latency = (time.time() - t1) * 1000
            self.results["refiner_latencies"].append(refine_latency)

            if refined_result["error"]:
                self.results["refiner_errors"] += 1

            refined = refined_result["refined"]

            # 2. Vocab
            t2 = time.time()
            corrected, _ = self.vocab.apply_corrections(refined)
            vocab_latency = (time.time() - t2) * 1000
            self.results["vocab_latencies"].append(vocab_latency)

            # 3. Paste format
            t3 = time.time()
            formatted = self.paste.format_for_task(corrected)
            paste_latency = (time.time() - t3) * 1000
            self.results["paste_latencies"].append(paste_latency)

            if not formatted:
                self.results["paste_errors"] += 1
                return False

            total_latency = (time.time() - start) * 1000
            self.results["total_latencies"].append(total_latency)

            return True

        except Exception as e:
            logger.error(f"Test error: {e}")
            self.results["refiner_errors"] += 1
            return False

    def run_batch(self, num_tests: int = 100):
        print(f"\n🔥 STRESS TEST: {num_tests} pipeline iterations")
        print("=" * 70)

        for i in range(num_tests):
            phrase = random.choice(TEST_PHRASES)
            success = self.test_single_pipeline(phrase)

            self.results["total_tests"] += 1

            if (i + 1) % 10 == 0:
                print(f"  ✓ Completed {i + 1}/{num_tests} tests")

        self.print_results()

    def print_results(self):
        print("\n" + "=" * 70)
        print("📊 STRESS TEST RESULTS")
        print("=" * 70)

        total = self.results["total_tests"]
        refiner_errors = self.results["refiner_errors"]
        paste_errors = self.results["paste_errors"]

        success_rate = (
            (total - refiner_errors - paste_errors) / total * 100
        ) if total > 0 else 0

        print(f"\n📈 OVERVIEW")
        print(f"  Total tests:      {total}")
        print(f"  Success rate:     {success_rate:.1f}%")
        print(f"  Refiner errors:   {refiner_errors}")
        print(f"  Paste errors:     {paste_errors}")

        if self.results["refiner_latencies"]:
            refiner_lats = self.results["refiner_latencies"]
            print(f"\n⚡ REFINER LATENCY")
            print(f"  Min:      {min(refiner_lats):.0f}ms")
            print(f"  Max:      {max(refiner_lats):.0f}ms")
            print(f"  Avg:      {sum(refiner_lats)/len(refiner_lats):.0f}ms")
            p95_idx = int(len(refiner_lats) * 0.95)
            if p95_idx < len(refiner_lats):
                print(f"  p95:      {sorted(refiner_lats)[p95_idx]:.0f}ms")

        if self.results["vocab_latencies"]:
            vocab_lats = self.results["vocab_latencies"]
            print(f"\n📚 VOCAB LATENCY")
            print(f"  Min:      {min(vocab_lats):.1f}ms")
            print(f"  Max:      {max(vocab_lats):.1f}ms")
            print(f"  Avg:      {sum(vocab_lats)/len(vocab_lats):.1f}ms")

        if self.results["total_latencies"]:
            total_lats = self.results["total_latencies"]
            print(f"\n🎯 TOTAL PIPELINE LATENCY")
            print(f"  Min:      {min(total_lats):.0f}ms")
            print(f"  Max:      {max(total_lats):.0f}ms")
            print(f"  Avg:      {sum(total_lats)/len(total_lats):.0f}ms")
            p95_idx = int(len(total_lats) * 0.95)
            if p95_idx < len(total_lats):
                print(f"  p95:      {sorted(total_lats)[p95_idx]:.0f}ms")
            print(f"  Budget:   2500ms (F9 press -> paste)")
            avg = sum(total_lats) / len(total_lats)
            if avg < 2500:
                print(f"  ✓ PASS: Under latency budget")
            else:
                print(f"  ✗ FAIL: Over latency budget")

        refiner_stats = self.refiner.get_stats()
        print(f"\n🤖 REFINER STATS")
        print(f"  Refinements:  {refiner_stats['total_refinements']}")
        print(f"  Changes made: {refiner_stats['changes_made']}")
        print(f"  Avg latency:  {refiner_stats['avg_latency_ms']:.0f}ms")
        print(f"  Errors:       {refiner_stats['errors']}")

        paste_stats = self.paste.get_paste_stats()
        print(f"\n📋 PASTE STATS")
        print(f"  Attempted:  {paste_stats['total_pastes']}")
        print(f"  Successful: {paste_stats['successful']}")
        print(f"  Failed:     {paste_stats['failed']}")
        if paste_stats['total_pastes'] > 0:
            sr = paste_stats['successful'] / paste_stats['total_pastes'] * 100
            print(f"  Success %:  {sr:.1f}%")
        print(f"  Avg latency: {paste_stats['avg_latency_ms']:.1f}ms")

        print("\n" + "=" * 70)


if __name__ == "__main__":
    tester = STTStressTest()
    tester.run_batch(100)
