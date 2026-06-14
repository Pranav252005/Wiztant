"""
core/tune_hub/browser_agent.py — Playwright-based background research agent.

Spawns a headless browser to search authoritative sources, extract content,
and convert unstructured documentation into executable workflow steps.

Playwright is optional — falls back to requests + BeautifulSoup if unavailable.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlparse

log = logging.getLogger("core.tune_hub.browser_agent")

# =============================================================
#  DATA CLASSES
# =============================================================

@dataclass
class KnowledgeChunk:
    """A piece of knowledge extracted from a web source."""

    source: str
    title: str
    content: str
    authority_score: float = 0.0


@dataclass
class LearnedWorkflow:
    """Result of a learning session — a new workflow template."""

    template_id: str
    name: str
    description: str
    apps_required: List[str] = field(default_factory=list)
    estimated_steps: int = 0
    estimated_budget: int = 0
    steps: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    sources: List[str] = field(default_factory=list)
    query: str = ""
    risk_flags: List[str] = field(default_factory=list)
    persona_weights: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "apps_required": self.apps_required,
            "estimated_steps": self.estimated_steps,
            "estimated_budget": self.estimated_budget,
            "steps": self.steps,
            "confidence": self.confidence,
            "sources": self.sources,
            "query": self.query,
            "risk_flags": self.risk_flags,
            "persona_weights": self.persona_weights,
        }


# =============================================================
#  BROWSER AGENT
# =============================================================

class TuneHubBrowserAgent:
    """
    Headless browser agent for researching workflows from web sources.

    Uses Playwright when available, falls back to requests + BeautifulSoup.
    """

    def __init__(self) -> None:
        self._playwright_available = self._check_playwright()
        self._browser = None
        self._context = None
        self._page = None
        self._pw = None

    def _check_playwright(self) -> bool:
        try:
            import playwright  # noqa: F401
            return True
        except ImportError:
            log.warning("Playwright not installed. Using requests fallback.")
            return False

    async def launch(self) -> bool:
        """Launch the browser. Returns True if ready."""
        if not self._playwright_available:
            return False
        try:
            from playwright.async_api import async_playwright
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(headless=True)
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Wiztant-Learning-Agent/1.0",
            )
            self._page = await self._context.new_page()
            log.info("Playwright browser launched")
            return True
        except Exception as e:
            log.error("Failed to launch Playwright: %s", e)
            self._playwright_available = False
            return False

    async def close(self) -> None:
        """Close browser and cleanup."""
        try:
            if self._context:
                await self._context.close()
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception as e:
            log.warning("Browser cleanup error: %s", e)
        finally:
            self._page = None
            self._context = None
            self._browser = None
            self._pw = None

    async def research(self, query: str, intent: str) -> LearnedWorkflow:
        """
        Research a workflow from web sources.

        Returns a LearnedWorkflow with extracted steps.
        """
        await self.launch()
        try:
            # Step 1: Search
            search_results = await self._search(query)
            log.info("Search returned %d results", len(search_results))

            # Step 2: Visit authoritative sources
            chunks: List[KnowledgeChunk] = []
            for result in search_results[:3]:
                try:
                    content = await self._extract_page_content(result["url"])
                    if content and len(content) > 200:
                        score = self._authority_score(result["url"])
                        chunks.append(KnowledgeChunk(
                            source=result["url"],
                            title=result.get("title", ""),
                            content=content,
                            authority_score=score,
                        ))
                except Exception as e:
                    log.warning("Failed to extract %s: %s", result["url"], e)

            log.info("Extracted %d knowledge chunks", len(chunks))

            # Step 3: Generate workflow from knowledge
            workflow = await self._extract_workflow(chunks, intent, query)
            return workflow

        finally:
            await self.close()

    async def _search(self, query: str) -> List[Dict[str, str]]:
        """Search Google and return top results."""
        if self._page:
            return await self._search_playwright(query)
        return await self._search_requests(query)

    async def _search_playwright(self, query: str) -> List[Dict[str, str]]:
        """Search using Playwright."""
        if not self._page:
            return []
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        await self._page.goto(url)
        await self._page.wait_for_load_state("networkidle")

        links = await self._page.eval_on_selector_all(
            "a[href^='http']",
            """els => els.slice(0, 8).map(e => {
                const href = e.href;
                const text = e.innerText || e.textContent || '';
                return {title: text.trim().slice(0, 120), url: href};
            }).filter(r => r.title.length > 5 && !r.url.includes('google.com/search'))""",
        )
        return links

    async def _search_requests(self, query: str) -> List[Dict[str, str]]:
        """Search using requests + DuckDuckGo HTML (no API key needed)."""
        try:
            import requests
            from bs4 import BeautifulSoup

            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            headers = {"User-Agent": "Wiztant-Learning-Agent/1.0"}
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            for link in soup.select("a.result__a")[:5]:
                href = link.get("href", "")
                title = link.get_text(strip=True)
                if href and title:
                    results.append({"title": title[:120], "url": href})
            return results
        except Exception as e:
            log.warning("Requests search failed: %s", e)
            return []

    async def _extract_page_content(self, url: str) -> str:
        """Extract main textual content from a page."""
        if self._page:
            return await self._extract_playwright(url)
        return await self._extract_requests(url)

    async def _extract_playwright(self, url: str) -> str:
        """Extract content via Playwright."""
        if not self._page:
            return ""
        await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # Remove nav, footer, ads
        await self._page.evaluate("""
            () => {
                document.querySelectorAll('nav, footer, header, aside, .advertisement, .ads, [class*="cookie"]').forEach(e => e.remove());
            }
        """)
        # Get text from main or article or body
        text = await self._page.eval_on_selector(
            "main, article, [role='main'], body",
            "el => el.innerText.slice(0, 50000)",
        )
        return text or ""

    async def _extract_requests(self, url: str) -> str:
        """Extract content via requests + BeautifulSoup."""
        try:
            import requests
            from bs4 import BeautifulSoup

            headers = {"User-Agent": "Wiztant-Learning-Agent/1.0"}
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            # Remove noise
            for tag in soup.find_all(["nav", "footer", "header", "aside", "script", "style"]):
                tag.decompose()
            for tag in soup.find_all(class_=re.compile("ad|cookie|banner|sidebar", re.I)):
                tag.decompose()

            # Prefer main/article content
            main = soup.find("main") or soup.find("article") or soup.find(role="main") or soup.body
            if main:
                text = main.get_text(separator="\n", strip=True)
                return text[:50000]
            return soup.get_text(separator="\n", strip=True)[:50000]
        except Exception as e:
            log.warning("Requests extraction failed for %s: %s", url, e)
            return ""

    def _authority_score(self, url: str) -> float:
        """Score a URL's authority for trustworthiness."""
        domain = urlparse(url).netloc.lower()
        # High authority
        if any(d in domain for d in ["docs.", "support.", "developers.", "github.com", "stackoverflow.com"]):
            return 0.95
        if any(d in domain for d in ["vercel.com", "supabase.com", "aws.amazon.com", "cloud.google.com", "azure.microsoft.com"]):
            return 0.90
        if any(d in domain for d in ["medium.com", "dev.to", "digitalocean.com", "heroku.com"]):
            return 0.75
        if any(d in domain for d in ["npmjs.com", "pypi.org", "crates.io", "maven.apache.org"]):
            return 0.85
        # Low authority
        if any(d in domain for d in ["forum", "reddit.com", "quora.com"]):
            return 0.50
        return 0.60

    async def _extract_workflow(
        self,
        chunks: List[KnowledgeChunk],
        intent: str,
        query: str,
    ) -> LearnedWorkflow:
        """Use LLM to convert knowledge chunks into a structured workflow."""
        from core.agent_engine import call_api, parse_json

        if not chunks:
            return LearnedWorkflow(
                template_id=intent,
                name=intent.replace("_", " ").title(),
                description="Learning failed — no sources found",
                confidence=0.0,
                query=query,
            )

        # Build context from chunks, weighted by authority
        context_parts = []
        for chunk in sorted(chunks, key=lambda c: c.authority_score, reverse=True):
            context_parts.append(
                f"SOURCE: {chunk.title}\nURL: {chunk.source}\nAUTHORITY: {chunk.authority_score:.0%}\n{chunk.content[:8000]}\n---"
            )

        full_context = "\n".join(context_parts)

        prompt = f"""You are Wiztant's Learning Engine. You have just read web documentation about how to perform a task.

Your job: Convert this unstructured documentation into a STRICT, EXECUTABLE workflow template.

Rules:
1. Every step must specify: app (terminal/browser/cursor/figma/slack/notion/jira), action type (command/click/type/navigate/wait/open_url), and exact instruction
2. For terminal commands: write the EXACT command string with placeholders like {{repo_url}} or {{project_name}}
3. For browser actions: describe what to click and what to type
4. Include verification cues for each step: how do we know this step succeeded?
5. Flag any steps requiring user secrets (passwords, tokens, 2FA) in risk_flags
6. Estimate step budget cost (each command = 1, each browser interaction = 1-2). Total budget MUST NOT exceed 80.
7. Assign confidence score 0.0-1.0 based on source authority and clarity
8. The workflow must be practical and executable by a desktop automation agent

Output format (JSON only):
{{
  "name": "Human readable name",
  "description": "Brief description",
  "apps_required": ["terminal", "browser"],
  "estimated_steps": 8,
  "estimated_budget": 14,
  "steps": [
    {{
      "id": 1,
      "app": "terminal",
      "action": "command",
      "description": "Install Vercel CLI",
      "command": "npm i -g vercel",
      "verification": "vercel --version returns version number",
      "step_cost": 1,
      "requires_decision": false
    }}
  ],
  "risk_flags": ["requires_credentials"],
  "confidence": 0.87
}}

User intent: {intent}
Search query: {query}

Documentation content:
{full_context}
"""

        try:
            raw = call_api(
                model="qwen/qwen3-vl-235b-a22b-instruct",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=4096,
            )
            data = parse_json(raw)

            if not data:
                log.warning("LLM returned non-JSON workflow: %s", raw[:200])
                return self._fallback_workflow(intent, query, [c.source for c in chunks])

            return LearnedWorkflow(
                template_id=intent,
                name=data.get("name", intent.replace("_", " ").title()),
                description=data.get("description", ""),
                apps_required=data.get("apps_required", []),
                estimated_steps=data.get("estimated_steps", len(data.get("steps", []))),
                estimated_budget=data.get("estimated_budget", 20),
                steps=data.get("steps", []),
                confidence=float(data.get("confidence", 0.5)),
                sources=[c.source for c in chunks],
                query=query,
                risk_flags=data.get("risk_flags", []),
            )

        except Exception as e:
            log.error("Workflow extraction failed: %s", e)
            return self._fallback_workflow(intent, query, [c.source for c in chunks])

    def _fallback_workflow(self, intent: str, query: str, sources: List[str]) -> LearnedWorkflow:
        return LearnedWorkflow(
            template_id=intent,
            name=intent.replace("_", " ").title(),
            description="Auto-learned workflow (fallback — manual review recommended)",
            apps_required=["terminal"],
            estimated_steps=3,
            estimated_budget=5,
            steps=[
                {
                    "id": 1,
                    "app": "terminal",
                    "action": "research",
                    "description": f"Research: {query}",
                    "verification": "User reviews steps",
                    "step_cost": 1,
                    "requires_decision": True,
                }
            ],
            confidence=0.3,
            sources=sources,
            query=query,
            risk_flags=["manual_review_required"],
        )
