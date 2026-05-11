"""core/wizprompt.py — Dynamic Multi-Agent Prompt Optimization System."""
from __future__ import annotations
import asyncio
import hashlib
import logging
import os
import re
import time
from typing import Dict, List, Optional
from openai import AsyncOpenAI

log = logging.getLogger("core.wizprompt")

# Lazy import to avoid circular dependency at module load time
_wizprompt_memory = None

def _get_memory():
    global _wizprompt_memory
    if _wizprompt_memory is None:
        import core.wizprompt_memory as _wizprompt_memory
    return _wizprompt_memory


def _load_model_setting(key: str, default: str) -> str:
    try:
        import json
        settings_path = os.path.join(os.path.dirname(__file__), "..", "data", "settings.json")
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    except Exception:
        pass
    return os.getenv(key, default)


WIZPROMPT_MODEL = _load_model_setting("WIZPROMPT_MODEL", "google/gemini-3-flash-preview")
WIZPROMPT_TEMP = float(os.getenv("WIZPROMPT_TEMP", "0.2"))
MAX_TOKENS = int(os.getenv("WIZPROMPT_MAX_TOKENS", "1200"))
SYNTH_MAX_TOKENS = int(os.getenv("WIZPROMPT_SYNTHESIS_MAX_TOKENS", "1800"))
FAST_MAX_TOKENS = int(os.getenv("WIZPROMPT_FAST_MAX_TOKENS", "2000"))

_async_openrouter_client: Optional[AsyncOpenAI] = None


def _get_async_client() -> AsyncOpenAI:
    global _async_openrouter_client
    if _async_openrouter_client is None:
        _async_openrouter_client = AsyncOpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY", ""),
            base_url="https://openrouter.ai/api/v1",
            default_headers={"HTTP-Referer": "https://whiztant.com", "X-Title": "Wiztant"},
        )
    return _async_openrouter_client


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
    "Output Format (IMPORTANT - NO MARKDOWN):\n"
    "- Use plain text only. Do NOT use markdown syntax like #, ##, **, *, `, or tables.\n"
    "- Use clear section labels in plain text (e.g., 'Role:', 'Context:', 'Goal:', 'Constraints:').\n"
    "- Use simple numbered lists (1., 2., 3.) or bullet points (-) where helpful.\n"
    "- Preserve the original intent while incorporating all improvements.\n"
    "- If emotional framing is provided, embed it naturally in the opening directive.\n"
    "- Do NOT include an 'Optimizations Applied' summary section. Just give the final prompt.\n\n"
    "Quality bar: The output should be a prompt that an expert could have written from scratch, formatted as clean plain text."
)

