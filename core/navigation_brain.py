import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_NAV_PATHS = {
    "agent": _PROJECT_ROOT / "agent_rules" / "agent_navigation.md",
    "browser": _PROJECT_ROOT / "agent_rules" / "browser_navigation_spec.md",
    "browser_apps": _PROJECT_ROOT / "agent_rules" / "apps_browsers.md",
    "microsoft_apps": _PROJECT_ROOT / "agent_rules" / "apps_microsoft.md",
    "creative_apps": _PROJECT_ROOT / "agent_rules" / "apps_creative.md",
    "optimize": _PROJECT_ROOT / "agent_rules" / "agent_universal_optimize.md",
}

_cached_docs = None
_cached_candidates = None
_cached_general_brain = None


def _read_nav_docs() -> dict[str, str]:
    global _cached_docs
    if _cached_docs is not None:
        return _cached_docs
    docs: dict[str, str] = {}
    for key, path in _NAV_PATHS.items():
        if path.exists():
            docs[key] = path.read_text(encoding="utf-8", errors="replace")
        else:
            docs[key] = ""
    _cached_docs = docs
    return _cached_docs


def _tokenize(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9_+.-]+", text.lower()) if len(token) > 1}


def _normalize_line(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _build_candidates() -> list[dict[str, str]]:
    global _cached_candidates
    if _cached_candidates is not None:
        return _cached_candidates
    candidates: list[dict[str, str]] = []
    for source, text in _read_nav_docs().items():
        current_h2 = ""
        current_h3 = ""
        in_code_block = False
        for raw_line in text.splitlines():
            stripped = raw_line.strip()
            if not stripped:
                continue
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if stripped.startswith("## "):
                current_h2 = stripped[3:].strip()
                current_h3 = ""
                continue
            if stripped.startswith("### "):
                current_h3 = stripped[4:].strip()
                continue
            if stripped.startswith("#"):
                continue
            is_candidate = (
                stripped.startswith("|")
                or stripped.startswith("-")
                or stripped.startswith("*")
                or bool(re.match(r"^\d+[.)]\s", stripped))
                or (in_code_block and len(stripped) <= 140)
                or "Ctrl+" in stripped
                or "Alt+" in stripped
                or "Shift+" in stripped
                or stripped.startswith("Option ")
            )
            if not is_candidate:
                continue
            normalized = _normalize_line(stripped)
            if normalized in {"|---|---|", "|--------|----------|", "---"}:
                continue
            candidates.append({
                "source": source,
                "section": current_h2,
                "subsection": current_h3,
                "line": normalized,
            })
    _cached_candidates = candidates
    return _cached_candidates


def _fallback_brain() -> str:
    return "\n".join([
        "NAVIGATION BRAIN:",
        "- Prefer keyboard over mouse.",
        "- Prefer direct app launch or search over menu navigation.",
        "- Prefer clipboard paste over character typing for longer text.",
        "- Focus target window before paste or type.",
        "- Browser fast path: ctrl+l address bar, ctrl+t new tab, ctrl+w close tab.",
        "- Editor fast path: ctrl+p quick open, ctrl+shift+p palette, ctrl+` terminal.",
        "- Universal: alt+tab switch, alt+f4 close, enter confirm, esc cancel.",
        "- Avoid waits unless UI is visibly loading.",
    ])


def _score_candidate(candidate: dict[str, str], task_tokens: set[str]) -> int:
    haystack = " ".join([
        candidate["source"],
        candidate["section"],
        candidate["subsection"],
        candidate["line"],
    ]).lower()
    score = 0
    overlap = [token for token in task_tokens if token in haystack]
    score += len(overlap) * 4
    if candidate["source"] == "browser" and task_tokens.intersection({"browser", "chrome", "edge", "firefox", "brave", "opera", "vivaldi", "arc", "tab", "url", "search", "page", "website"}):
        score += 6
    if candidate["source"] == "optimize" and task_tokens.intersection({"optimize", "performance", "fps", "lag", "gpu", "nvidia", "amd", "intel", "registry", "settings", "config", "boost", "tweak", "game", "latency", "ram", "cpu", "overclock", "thermal", "power"}):
        score += 6
    if "ctrl+" in candidate["line"].lower() or "alt+" in candidate["line"].lower() or "f12" in candidate["line"].lower():
        score += 2
    if candidate["line"].lower().startswith(("1.", "2.", "3.", "option ")):
        score += 1
    if any(term in haystack for term in ["agent notes", "recommended agent action sequence", "universal principles", "decision tree"]):
        score += 3
    return score


def _format_candidate(candidate: dict[str, str]) -> str:
    section_bits = [bit for bit in [candidate["section"], candidate["subsection"]] if bit]
    if section_bits:
        return f"- [{candidate['source']} | {' > '.join(section_bits)}] {candidate['line']}"
    return f"- [{candidate['source']}] {candidate['line']}"


def _priority_needles(task_tokens: set[str]) -> list[str]:
    needles: list[str] = []
    if task_tokens.intersection({"browser", "chrome", "edge", "firefox", "brave", "opera", "vivaldi", "arc", "website", "url", "search", "page"}):
        needles.extend(["ctrl+l", "address bar", "omnibox"])
    if task_tokens.intersection({"tab", "tabs", "new"}):
        needles.extend(["ctrl+t", "new tab", "ctrl+shift+t", "ctrl+w"])
    if task_tokens.intersection({"devtools", "console", "inspect", "debug"}):
        needles.extend(["f12", "ctrl+shift+j", "devtools"])
    if task_tokens.intersection({"back", "forward", "reload", "refresh"}):
        needles.extend(["alt+left", "alt+right", "ctrl+r", "f5"])
    if task_tokens.intersection({"find", "search_page", "page_text"}):
        needles.extend(["ctrl+f", "find on page"])
    if task_tokens.intersection({"optimize", "performance", "fps", "gpu", "nvidia", "amd", "registry", "settings", "game", "boost", "tweak", "config", "power", "thermal"}):
        needles.extend(["nvidia control panel", "amd adrenalin", "regedit", "power plan", "game mode", "config file", "youtube", "research"])
    return needles


def build_navigation_brain(task: str = "") -> str:
    global _cached_general_brain
    if not any(_read_nav_docs().values()):
        return _fallback_brain()
    if not task.strip() and _cached_general_brain is not None:
        return _cached_general_brain
    task_tokens = _tokenize(task)
    compact = [
        "NAVIGATION BRAIN:",
        "- Learned from agent_navigation.md, browser_navigation_spec.md, apps_browsers.md, apps_microsoft.md, apps_creative.md, and agent_universal_optimize.md for this session.",
        "- Search all guides for the current task and prefer the fastest matching shortcut or optimization path.",
        "- Prefer keyboard shortcuts over mouse clicks.",
        "- Prefer direct launch, address-bar navigation, and tab shortcuts before visual clicking.",
        "- Prefer clipboard paste over slow keystroke typing when entering text.",
        "- Focus the right surface first, then type or paste, then confirm with Enter.",
        "- Use visual grounding only when no reliable shortcut path exists.",
        "- Avoid waits unless UI is visibly loading or navigation requires verification.",
    ]
    candidates = _build_candidates()
    if task_tokens:
        selected: list[str] = []
        seen = set()
        priority_needles = _priority_needles(task_tokens)
        for needle in priority_needles:
            for candidate in candidates:
                lowered = candidate["line"].lower()
                if needle not in lowered:
                    continue
                key = candidate["line"].lower()
                if key in seen:
                    continue
                seen.add(key)
                selected.append(_format_candidate(candidate))
                break
        ranked = sorted(candidates, key=lambda item: (_score_candidate(item, task_tokens), -len(item["line"])), reverse=True)
        for candidate in ranked:
            score = _score_candidate(candidate, task_tokens)
            if score <= 0:
                continue
            formatted = _format_candidate(candidate)
            key = candidate["line"].lower()
            if key in seen:
                continue
            seen.add(key)
            selected.append(formatted)
            if len(selected) >= 22:
                break
        if selected:
            compact.append(f"- Task focus: {task.strip()}")
            compact.append("- Retrieved relevant rules:")
            compact.extend(selected)
    if len(compact) <= 9:
        fallback_lines = []
        seen = set()
        for candidate in candidates:
            lowered = candidate["line"].lower()
            if lowered in seen:
                continue
            if any(term in lowered for term in ["ctrl+l", "ctrl+t", "ctrl+w", "ctrl+p", "ctrl+shift+p", "alt+tab", "alt+f4", "clipboard paste"]):
                seen.add(lowered)
                fallback_lines.append(_format_candidate(candidate))
            if len(fallback_lines) >= 10:
                break
        if fallback_lines:
            compact.append("- Core retrieved rules:")
            compact.extend(fallback_lines)
    brain = "\n".join(compact)
    if len(brain) > 4200:
        brain = brain[:4200].rsplit("\n", 1)[0]
    if not task.strip():
        _cached_general_brain = brain
    return brain


def get_navigation_brain(task: str = "") -> str:
    return build_navigation_brain(task)
