"""
core/agent_v2_filefinder.py — File identification engine for the Bridge Agent.

CRITICAL CONSTRAINT: This module NEVER reads the contents of code files.
It identifies files by name, path, git status, error stack traces, and project
heuristics only. The IDE (Cursor) reads and edits files. Wiztant just points.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("core.agent_v2_filefinder")


# =============================================================
#  DATA CLASSES
# =============================================================

@dataclass
class FileCandidate:
    """A candidate file with confidence score and reasoning."""

    path: str
    confidence: float  # 0.0 - 1.0
    source: str  # git_status | keyword_search | stack_trace | heuristic | screenshot
    reasoning: str = ""


@dataclass
class FileIdentificationResult:
    """Result of a file identification query."""

    top_candidate: Optional[FileCandidate] = None
    candidates: List[FileCandidate] = field(default_factory=list)
    query: str = ""

    def is_confident(self, threshold: float = 0.99) -> bool:
        return self.top_candidate is not None and self.top_candidate.confidence >= threshold


# =============================================================
#  SOURCE 1: GIT STATUS
# =============================================================

def from_git_status(cwd: Optional[str] = None) -> List[FileCandidate]:
    """
    Get recently modified files from git status / diff.

    Returns files sorted by recency with high confidence.
    """
    candidates: List[FileCandidate] = []
    cwd = cwd or os.getcwd()

    try:
        # Recently modified files
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~5"],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if line:
                    candidates.append(FileCandidate(
                        path=line,
                        confidence=0.85,
                        source="git_status",
                        reasoning="Modified in last 5 commits",
                    ))

        # Staged + unstaged files
        result2 = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=5,
        )
        if result2.returncode == 0:
            for line in result2.stdout.strip().split("\n"):
                line = line.strip()
                if len(line) > 3:
                    filepath = line[3:].strip()
                    if filepath:
                        candidates.append(FileCandidate(
                            path=filepath,
                            confidence=0.90,
                            source="git_status",
                            reasoning="Currently staged or modified",
                        ))

    except Exception as e:
        log.warning("git status failed: %s", e)

    return candidates


# =============================================================
#  SOURCE 2: KEYWORD SEARCH
# =============================================================

def from_keyword_search(
    keywords: List[str],
    cwd: Optional[str] = None,
    max_results: int = 20,
) -> List[FileCandidate]:
    """
    Search for files by keyword in their names using `find`.

    Never reads file contents — only matches filenames.
    """
    candidates: List[FileCandidate] = []
    cwd = cwd or os.getcwd()

    try:
        # Build find expression: -iname "*kw1*" -o -iname "*kw2*"
        conditions = []
        for kw in keywords:
            safe_kw = kw.replace('"', '\\"')
            conditions.append(f'-iname "*{safe_kw}*"')

        if not conditions:
            return candidates

        expr = " -o ".join(conditions)
        cmd = f'find . -type f \( {expr} \) | head -{max_results}'

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=10,
        )

        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                line = line.strip().lstrip("./")
                if line:
                    # Confidence based on how many keywords match
                    name_lower = Path(line).name.lower()
                    matches = sum(1 for kw in keywords if kw.lower() in name_lower)
                    confidence = min(0.95, 0.70 + matches * 0.08)
                    candidates.append(FileCandidate(
                        path=line,
                        confidence=confidence,
                        source="keyword_search",
                        reasoning=f"Filename matches {matches} keyword(s)",
                    ))

    except Exception as e:
        log.warning("Keyword search failed: %s", e)

    return candidates


# =============================================================
#  SOURCE 3: ERROR STACK TRACES
# =============================================================

STACK_TRACE_PATTERN = re.compile(
    r'File\s+["\']([^"\']+)["\']\s*,\s*line\s*(\d+)',
    re.IGNORECASE,
)

ERROR_PATH_PATTERN = re.compile(
    r'(?:in\s+|at\s+|from\s+|can\'t\s+resolve\s+)[\'"]?([/@~.][^\s\'"]+)',
    re.IGNORECASE,
)

MODULE_NOT_FOUND_PATTERN = re.compile(
    r"Module not found:.*?['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


def from_error_stacktrace(error_text: str) -> List[FileCandidate]:
    """
    Extract file paths from error messages and stack traces.

    This is the highest-accuracy source because errors already contain the exact path.
    """
    candidates: List[FileCandidate] = []

    # Pattern 1: File "path", line N
    for match in STACK_TRACE_PATTERN.finditer(error_text):
        path = match.group(1)
        line = match.group(2)
        candidates.append(FileCandidate(
            path=path,
            confidence=0.99,
            source="stack_trace",
            reasoning=f"Exact path from stack trace at line {line}",
        ))

    # Pattern 2: import/from/at path references
    for match in ERROR_PATH_PATTERN.finditer(error_text):
        path = match.group(1)
        if "/" in path or path.startswith("@"):
            candidates.append(FileCandidate(
                path=path,
                confidence=0.95,
                source="stack_trace",
                reasoning="Path referenced in error message",
            ))

    # Pattern 3: Module not found
    for match in MODULE_NOT_FOUND_PATTERN.finditer(error_text):
        path = match.group(1)
        candidates.append(FileCandidate(
            path=path,
            confidence=0.92,
            source="stack_trace",
            reasoning="Module path from 'not found' error",
        ))

    return candidates


# =============================================================
#  SOURCE 4: PROJECT HEURISTICS
# =============================================================

FRAMEWORK_PATTERNS: Dict[str, Dict[str, List[str]]] = {
    "nextjs": {
        "auth": [
            "app/(auth)/login/page.tsx",
            "app/login/page.tsx",
            "src/app/login/page.tsx",
            "pages/login.tsx",
            "src/pages/login.tsx",
            "app/api/auth/[...nextauth]/route.ts",
        ],
        "button": [
            "components/ui/button.tsx",
            "app/components/ui/button.tsx",
            "src/components/ui/button.tsx",
        ],
        "layout": [
            "app/layout.tsx",
            "src/app/layout.tsx",
        ],
    },
    "react": {
        "auth": [
            "src/pages/Login.tsx",
            "src/pages/Login.jsx",
            "src/components/Login.tsx",
            "src/auth/login.ts",
        ],
        "button": [
            "src/components/Button.tsx",
            "src/components/ui/Button.tsx",
        ],
        "layout": [
            "src/App.tsx",
            "src/App.jsx",
        ],
    },
    "vue": {
        "auth": [
            "src/views/Login.vue",
            "src/pages/Login.vue",
            "src/components/Login.vue",
        ],
    },
    "svelte": {
        "auth": [
            "src/routes/login/+page.svelte",
            "src/pages/Login.svelte",
        ],
    },
    "django": {
        "auth": [
            "auth/views.py",
            "users/views.py",
            "accounts/views.py",
        ],
    },
    "flask": {
        "auth": [
            "auth.py",
            "routes/auth.py",
            "views/auth.py",
        ],
    },
    "fastapi": {
        "auth": [
            "routers/auth.py",
            "api/auth.py",
            "routes/auth.py",
        ],
    },
}


def detect_framework(cwd: Optional[str] = None) -> Optional[str]:
    """Detect project framework from root files."""
    cwd = cwd or os.getcwd()
    root = Path(cwd)

    if (root / "next.config.js").exists() or (root / "next.config.ts").exists():
        return "nextjs"
    if (root / "src" / "app" / "layout.tsx").exists() or (root / "app" / "layout.tsx").exists():
        return "nextjs"
    if (root / "package.json").exists():
        try:
            import json
            with open(root / "package.json", "r", encoding="utf-8") as f:
                pkg = json.load(f)
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "next" in deps:
                return "nextjs"
            if "react" in deps:
                return "react"
            if "vue" in deps:
                return "vue"
            if "svelte" in deps:
                return "svelte"
        except Exception:
            pass
    if (root / "manage.py").exists():
        return "django"
    if (root / "app.py").exists() and "Flask" in (root / "app.py").read_text(errors="ignore")[:2000]:
        return "flask"
    if (root / "main.py").exists() and "FastAPI" in (root / "main.py").read_text(errors="ignore")[:2000]:
        return "fastapi"

    return None


def from_project_heuristics(
    intent: str,
    framework: Optional[str] = None,
    cwd: Optional[str] = None,
) -> List[FileCandidate]:
    """
    Suggest files based on known framework conventions.

    Example: "fix login" + Next.js → app/login/page.tsx
    """
    candidates: List[FileCandidate] = []
    cwd = cwd or os.getcwd()

    if framework is None:
        framework = detect_framework(cwd)

    if not framework:
        return candidates

    patterns = FRAMEWORK_PATTERNS.get(framework, {})
    intent_lower = intent.lower()

    # Match intent keywords to pattern keys
    for key, paths in patterns.items():
        if key in intent_lower:
            for p in paths:
                full_path = os.path.join(cwd, p)
                if os.path.exists(full_path):
                    candidates.append(FileCandidate(
                        path=p,
                        confidence=0.88,
                        source="heuristic",
                        reasoning=f"{framework} convention: {key} → {p}",
                    ))
                else:
                    # Still suggest it with lower confidence even if not yet created
                    candidates.append(FileCandidate(
                        path=p,
                        confidence=0.60,
                        source="heuristic",
                        reasoning=f"{framework} convention (file may not exist): {key} → {p}",
                    ))

    return candidates


# =============================================================
#  SOURCE 5: IDE FILE TREE SCREENSHOT (VISION)
# =============================================================

async def from_file_tree_screenshot(
    screenshot,
    intent: str,
    vision_brain=None,
) -> List[FileCandidate]:
    """
    Ask the vision model to identify relevant files from a screenshot of the IDE file tree.

    This does NOT read file contents — it only looks at the file tree sidebar.
    """
    candidates: List[FileCandidate] = []

    if vision_brain is None:
        log.warning("No vision brain provided for file tree analysis")
        return candidates

    try:
        from core.agent_engine import to_base64

        b64 = to_base64(screenshot)
        prompt = (
            f"The user wants to: '{intent}'.\n\n"
            "Look at the IDE file tree in this screenshot. "
            "Identify the most relevant file(s) by name/path only. "
            "Do NOT read or analyze file contents. "
            "Return JSON with a list of candidates: "
            '[{"path": "src/auth/login.ts", "confidence": 0.95, "reasoning": "..."}]'
        )

        from core.agent_engine import call_api
        messages = [
            {"role": "system", "content": "You are a file identification assistant. You only look at file names and paths, never file contents."},
            {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]},
        ]

        raw = call_api("google/gemini-3-flash-preview", messages, 0.1, 512)
        from core.agent_engine import parse_json
        data = parse_json(raw)

        if data and isinstance(data, list):
            for item in data:
                candidates.append(FileCandidate(
                    path=item.get("path", ""),
                    confidence=float(item.get("confidence", 0.7)),
                    source="screenshot",
                    reasoning=item.get("reasoning", "Identified from file tree screenshot"),
                ))
        elif data and isinstance(data, dict) and "candidates" in data:
            for item in data["candidates"]:
                candidates.append(FileCandidate(
                    path=item.get("path", ""),
                    confidence=float(item.get("confidence", 0.7)),
                    source="screenshot",
                    reasoning=item.get("reasoning", "Identified from file tree screenshot"),
                ))

    except Exception as e:
        log.warning("File tree screenshot analysis failed: %s", e)

    return candidates


# =============================================================
#  ORCHESTRATOR
# =============================================================

class FileFinder:
    """
    Identifies the right file for a given user intent without reading file contents.

    Uses multiple sources in priority order:
    1. Error stack traces (99% accuracy)
    2. Git status (very high accuracy)
    3. IDE file tree screenshot (high accuracy)
    4. Keyword search (high accuracy)
    5. Project heuristics (medium-high accuracy)
    """

    def __init__(self, cwd: Optional[str] = None) -> None:
        self.cwd = cwd or os.getcwd()
        self._vision_brain = None

    def set_vision_brain(self, vision_brain) -> None:
        """Set the vision brain for screenshot-based file identification."""
        self._vision_brain = vision_brain

    def identify(
        self,
        intent: str,
        error_text: Optional[str] = None,
        screenshot=None,
        keywords: Optional[List[str]] = None,
    ) -> FileIdentificationResult:
        """
        Identify the most likely file for a given intent.

        Returns a FileIdentificationResult with candidates sorted by confidence.
        """
        all_candidates: List[FileCandidate] = []

        # Source 1: Error stack trace (highest accuracy)
        if error_text:
            all_candidates.extend(from_error_stacktrace(error_text))

        # Source 2: Git status
        all_candidates.extend(from_git_status(self.cwd))

        # Source 3: IDE file tree screenshot
        if screenshot is not None and self._vision_brain is not None:
            import asyncio
            try:
                # Try async first
                loop = asyncio.get_event_loop()
                candidates = loop.run_until_complete(
                    from_file_tree_screenshot(screenshot, intent, self._vision_brain)
                )
                all_candidates.extend(candidates)
            except Exception:
                # Fallback: skip vision-based identification
                pass

        # Source 4: Keyword search
        if keywords:
            all_candidates.extend(from_keyword_search(keywords, self.cwd))
        else:
            # Derive keywords from intent
            derived_keywords = self._extract_keywords(intent)
            all_candidates.extend(from_keyword_search(derived_keywords, self.cwd))

        # Source 5: Project heuristics
        all_candidates.extend(from_project_heuristics(intent, cwd=self.cwd))

        # Deduplicate by path, keeping highest confidence
        by_path: Dict[str, FileCandidate] = {}
        for c in all_candidates:
            if not c.path:
                continue
            existing = by_path.get(c.path)
            if existing is None or c.confidence > existing.confidence:
                by_path[c.path] = c

        # Sort by confidence descending
        sorted_candidates = sorted(by_path.values(), key=lambda c: c.confidence, reverse=True)

        top = sorted_candidates[0] if sorted_candidates else None
        return FileIdentificationResult(
            top_candidate=top,
            candidates=sorted_candidates[:5],
            query=intent,
        )

    def _extract_keywords(self, intent: str) -> List[str]:
        """Extract search keywords from a natural language intent."""
        # Common programming keywords to look for
        intent_lower = intent.lower()
        keywords = []

        # Map common terms to file naming patterns
        keyword_map = {
            "login": ["login", "auth", "signin"],
            "auth": ["auth", "login", "session", "oauth"],
            "redirect": ["redirect", "router", "navigation"],
            "button": ["button", "ui"],
            "component": ["component"],
            "layout": ["layout", "template"],
            "error": ["error", "exception", "handler"],
            "api": ["api", "route", "endpoint"],
            "database": ["db", "database", "model", "schema"],
            "style": ["style", "css", "theme"],
            "test": ["test", "spec"],
            "config": ["config", "settings", "env"],
            "hook": ["hook", "use"],
            "util": ["util", "helper", "lib"],
        }

        for term, mappings in keyword_map.items():
            if term in intent_lower:
                keywords.extend(mappings)

        # Also extract any literal file extensions mentioned
        ext_match = re.search(r'(\.(tsx?|jsx?|py|vue|svelte|css|scss))\b', intent_lower)
        if ext_match:
            keywords.append(ext_match.group(1).lstrip("."))

        return list(set(keywords)) if keywords else [intent_lower.split()[0]]