FAST_SINGLE_SHOT = (
    "You are an elite prompt engineer. Your job is to analyze and optimize the user's prompt in a single pass.\n\n"
    "Analyze across these 4 dimensions:\n"
    "1. STRUCTURE: logical flow, hierarchy, output format clarity, step numbering, scope boundaries.\n"
    "2. SEMANTICS: ambiguous language, missing examples, implicit assumptions, vocabulary precision, constraints clarity.\n"
    "3. EDGE CASES: boundary conditions, contradictions, incomplete coverage, fragile assumptions, adversarial inputs.\n"
    "4. EMOTIONAL FRAMING: pick the single best emotion from this list that unlocks peak LLM performance: "
    + ", ".join(EMOTIONS) + ".\n\n"
    "Output Format (STRICT — use these exact XML-like tags):\n"
    "<optimized_prompt>\n"
    "[The fully optimized prompt here. Plain text only. No markdown (#, ##, **, *, `, tables). "
    "Use clear section labels like 'Role:', 'Context:', 'Goal:', 'Constraints:'. "
    "Use simple numbered lists or bullet points. Preserve original intent.]\n"
    "</optimized_prompt>\n\n"
    "<emotion>[single emotion name from the list above]</emotion>\n\n"
    "<framing>[One 1-2 sentence directive on how the emotional framing is embedded]</framing>\n\n"
    "<critique_structure>[2-3 bullet points of structural weaknesses and improvements]</critique_structure>\n\n"
    "<critique_semantic>[2-3 bullet points of semantic issues and fixes]</critique_semantic>\n\n"
    "<critique_edge>[2-3 bullet points of edge cases and guardrails, or 'N/A' if none found]</critique_edge>\n\n"
    "Rules:\n"
    "- The optimized prompt inside <optimized_prompt> must be production-ready and coherent.\n"
    "- Do not output any text outside the tags.\n"
    "- Do not include a summary section.\n"
    "- If a preset focus is provided, bias the optimization toward that focus."
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


# =============================================================
#  CACHE & IN-FLIGHT DEDUPLICATION
# =============================================================

_CACHE_TTL_SECONDS = 300  # 5 minutes
_result_cache: dict[str, tuple[float, dict]] = {}
_inflight: dict[str, asyncio.Future[dict]] = {}


def _cache_key(prompt: str, model: str | None, preset: str | None, mode: str) -> str:
    normalized = prompt.strip().lower()
    raw = f"{normalized}::{model or ''}::{preset or ''}::{mode}"
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(key: str) -> dict | None:
    now = time.time()
    entry = _result_cache.get(key)
    if entry is None:
        return None
    ts, result = entry
    if now - ts > _CACHE_TTL_SECONDS:
        del _result_cache[key]
        return None
    log.info("WizPrompt: cache hit")
    return result


def _set_cached(key: str, result: dict) -> None:
    _result_cache[key] = (time.time(), result)
    # Prune old entries if cache grows beyond 50 items
    if len(_result_cache) > 50:
        now = time.time()
        for k in list(_result_cache.keys()):
            if now - _result_cache[k][0] > _CACHE_TTL_SECONDS:
                del _result_cache[k]


# =============================================================
#  DEEP MODE: MULTI-AGENT (legacy, slower)
# =============================================================

def _deduct_actual_tokens(feature: str, resp, model: str | None = None) -> int:
    """
    Extract actual token usage from an API response and deduct exact credits.
    Returns the number of credits deducted.
    Allows a grace overdraft of up to 2 credits to avoid failing mid-session.
    """
    try:
        from core.credit_system import (
            calculate_api_cost,
            calculate_credits,
            deduct,
            get_current_user_id,
            get_balance,
            refill,
        )
        usage = getattr(resp, "usage", None)
        if usage is None:
            return 0
        user_id = get_current_user_id()
        actual_input = getattr(usage, "prompt_tokens", 0)
        actual_output = getattr(usage, "completion_tokens", 0)
        api_cost = calculate_api_cost(model or WIZPROMPT_MODEL, actual_input, actual_output)
        credits = calculate_credits(api_cost)
        if credits <= 0:
            return 0

        # Primary deduction
        if deduct(user_id, feature, credits, model=model or WIZPROMPT_MODEL):
            log.info("%s: deducted %d credits for %d in / %d out tokens (%s)",
                     feature, credits, actual_input, actual_output, model or WIZPROMPT_MODEL)
            return credits

        # Grace overdraft: allow up to 2 credits negative balance
        balance = get_balance(user_id)
        shortfall = credits - balance
        if shortfall <= 2:
            # Force deduct by temporarily refilling the shortfall, then deduct full amount
            refill(user_id, shortfall, source=f"{feature}_grace_overdraft")
            if deduct(user_id, feature, credits, model=model or WIZPROMPT_MODEL):
                log.info("%s: deducted %d credits with %d grace overdraft (balance was %d)",
                         feature, credits, shortfall, balance)
                return credits
    except Exception as e:
        log.warning("Token credit deduction failed: %s", e)
    return 0


def _call_agent(agent_type: str, user_prompt: str, model: str | None = None) -> str:
    # Kept as sync for run_in_executor compatibility in deep mode
    from openai import OpenAI
    client = OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        base_url="https://openrouter.ai/api/v1",
        default_headers={"HTTP-Referer": "https://whiztant.com", "X-Title": "Wiztant"},
    )
    system = AGENTS[agent_type]
    msg = f"Critique this prompt for {agent_type.replace('_',' ')} issues:\n{user_prompt}"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": msg}]
    try:
        resp = client.chat.completions.create(
            model=model or WIZPROMPT_MODEL,
            messages=messages,
            temperature=WIZPROMPT_TEMP,
            max_tokens=MAX_TOKENS,
            extra_body={"include_reasoning": False}
        )
        _deduct_actual_tokens("reprompt_deep_agent", resp, model)
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


