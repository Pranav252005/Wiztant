"""core/wizprompt.py — Dynamic Multi-Agent Prompt Optimization System."""
from __future__ import annotations
import asyncio
import logging
import os
import re
from typing import Dict, List, Optional
from openai import OpenAI

log = logging.getLogger("core.wizprompt")

WIZPROMPT_MODEL = os.getenv("WIZPROMPT_MODEL", "anthropic/claude-sonnet-4-20250514")
WIZPROMPT_TEMP = float(os.getenv("WIZPROMPT_TEMP", "0.2"))
MAX_TOKENS = int(os.getenv("WIZPROMPT_MAX_TOKENS", "1200"))
SYNTH_MAX_TOKENS = int(os.getenv("WIZPROMPT_SYNTHESIS_MAX_TOKENS", "1800"))

_openrouter_client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY", ""),
    base_url="https://openrouter.ai/api/v1",
    default_headers={"HTTP-Referer": "https://whiztant.com", "X-Title": "Wiztant"},
)

EMOTIONS = [
    "admiration","adoration","aesthetic appreciation","amusement","anger",
    "anxiety","awe","awkwardness","boredom","calmness","confusion",
    "craving","disgust","empathic pain","entrancement","excitement",
    "fear","horror","interest","joy","nostalgia","relief",
    "clearance","sadness","satisfaction","paranoid","surprise",
]

STRUCTURE = (
    "You are a prompt architect obsessed with logical flow, organization, and clarity.\n\n"
    "Your mandate: Make this prompt's structure bulletproof.\n\n"
    "Analyze the following aspects:\n"
    "1. Logical flow: Are instructions in optimal order?\n"
    "2. Hierarchy: Is the prompt organized with clear primary/secondary/tertiary goals?\n"
    "3. Output format: Is the expected output format explicitly stated?\n"
    "4. Steps: If multi-step, are steps numbered and clear?\n"
    "5. Boundaries: Are scope and limitations defined?\n\n"
    "Critique Format:\n"
    "- List 2-3 structural weaknesses (be specific)\n"
    "- Suggest 2-3 structural improvements\n"
    "- Rate clarity on scale 1-10\n\n"
    "Do NOT critique wording, vocabulary, or robustness. Focus ONLY on architecture."
)
SEMANTIC = (
    "You are a semantic precision expert. Every word must earn its place.\n\n"
    "Your mandate: Remove ambiguity, ensure specificity, catch vague language.\n\n"
    "Analyze the following aspects:\n"
    "1. Ambiguous language: What words/phrases are unclear or could be interpreted multiple ways?\n"
    "2. Missing examples: Where would concrete examples eliminate ambiguity?\n"
    "3. Implicit assumptions: What assumptions does the prompt make that should be explicit?\n"
    "4. Vocabulary precision: Are technical terms defined? Is jargon necessary?\n"
    "5. Constraints clarity: Are all requirements and constraints explicitly stated?\n\n"
    "Critique Format:\n"
    "- List 2-3 semantic weaknesses with examples\n"
    "- Suggest 2-3 semantic improvements (specific word changes, added examples)\n"
    "- Rate precision on scale 1-10\n\n"
    "Do NOT critique structure, edge cases, or emotional framing. Focus ONLY on semantics."
)
EDGE = (
    "You are an adversarial prompt tester. Your job: break this prompt and find failure modes.\n\n"
    "Your mandate: Identify boundary conditions, edge cases, and fragile assumptions.\n\n"
    "Analyze the following aspects:\n"
    "1. Boundary conditions: What happens at input extremes (empty, huge, malformed)?\n"
    "2. Contradictions: Are there conflicting instructions?\n"
    "3. Incomplete coverage: What scenarios are not addressed?\n"
    "4. Assumption fragility: What assumptions will break under unusual but valid inputs?\n"
    "5. Adversarial inputs: How would a user try to break this prompt's intent?\n\n"
    "Critique Format:\n"
    "- List 3-4 edge cases/robustness issues that could cause failure\n"
    "- Suggest guardrails or clarifications to handle them\n"
    "- Rate robustness on scale 1-10\n\n"
    "Do NOT critique structure, semantics, or emotional framing. Focus ONLY on failure modes."
)
EMOTIONAL = (
    "You are an emotional calibration expert. LLMs perform measurably better when prompts \n"
    "are framed with optimal emotional/cognitive states.\n\n"
    "Your mandate: Identify the emotional state that unlocks best performance for THIS task.\n\n"
    "The 27 Available Emotions:\n"
    + ", ".join(EMOTIONS) + "\n\n"
    "Analyze:\n"
    "1. Task intent: What is the core objective? (creative, analytical, careful, rigorous, etc.)\n"
    "2. Optimal cognitive state: What emotional frame would make an LLM excel at this?\n"
    "3. Anti-patterns: What emotional frames would HURT performance?\n\n"
    "Decision Framework:\n"
    "- Creative/exploratory tasks -> excitement, interest, awe, wonder\n"
    "- Analytical/logical tasks -> calmness, interest, admiration\n"
    "- Risk-aware/careful tasks -> anxiety (healthy), caution framing\n"
    "- Relationship/empathy tasks -> empathic pain, admiration, joy\n"
    "- Novel/breakthrough tasks -> awe, interest, surprise\n"
    "- Detail-oriented tasks -> calmness, satisfaction, interest\n\n"
    "Output Format (CRITICAL):\n"
    "EMOTION: [single emotion name from list]\n"
    "FRAMING_DIRECTIVE: [One 1-2 sentence directive on how to embed this into the prompt]\n\n"
    "Example:\n"
    "EMOTION: awe\n"
    "FRAMING_DIRECTIVE: Frame this task as exploring something profound and intellectually non-obvious. Position the user as a curious discoverer, not an executor.\n\n"
    "Do NOT critique structure, semantics, or edge cases. Focus ONLY on emotional optimization."
)
SYNTHESIS = (
    "You are the final prompt optimizer and arbiter. Your job: synthesize all expert critiques \n"
    "into ONE cohesive, production-ready prompt.\n\n"
    "You will receive:\n"
    "1. Structural critique (from Agent 1)\n"
    "2. Semantic critique (from Agent 2)\n"
    "3. Edge case critique (from Agent 3, if provided)\n"
    "4. Emotional calibration directive (from Agent 4, if provided)\n"
    "5. The original user prompt\n\n"
    "Your task:\n"
    "1. Identify the top 3-4 priority improvements across all critiques\n"
    "2. Integrate structural changes (Agent 1 suggestions)\n"
    "3. Refine vocabulary and examples (Agent 2 suggestions)\n"
    "4. Add guardrails for edge cases (Agent 3 suggestions, if present)\n"
    "5. Embed emotional framing (Agent 4 directive, if present)\n"
    "6. Ensure the final prompt is coherent, not fragmented\n\n"
    "Output Format:\n"
    "- Markdown with clear sections\n"
    "- Preserve the original intent while incorporating all improvements\n"
    "- If emotional framing is provided, embed it naturally in the system message or opening directive\n"
    "- Include a brief \"Optimizations Applied\" header listing what changed\n\n"
    "Quality bar: The output should be a prompt that an expert could have written from scratch."
)

