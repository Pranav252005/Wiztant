"""
core/agent_v2/ui_analyzer.py — Screenshot-based UI analysis engine.

Sends screenshots to a vision model to detect layout issues, spacing
problems, color inconsistencies, typography hierarchy issues, and more.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image


def _encode_screenshot(img: Image.Image) -> str:
    """Encode a PIL Image to base64 JPEG."""
    import io
    import base64
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=82)
    return base64.b64encode(buf.getvalue()).decode()


def _get_vision_client():
    """Lazy-load OpenRouter client for vision calls."""
    from openai import OpenAI
    return OpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY", ""),
        base_url="https://openrouter.ai/api/v1",
        default_headers={"HTTP-Referer": "https://whiztant.com", "X-Title": "Wiztant"},
    )


def _build_analysis_prompt() -> str:
    return (
        "You are a senior UI/UX engineer reviewing a web application screenshot. "
        "Analyze the screenshot for the following categories:\n\n"
        "1. **Layout** — alignment, grid consistency, overflow, element overlap\n"
        "2. **Spacing** — padding, margin, gap consistency, cramped or excessive whitespace\n"
        "3. **Color** — palette consistency, contrast (WCAG), stray colors, dark mode issues\n"
        "4. **Typography** — hierarchy, font sizes, line height, readability, inconsistent fonts\n"
        "5. **Accessibility** — missing labels, low contrast, tiny click targets, focus indicators\n"
        "6. **Responsive** — horizontal scroll, clipped content, breakpoint issues\n"
        "7. **Interactions** — button states, hover feedback, loading states, broken links\n\n"
        "Respond ONLY with valid JSON in this exact schema:\n"
        "{\n"
        '  "issues": [\n'
        '    {\n'
        '      "severity": "critical|warning|suggestion",\n'
        '      "category": "layout|spacing|color|typography|a11y|responsive|interaction",\n'
        '      "description": "specific issue description",\n'
        '      "element_location": "rough area e.g. top-left navbar",\n'
        '      "suggested_fix": "concrete fix instruction"\n'
        '    }\n'
        '  ],\n'
        '  "overall_score": 0-100,\n'
        '  "style_consistency": "consistent|inconsistent|partially_consistent",\n'
        '  "recommendations": ["top-level actionable recommendation"]\n'
        "}\n\n"
        "Be strict. A production-ready UI should score 85+. "
        "Flag anything that would make a user think the app is unfinished."
    )


async def analyze_ui(
    screenshot: Image.Image,
    project_context: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], str]:
    """
    Analyze a UI screenshot. Returns (analysis_dict, status).
    status: "ok" | "parse_error" | "model_error"
    """
    try:
        client = _get_vision_client()
        b64_image = _encode_screenshot(screenshot)

        model = os.getenv("AGENT_OMNI_MODEL", "google/gemini-3-flash-preview")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _build_analysis_prompt()},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                    },
                ],
            }
        ]

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.1,
            max_tokens=1500,
        )

        content = response.choices[0].message.content or ""

        # Extract JSON from response
        import re
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(0))
                return result, "ok"
            except json.JSONDecodeError:
                pass

        # Fallback: try to parse the entire content
        try:
            result = json.loads(content)
            return result, "ok"
        except json.JSONDecodeError:
            return {
                "issues": [],
                "overall_score": 50,
                "style_consistency": "unknown",
                "recommendations": ["Could not parse analysis result"],
                "_raw_response": content[:500],
            }, "parse_error"

    except Exception as e:
        return {
            "issues": [],
            "overall_score": 50,
            "style_consistency": "unknown",
            "recommendations": [f"Analysis failed: {e}"],
        }, "model_error"


def filter_critical_issues(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return only critical and warning issues."""
    issues = analysis.get("issues", [])
    return [i for i in issues if i.get("severity") in ("critical", "warning")]


def score_passes(analysis: Dict[str, Any], threshold: int = 80) -> bool:
    """Check if the UI score meets the threshold."""
    score = analysis.get("overall_score", 0)
    return score >= threshold