def _synthesize(user_prompt: str, critiques: dict, emotional: Optional[dict], model: str | None = None, preset: str | None = None) -> str:
    synthesis_prompt = SYNTHESIS
    if preset:
        synthesis_prompt = synthesis_prompt + "\n\nADDITIONAL OPTIMIZATION FOCUS:\n" + preset
    parts = [f"STRUCTURAL CRITIQUE:\n{critiques.get('structure','N/A')}\n",
             f"SEMANTIC CRITIQUE:\n{critiques.get('semantic','N/A')}\n"]
    if "edge_case" in critiques:
        parts.append(f"EDGE CASE CRITIQUE:\n{critiques['edge_case']}\n")
    if emotional:
        parts.append(f"EMOTIONAL DIRECTIVE:\nEMOTION: {emotional['emotion']}\nFRAMING_DIRECTIVE: {emotional['framing_directive']}\n")
    parts.append(f"ORIGINAL PROMPT:\n{user_prompt}")
    messages = [{"role": "system", "content": synthesis_prompt}, {"role": "user", "content": "\n".join(parts)}]
    from openai import OpenAI
    client = OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        base_url="https://openrouter.ai/api/v1",
        default_headers={"HTTP-Referer": "https://whiztant.com", "X-Title": "Wiztant"},
    )
    try:
        resp = client.chat.completions.create(
            model=model or WIZPROMPT_MODEL,
            messages=messages,
            temperature=WIZPROMPT_TEMP,
            max_tokens=SYNTH_MAX_TOKENS,
            extra_body={"include_reasoning": False}
        )
        _deduct_actual_tokens("reprompt_deep_synth", resp, model)
        return resp.choices[0].message.content or ""
    except Exception as e:
        log.error("Synthesis failed: %s", e)
        raise e


async def _optimize_deep(
    user_prompt: str,
    model: str | None = None,
    preset: str | None = None,
    selected: list[str] | None = None,
    config: dict | None = None,
) -> dict:
    """Original multi-agent pipeline. 3–5 LLM calls."""
    loop = asyncio.get_event_loop()
    coros = [(a, loop.run_in_executor(None, _call_agent, a, user_prompt, model)) for a in selected]
    critiques = {a: await c for a, c in coros}
    emotional = parse_emotional(critiques.get("emotional", "")) if "emotional" in critiques else None
    try:
        optimized = await loop.run_in_executor(None, _synthesize, user_prompt, critiques, emotional, model, preset)
        synthesis_failed = False
    except Exception as e:
        optimized = ""
        synthesis_failed = True

    return {
        "optimized_prompt": optimized,
        "agent_count": len(selected),
        "prompt_size": config["size_category"] if config else "unknown",
        "emotional_state": emotional["emotion"] if emotional else None,
        "framing_directive": emotional["framing_directive"] if emotional else None,
        "critiques": critiques,
        "line_count": len(user_prompt.split("\n")),
        "synthesis_failed": synthesis_failed,
        "preset_used": preset,
        "examples_used": 0,
        "example_ids": [],
        "cluster_id": None,
    }


# =============================================================
#  FAST MODE: SINGLE-SHOT
# =============================================================

_TAG_RE = re.compile(r"<(optimized_prompt|emotion|framing|critique_structure|critique_semantic|critique_edge)>(.*?)</\1>", re.DOTALL | re.IGNORECASE)