AGENTS = {"structure": STRUCTURE, "semantic": SEMANTIC, "edge_case": EDGE, "emotional": EMOTIONAL}


def select_agents_by_size(line_count: int) -> dict:
    if line_count <= 0:
        line_count = 1
    if line_count <= 5:
        return {"size_category": "small", "selected_agents": ["structure", "semantic"]}
    elif line_count <= 15:
        return {"size_category": "medium", "selected_agents": ["structure", "semantic", "edge_case"]}
    return {"size_category": "large", "selected_agents": ["structure", "semantic", "edge_case", "emotional"]}


def _call_agent(agent_type: str, user_prompt: str, model: str | None = None) -> str:
    system = AGENTS[agent_type]
    msg = f"Critique this prompt for {agent_type.replace('_',' ')} issues:\n{user_prompt}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": msg}]
    try:
        resp = _openrouter_client.chat.completions.create(
            model=model or WIZPROMPT_MODEL,
            messages=messages,
            temperature=WIZPROMPT_TEMP,
            max_tokens=MAX_TOKENS,
            extra_body={"include_reasoning": False}
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        log.error("Agent %s failed: %s", agent_type, e)
        return f"[Agent {agent_type} failed: {e}]"


def parse_emotional(text: str) -> Optional[Dict[str, str]]:
    if not text:
        return None
    emo = re.search(r"EMOTION:\s*([\w\s]+)", text, re.IGNORECASE)
    frame = re.search(r"FRAMING_DIRECTIVE:\s*(.+?)(?:\n|$)", text, re.IGNORECASE | re.DOTALL)
    if not emo:
        return None
    return {"emotion": emo.group(1).strip().lower(), "framing_directive": (frame.group(1).strip() if frame else "")}


def _synthesize(user_prompt: str, critiques: dict, emotional: Optional[dict], model: str | None = None) -> str:
    parts = [f"STRUCTURAL CRITIQUE:\n{critiques.get('structure','N/A')}\n",
             f"SEMANTIC CRITIQUE:\n{critiques.get('semantic','N/A')}\n"]
    if "edge_case" in critiques:
        parts.append(f"EDGE CASE CRITIQUE:\n{critiques['edge_case']}\n")
    if emotional:
        parts.append(f"EMOTIONAL DIRECTIVE:\nEMOTION: {emotional['emotion']}\nFRAMING_DIRECTIVE: {emotional['framing_directive']}\n")
    parts.append(f"ORIGINAL PROMPT:\n{user_prompt}")
    messages = [{"role": "system", "content": SYNTHESIS}, {"role": "user", "content": "\n".join(parts)}]
    try:
        resp = _openrouter_client.chat.completions.create(
            model=model or WIZPROMPT_MODEL,
            messages=messages,
            temperature=WIZPROMPT_TEMP,
            max_tokens=SYNTH_MAX_TOKENS,
            extra_body={"include_reasoning": False}
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        log.error("Synthesis failed: %s", e)
        raise e


_GREETINGS = {"hello", "hi", "hey", "test", "testing", "ok", "okay", "yes", "no", "yep", "nope", "lol", "haha"}
_URL_RE = re.compile(r"^\s*https?://\S+\s*$", re.IGNORECASE)


def validate_prompt(text: str) -> str | None:
    """Return a human-readable error string if the prompt is silly/invalid, else None."""
    stripped = text.strip()
    if not stripped:
        return "Enter a prompt first."

    # Too short
    if len(stripped) < 15:
        return "That's too short to be a real prompt. Write at least a full sentence."

    # Just a URL
    if _URL_RE.match(stripped):
        return "That's just a link. Paste the actual content you want optimized."

    # Strip common punctuation for further checks
    letters_only = re.sub(r"[^a-zA-Z]", "", stripped)

    # No real words (only symbols / emojis / numbers)
    if len(letters_only) < 3:
        return "A prompt needs actual words, not just symbols or emojis."

    # Single char repeated (e.g., "aaaaaa", "!!!!!!!!")
    if len(stripped) > 5:
        most_common = max(set(stripped.lower()), key=stripped.lower().count)
        if stripped.lower().count(most_common) / len(stripped) > 0.6:
            return "Looks like accidental key mashing. Try writing a real prompt."

    # Single word repeated (e.g., "hello hello hello")
    words = stripped.lower().split()
    if len(words) > 2 and len(set(words)) == 1:
        return "Repeating the same word isn't a prompt. Be more descriptive."

    # Common greetings / filler only
    if len(words) <= 3 and all(w.strip(".,!?;:") in _GREETINGS for w in words):
        return "That's a greeting, not a prompt. Tell the AI what you want it to optimize."

    return None


async def optimize_prompt_with_dynamic_agents(user_prompt: str, model: str | None = None) -> dict:
    if not user_prompt or not user_prompt.strip():
        raise ValueError("Prompt cannot be empty")

    error = validate_prompt(user_prompt)
    if error:
        raise ValueError(error)

    line_count = len(user_prompt.split("\n"))
    config = select_agents_by_size(line_count)
    selected = config["selected_agents"]
    log.info("WizPrompt: %s prompt (%d lines), %d agents, model=%s", config["size_category"], line_count, len(selected), model or WIZPROMPT_MODEL)
    loop = asyncio.get_event_loop()
    coros = [(a, loop.run_in_executor(None, _call_agent, a, user_prompt, model)) for a in selected]
    critiques = {a: await c for a, c in coros}
    emotional = parse_emotional(critiques.get("emotional", "")) if "emotional" in critiques else None
    try:
        optimized = await loop.run_in_executor(None, _synthesize, user_prompt, critiques, emotional, model)
        synthesis_failed = False
    except Exception as e:
        optimized = ""
        synthesis_failed = True

    return {
        "optimized_prompt": optimized,
        "agent_count": len(selected),
        "prompt_size": config["size_category"],
        "emotional_state": emotional["emotion"] if emotional else None,
        "framing_directive": emotional["framing_directive"] if emotional else None,
        "critiques": critiques,
        "line_count": line_count,
        "synthesis_failed": synthesis_failed,
    }
