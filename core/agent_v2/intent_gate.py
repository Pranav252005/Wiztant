"""
core/agent_v2/intent_gate.py — Intent classifier for the IDE Controller Agent.

Rejects off-topic requests before any LLM call. Fast regex for common cases;
lightweight LLM fallback for borderline cases.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

# =============================================================
#  TOPIC CLASSIFICATION
# =============================================================

# Topics the agent is ALLOWED to handle
ALLOWED_TOPICS = {
    "code", "build", "debug", "refactor", "design", "test", "deploy",
    "migrate", "optimize", "fix", "create", "update", "delete", "search",
    "navigate", "open", "close", "run", "install", "configure", "setup",
    "ship", "publish", "release", "review", "merge", "commit", "push",
    "pull", "clone", "init", "generate", "scaffold", "template", "component",
    "page", "route", "api", "schema", "model", "migration", "seed",
    "style", "theme", "layout", "responsive", "animation", "interaction",
    "form", "validation", "auth", "login", "logout", "register", "oauth",
    "permission", "role", "middleware", "hook", "context", "state",
    "database", "query", "mutation", "subscription", "cache", "index",
    "test", "spec", "e2e", "unit", "integration", "mock", "stub",
    "ci", "cd", "pipeline", "docker", "kubernetes", "terraform",
    "vercel", "netlify", "aws", "supabase", "firebase", "cloudflare",
    "eslint", "prettier", "typescript", "javascript", "python", "rust",
    "go", "java", "kotlin", "swift", "dart", "php", "ruby", "shell",
    "sql", "prisma", "drizzle", "mongodb", "postgres", "mysql", "redis",
    "react", "vue", "svelte", "angular", "solid", "next", "nuxt", "remix",
    "astro", "vite", "webpack", "rollup", "esbuild", "tailwind", "sass",
    "less", "css", "html", "svg", "canvas", "webgl", "threejs",
    "node", "bun", "deno", "npm", "yarn", "pnpm", "pip", "poetry",
    "cursor", "windsurf", "vscode", "lovable", "warp", "terminal",
    "git", "github", "gitlab", "bitbucket", "jira", "linear", "notion",
    "figma", "photoshop", "illustrator", "blender", "unity", "unreal",
    "electron", "tauri", "flutter", "react-native", "expo", "ionic",
    "pwa", "ssr", "csr", "ssg", "spa", "mpa", "jamstack", "serverless",
    "rest", "graphql", "grpc", "websocket", "sse", "webhook", "rpc",
    "jwt", "session", "cookie", "cors", "csrf", "xss", "sql-injection",
    "oauth2", "openid", "saml", "ldap", "mfa", "2fa", "totp", "webauthn",
    "stripe", "paypal", "razorpay", " lemon-squeezy", "paddle",
    "sendgrid", "resend", "postmark", "twilio", "slack-webhook",
    "s3", "gcs", "azure-blob", "r2", "cloudfront", "cdn",
    "prometheus", "grafana", "datadog", "sentry", "logrocket",
    "algolia", "meilisearch", "elasticsearch", "typesense",
    "ffmpeg", "imagemagick", "sharp", "puppeteer", "playwright",
}

# Topics the agent must REJECT
BLOCKED_TOPICS = {
    "weather", "forecast", "temperature", "rain", "snow", "sunny",
    "news", "headline", "breaking", "article", "journalist", "media",
    "sports", "game", "match", "score", "player", "team", "league",
    "politics", "election", "vote", "party", "government", "minister",
    "trivia", "quiz", "fact", "did you know", "random fact",
    "joke", "funny", "humor", "meme", "comedy", "laugh",
    "poem", "poetry", "verse", "rhyme", "sonnet", "haiku",
    "story", "fiction", "novel", "chapter", "narrative", "plot",
    "recipe", "cook", "bake", "ingredient", "kitchen", "food",
    "horoscope", "zodiac", "astrology", "star sign", "fortune",
    "dating", "relationship", "romance", "love advice", "crush",
    "medical", "health", "symptom", "diagnosis", "disease", "cure",
    "legal", "law", "lawyer", "sue", "court", "contract", "patent",
    "financial", "stock", "crypto", "invest", "trading", "dividend",
    "tax", "accounting", "budget", "mortgage", "loan", "insurance",
    "gaming", "gamer", "console", "playstation", "xbox", "nintendo",
    "minecraft", "fortnite", "roblox", "call of duty", "gta",
    "travel", "vacation", "flight", "hotel", "booking", "visa",
    "shopping", "buy", "discount", "coupon", "deal", "amazon", "ebay",
    "music", "song", "lyrics", "playlist", "spotify", "apple music",
    "movie", "film", "actor", "director", "netflix", "disney",
    "tv show", "series", "episode", "season", "streaming",
    "beauty", "fashion", "makeup", "skincare", "outfit", "style",
    "fitness", "gym", "workout", "diet", "weight loss", "calories",
    "pet", "dog", "cat", "animal", "veterinarian", "breed",
    "homework", "essay", "assignment", "exam", "thesis", "dissertation",
    "translation", "translate", "language learning", "duolingo",
    "meditation", "mindfulness", "yoga", "spiritual", "religion",
    "philosophy", "existential", "meaning of life", "consciousness",
    "conspiracy", "flat earth", "alien", "ufo", "cryptid",
    "lottery", "gamble", "bet", "casino", "poker", "slot",
    "curse", "swear", "insult", "offend", "harass", "bully",
    "nsfw", "adult", "porn", "sex", "nude", "explicit",
    "illegal", "drug", "weapon", "bomb", "terror", "hack",
}

# Prefixes that flip a blocked topic to allowed
# e.g. "optimize my gaming setup" → allowed because "optimize" prefix
ALLOWED_PREFIXES = {
    "optimize", "fix", "debug", "build", "create", "setup", "configure",
    "install", "deploy", "develop", "code", "program", "script",
    "automate", "integrate", "connect", "sync", "migrate", "refactor",
    "test", "benchmark", "profile", "monitor", "log", "trace",
}

# Fast regex patterns for blocked topics (catches common phrases)
_BLOCKED_PATTERNS = [
    # Weather
    r"\bwhat('s| is) the weather\b",
    r"\bweather (today|tomorrow|now|like)\b",
    r"\b(forecast|temperature|rain|snow|sunny|cloudy|windy)\b",
    # News
    r"\bwhat('s| is) (happening|in the news|new)\b",
    r"\bnews (today|headline|article|story)\b",
    # Sports
    r"\b(who won|score of|result of|highlights)\b",
    r"\b(sports|match|game|team|player|league)\b",
    # Trivia / Chat
    r"\b(tell me a|say a) (joke|poem|story|fact)\b",
    r"\b(what's|what is) your (favorite|opinion|thought)\b",
    r"\b(can you|please) (chat|talk|converse)\b",
    r"\b(hi|hello|hey|how are you|what's up)\b",
    # Personal / Life
    r"\b(should i|advice on|help me with) (dating|relationship|love|career)\b",
    r"\b(i feel|i'm sad|i'm happy|i'm angry|i'm stressed)\b",
    # Homework
    r"\b(do my|write my|help with) (homework|essay|assignment|thesis)\b",
    # Medical / Legal / Financial
    r"\b(i have|my) (symptom|pain|condition|disease)\b",
    r"\b(should i see a|do i need a) (doctor|lawyer|accountant)\b",
    r"\b(what stock|should i invest|buy|sell) (stock|crypto|bitcoin)\b",
    # Random
    r"\b(why is the sky blue|meaning of life|who are you|what are you)\b",
    r"\b(count to|alphabet|sing|dance|draw a)\b",
]

_COMPILED_BLOCKED = [re.compile(p, re.IGNORECASE) for p in _BLOCKED_PATTERNS]

# Allowed code/build prefixes that override blocked keywords
_ALLOWED_CODE_PATTERNS = [
    r"\b(build|create|make|develop|code|write)\b.*\b(app|website|site|page|component|api|db|database|schema|project)\b",
    r"\b(fix|debug|refactor|optimize|test|deploy|setup|configure)\b.*\b(code|bug|error|issue|performance|ci|cd)\b",
    r"\b(add|update|delete|remove|change|modify)\b.*\b(feature|function|route|endpoint|component|style|test)\b",
    r"\b(run|start|stop|restart|build|compile|transpile|bundle)\b.*\b(server|dev|prod|app|project)\b",
    r"\b(git|github|commit|push|pull|merge|branch|rebase|checkout)\b",
    r"\b(npm|yarn|pnpm|bun|pip|poetry)\b.*\b(install|uninstall|update|outdated|audit)\b",
    r"\b(docker|compose|kubernetes|k8s|terraform)\b",
    r"\b(cursor|windsurf|vscode|lovable|warp)\b.*\b(open|focus|prompt|stage|build)\b",
    r"\b(open|navigate to|go to)\b.*\b(localhost|github|vercel|netlify|supabase)\b",
    r"\b(screenshot|analyze|verify|check|test)\b.*\b(ui|page|screen|component|layout)\b",
]

_COMPILED_ALLOWED = [re.compile(p, re.IGNORECASE) for p in _ALLOWED_CODE_PATTERNS]


# =============================================================
#  INTENT CLASSIFIER
# =============================================================

def classify_intent(text: str) -> Tuple[str, float, Optional[str]]:
    """
    Classify user intent. Returns (classification, confidence, reason).

    classification: "allowed" | "blocked" | "uncertain"
    confidence: 0.0–1.0
    reason: explanation string (None if allowed with high confidence)
    """
    if not text or not text.strip():
        return "blocked", 1.0, "empty_request"

    lower = text.lower().strip()

    # --- Fast path: explicit allowed code patterns ---
    for pattern in _COMPILED_ALLOWED:
        if pattern.search(lower):
            return "allowed", 0.95, None

    # --- Fast path: explicit blocked patterns ---
    for pattern in _COMPILED_BLOCKED:
        if pattern.search(lower):
            # Check if an allowed prefix rescues it
            first_word = lower.split()[0] if lower.split() else ""
            if first_word in ALLOWED_PREFIXES:
                return "allowed", 0.7, None
            return "blocked", 0.95, f"blocked_pattern:{pattern.pattern[:40]}"

    # --- Token-based scoring ---
    tokens = set(re.findall(r"\b[a-z]+\b", lower))

    allowed_hits = tokens & ALLOWED_TOPICS
    blocked_hits = tokens & BLOCKED_TOPICS

    if blocked_hits and not allowed_hits:
        return "blocked", 0.85, f"blocked_topic:{next(iter(blocked_hits))}"

    if allowed_hits and not blocked_hits:
        return "allowed", 0.85, None

    if allowed_hits and blocked_hits:
        # Mixed signals — check prefix rescue
        first_word = lower.split()[0] if lower.split() else ""
        if first_word in ALLOWED_PREFIXES:
            return "allowed", 0.7, None
        # If more allowed than blocked, allow with lower confidence
        if len(allowed_hits) > len(blocked_hits):
            return "allowed", 0.6, None
        return "blocked", 0.6, f"ambiguous_topic:{next(iter(blocked_hits))}"

    # --- Uncertain: no clear signal ---
    return "uncertain", 0.5, "no_clear_signal"


# =============================================================
#  GATE ENTRY POINT
# =============================================================

def gate_check(text: str, use_llm_fallback: bool = True) -> Tuple[bool, str, float]:
    """
    Main entry point. Returns (permitted, reason, confidence).

    If the fast classifier is uncertain and use_llm_fallback is True,
    a lightweight LLM call is made for final classification.
    """
    classification, confidence, reason = classify_intent(text)

    if classification == "allowed":
        return True, "", confidence

    if classification == "blocked":
        return False, _rejection_message(reason or "off_topic"), confidence

    # Uncertain — try LLM fallback if enabled
    if use_llm_fallback and classification == "uncertain":
        llm_result = _llm_fallback_check(text)
        return llm_result

    # Uncertain without fallback — block to be safe
    return False, _rejection_message("uncertain_intent"), confidence


def _rejection_message(reason: str) -> str:
    """Return a canned rejection message."""
    base = (
        "I am Wiztant, your IDE Controller Agent. I help you build, debug, "
        "and ship software. I cannot answer questions about that. "
        "Try asking about your code or project instead."
    )
    # Specific messages for common cases
    specifics = {
        "off_topic": base,
        "empty_request": "I didn't catch that. Try describing what you'd like to build or fix.",
        "uncertain_intent": (
            "I'm not sure how that relates to building software. "
            "Could you rephrase as a development task?"
        ),
        "blocked_topic:weather": (
            "I don't check the weather — I'm your IDE Controller Agent. "
            "Ask me about your code instead!"
        ),
        "blocked_topic:joke": (
            "I don't tell jokes — I'm your IDE Controller Agent. "
            "Ask me about your code instead!"
        ),
    }
    return specifics.get(reason, base)


def _llm_fallback_check(text: str) -> Tuple[bool, str, float]:
    """
    Lightweight LLM fallback for borderline cases.
    Uses a single fast call (Qwen 3.5 Flash or Gemini Flash) for classification.
    Returns (permitted, reason, confidence).
    """
    try:
        from core.credit_system import can_afford, deduct, get_current_user_id
        from core.agent_engine import parse_json
        import os

        user_id = get_current_user_id()
        # Cost: 1 credit for borderline classification
        if not can_afford(user_id, 1):
            # Can't afford fallback — block to be safe
            return False, _rejection_message("uncertain_intent"), 0.5

        from core.agent_engine import get_openrouter_client
        client = get_openrouter_client()
        if not client:
            return False, _rejection_message("uncertain_intent"), 0.5

        system_msg = (
            "You are an intent classifier for Wiztant, an IDE Controller Agent. "
            "Your job is to decide if a user request is about SOFTWARE DEVELOPMENT.\n\n"
            "ALLOWED topics: coding, building apps, debugging, testing, deploying, "
            "configuring dev tools, IDE operations, database schemas, UI design, "
            "API development, auth systems, CI/CD, devops, code review.\n\n"
            "BLOCKED topics: weather, news, sports, politics, trivia, jokes, poems, "
            "stories, recipes, horoscopes, dating, medical, legal, financial advice, "
            "gaming (unless about game development), general chat, homework help, "
            "personal life advice, shopping, travel, music/movies/TV (unless about media apps).\n\n"
            "Respond ONLY with JSON: {\"allowed\": true/false, \"reason\": \"...\"}"
        )

        response = client.chat.completions.create(
            model=os.getenv("PLANNER_MODEL", "google/gemini-3-flash-preview"),
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f'Classify this request: "{text}"'},
            ],
            temperature=0.0,
            max_tokens=100,
        )

        content = response.choices[0].message.content
        result = parse_json(content)

        if isinstance(result, dict) and "allowed" in result:
            allowed = bool(result["allowed"])
            reason = result.get("reason", "")
            if allowed:
                deduct(user_id, "intent_gate_allowed", 1)
                return True, "", 0.8
            else:
                deduct(user_id, "intent_gate_blocked", 1)
                return False, _rejection_message("off_topic"), 0.8

    except Exception as e:
        # LLM fallback failed — block to be safe
        print(f"[IntentGate] LLM fallback failed: {e}")

    return False, _rejection_message("uncertain_intent"), 0.5