def _parse_fast_response(text: str) -> dict:
    """Extract structured fields from single-shot XML-like tagged output."""
    tags: dict[str, str] = {}
    for match in _TAG_RE.finditer(text):
        tags[match.group(1).lower()] = match.group(2).strip()

    optimized = tags.get("optimized_prompt", "").strip()
    emotion = tags.get("emotion", "").strip().lower()
    framing = tags.get("framing", "").strip()
    critique_structure = tags.get("critique_structure", "N/A")
    critique_semantic = tags.get("critique_semantic", "N/A")
    critique_edge = tags.get("critique_edge", "N/A")

    # Fallback: if tags missing, treat entire response as optimized prompt
    if not optimized:
        optimized = text.strip()
        critique_structure = critique_semantic = critique_edge = "N/A"
        emotion = ""
        framing = ""

    # Clean up common markdown artifacts the model may have ignored
    optimized = re.sub(r"^```\w*\n?|```\s*$", "", optimized, flags=re.MULTILINE)

    critiques: dict[str, str] = {
        "structure": critique_structure,
        "semantic": critique_semantic,
    }
    if critique_edge and critique_edge.lower() != "n/a":
        critiques["edge_case"] = critique_edge
    if emotion:
        critiques["emotional"] = f"EMOTION: {emotion}\nFRAMING_DIRECTIVE: {framing}"

    return {
        "optimized_prompt": optimized,
        "emotional_state": emotion if emotion else None,
        "framing_directive": framing if framing else None,
        "critiques": critiques,
    }


async def _optimize_fast(
    user_prompt: str,
    model: str | None = None,
    preset: str | None = None,
    line_count: int = 1,
) -> dict:
    """Single LLM call optimization. Target latency ~1–2s."""
    mem = _get_memory()
    examples, cluster_id, style_bias = await mem.retrieve_examples_for_prompt(user_prompt, preset, limit=3)
    example_ids = [ex["id"] for ex in examples]

    few_shot_block = mem.format_few_shot_block(examples)
    system = FAST_SINGLE_SHOT
    if preset:
        system = system + "\n\nADDITIONAL OPTIMIZATION FOCUS:\n" + preset
    if few_shot_block:
        system = few_shot_block + "\n" + system
    if style_bias:
        system = system + "\n\n" + style_bias

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Optimize this prompt:\n{user_prompt}"},
    ]

    client = _get_async_client()
    resp = await client.chat.completions.create(
        model=model or WIZPROMPT_MODEL,
        messages=messages,
        temperature=WIZPROMPT_TEMP,
        max_tokens=FAST_MAX_TOKENS,
        extra_body={"include_reasoning": False},
    )
    content = resp.choices[0].message.content or ""

    # Deduct exact credits based on actual token usage
    _deduct_actual_tokens("reprompt_fast", resp, model)

    parsed = _parse_fast_response(content)

    config = select_agents_by_size(line_count)
    selected = config["selected_agents"]

    return {
        "optimized_prompt": parsed["optimized_prompt"],
        "agent_count": len(selected),
        "prompt_size": config["size_category"],
        "emotional_state": parsed["emotional_state"],
        "framing_directive": parsed["framing_directive"],
        "critiques": parsed["critiques"],
        "line_count": line_count,
        "synthesis_failed": not parsed["optimized_prompt"],
        "preset_used": preset,
        "examples_used": len(examples),
        "example_ids": example_ids,
        "cluster_id": cluster_id,
    }


# =============================================================
#  VALIDATION
# =============================================================

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


# Mapping from TuneHub persona weight keys to WizPrompt agent names
_PERSONA_WEIGHT_TO_AGENT = {
    "research": "structure",
    "write": "semantic",
    "build": "edge_case",
    "debug": "edge_case",
    "plan": "structure",
}


