#!/usr/bin/env python3
"""Interactive test: type phrases, run through pipeline, display results."""

import asyncio
import logging
from core.stt_refiner import STTRefiner
from core.smart_paste import SmartPasteEngine
from core.vocab import VocabManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_with_real_voice():
    print("\n" + "=" * 70)
    print("🎤 REAL VOICE TEST")
    print("=" * 70)
    print("\nEnter test phrases to process through full pipeline.")
    print("Type 'quit' to exit.\n")

    refiner = STTRefiner()
    paste = SmartPasteEngine()
    vocab = VocabManager()

    vocab.add_correction("groq", "Groq")
    vocab.add_correction("python", "Python")
    refiner.set_vocab(vocab.vocab_db)

    test_count = 0

    while True:
        try:
            phrase = input("\n📝 Enter phrase (or 'quit'): ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if phrase.lower() == "quit":
            break

        if not phrase:
            continue

        test_count += 1

        print(f"\n--- Test #{test_count} ---")
        print(f"Input:  {phrase}")

        # Step 1: Refine
        logger.info("Step 1: Refining...")
        refined_result = refiner.refine_transcript(phrase)
        refined = refined_result["refined"]

        print(f"Refined: {refined}")
        if refined_result["changes"]:
            print(f"Changes: {refined_result['changes']}")
        print(f"Latency: {refined_result['latency_ms']:.0f}ms")

        # Step 2: Vocab
        logger.info("Step 2: Applying vocab...")
        corrected, changes = vocab.apply_corrections(refined)

        if changes:
            print(f"Vocab corrections: {changes}")
            print(f"Corrected: {corrected}")

        # Step 3: Format
        logger.info("Step 3: Formatting...")
        formatted = paste.format_for_task(corrected)

        print(f"Formatted: {formatted}")
        print(f"\n✓ Ready to paste: {formatted}")

    # Summary
    print(f"\n" + "=" * 70)
    print(f"Tests completed: {test_count}")
    refiner_stats = refiner.get_stats()
    print(f"Avg refiner latency: {refiner_stats['avg_latency_ms']:.0f}ms")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_with_real_voice())