def _apply_persona_weights(selected: list, persona_weights: dict) -> list:
    """Reorder selected agents based on TuneHub persona weights."""
    if not persona_weights:
        return selected

    # Calculate priority score for each agent based on mapped persona weights
    agent_scores: dict[str, float] = {a: 0.0 for a in selected}
    for persona_key, weight in persona_weights.items():
        agent = _PERSONA_WEIGHT_TO_AGENT.get(persona_key)
        if agent and agent in agent_scores:
            agent_scores[agent] += float(weight)

    # Sort selected agents by score descending, preserving original order for ties
    scored = [(a, agent_scores[a]) for a in selected]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [a for a, _ in scored]


# =============================================================
#  PUBLIC API
# =============================================================

async def optimize_prompt_with_dynamic_agents(
    user_prompt: str,
    model: str | None = None,
    feature_input: dict | None = None,
    preset: str | None = None,
    mode: str = "fast",
) -> dict:
    """Optimize a prompt.

    Args:
        user_prompt: The raw prompt text to optimize.
        model: Optional override model ID.
        feature_input: Optional TuneHub feature input.
        preset: Optional preset ID or system prompt addendum string.
        mode: "fast" (single-shot, default) or "deep" (multi-agent legacy).
    """
    if not user_prompt or not user_prompt.strip():
        raise ValueError("Prompt cannot be empty")

    error = validate_prompt(user_prompt)
    if error:
        raise ValueError(error)

    line_count = len(user_prompt.split("\n"))
    config = select_agents_by_size(line_count)
    selected = list(config["selected_agents"])

    # Apply TuneHub persona weights if present
    persona_weights = (feature_input or {}).get("persona_weights")
    if persona_weights:
        selected = _apply_persona_weights(selected, persona_weights)
        log.info("WizPrompt: persona weights applied, agent order: %s", selected)

    # Resolve preset addendum if an ID was passed
    preset_addendum: str | None = None
    if preset:
        try:
            from core.presets import get_preset_by_id
            p = get_preset_by_id(preset)
            if p:
                preset_addendum = p.system_prompt_addendum
            else:
                preset_addendum = preset  # treat as raw addendum string
        except Exception:
            preset_addendum = preset

    cache_key = _cache_key(user_prompt, model, preset_addendum, mode)

    # Check cache
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    # Check in-flight deduplication
    future = _inflight.get(cache_key)
    if future is not None and not future.done():
        log.info("WizPrompt: dedup — waiting for in-flight request")
        return await future

    # Create future for deduplication
    loop = asyncio.get_event_loop()
    future = loop.create_future()
    _inflight[cache_key] = future

    log.info(
        "WizPrompt: %s prompt (%d lines), mode=%s, model=%s, preset=%s",
        config["size_category"], line_count, mode, model or WIZPROMPT_MODEL, preset if preset else "none"
    )

    # Credit pre-check for RePrompt (actual deduction happens post-call based on real tokens)
    try:
        from core.credit_system import (
            calculate_reprompt_credits,
            can_afford,
            get_current_user_id,
        )
        user_id = get_current_user_id()
        max_estimate = calculate_reprompt_credits(model or WIZPROMPT_MODEL)
        if not can_afford(user_id, max_estimate):
            raise RuntimeError(f"Insufficient credits for RePrompt. Need up to {max_estimate} credits.")
        log.info("WizPrompt: pre-authorized %d credits for user %s", max_estimate, user_id)
    except RuntimeError:
        raise
    except Exception as e:
        log.warning("WizPrompt credit pre-check failed (continuing): %s", e)

    try:
        if mode == "deep":
            result = await _optimize_deep(user_prompt, model=model, preset=preset_addendum, selected=selected, config=config)
        else:
            result = await _optimize_fast(user_prompt, model=model, preset=preset_addendum, line_count=line_count)
    except Exception as e:
        log.error("WizPrompt optimization failed: %s", e)
        future.set_exception(e)
        del _inflight[cache_key]
        raise

    _set_cached(cache_key, result)
    future.set_result(result)
    del _inflight[cache_key]
    return result
