"""Agent mode presets for Workflow Copilot — human-readable workflow specifications.

These presets define daily-life workflows that make repetitive tasks easier.
No coding, no file creation, no git — just UI navigation across apps.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AgentPreset:
    """A preset that defines a workflow, what it does, and its limits."""

    id: str
    name: str
    display_name: str
    category: str  # e.g. "Productivity", "Communication", "Research"
    description: str  # one-line summary
    what_it_does: str  # detailed explanation for laymen
    usage: str  # when and why to use it
    limitations: str  # common limits in plain English
    template_id: str  # workflow template id or "freeform"
    params_schema: List[dict] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    system_prompt_addendum: str = ""


# =============================================================
#  BUILT-IN WORKFLOW PRESETS
# =============================================================

DEFAULT_AGENT_PRESETS: List[AgentPreset] = [
    AgentPreset(
        id="morning_standup",
        name="Morning Standup",
        display_name="Morning Standup",
        category="Productivity",
        description="Open Jira, list your assigned tickets, copy status, open Slack, and paste your standup update.",
        what_it_does=(
            "This preset automates your daily standup routine. It opens your project management tool (Jira, Linear, etc.), "
            "reads your assigned tickets, copies the current status, then opens Slack, navigates to your standup channel, "
            "and posts a concise update with your ticket statuses. It waits briefly for any replies and summarizes them for you. "
            "You get your standup done without switching between apps manually."
        ),
        usage=(
            "Use this every morning before standup time. Just specify your Slack channel and the agent handles the rest. "
            "You can review the draft before it sends if you enable the decision gate."
        ),
        limitations=(
            "The agent can only read what is visible on screen. If your ticket board requires scrolling to see all assigned tickets, "
            "some items may be missed. Private channels or DMs may need manual navigation if the agent cannot find them by name. "
            "The agent cannot determine work completed yesterday vs today — it copies the current ticket state only."
        ),
        template_id="morning_standup",
        params_schema=[
            {"name": "channel", "label": "Slack Channel", "type": "text", "placeholder": "e.g. #standup"},
        ],
        examples=[
            "Post my Jira ticket status to #standup and tell me what people replied",
            "Do my morning standup update in Slack",
            "Check my assigned tickets and share the status in #team-standup",
        ],
        system_prompt_addendum=(
            "When doing a morning standup, keep the update concise: 1-2 sentences per ticket. "
            "Include ticket ID and current status. Do not paste raw HTML or Markdown."
        ),
    ),
    AgentPreset(
        id="ticket_to_slack",
        name="Ticket to Slack",
        display_name="Ticket to Slack",
        category="Productivity",
        description="Create a ticket in your project tracker and immediately share the link in a Slack channel.",
        what_it_does=(
            "This preset bridges your project tracker and Slack. It opens your tracker (Jira, Linear, GitHub Issues), "
            "creates a new ticket with the description you provide, copies the ticket URL, then switches to Slack, "
            "navigates to the specified channel, and posts the link. It waits for replies and summarizes any responses."
        ),
        usage=(
            "Use this when you need to file a ticket and immediately notify your team. Common scenarios: bug reports, "
            "feature requests, deployment issues. You only need the ticket description and the target Slack channel."
        ),
        limitations=(
            "The agent cannot determine the correct ticket type, priority, or assignee automatically. "
            "You may need to adjust these fields after creation. If the project tracker requires re-authentication, "
            "the agent will pause and ask for help. The agent cannot read Slack threads that require scrolling."
        ),
        template_id="ticket_to_slack",
        params_schema=[
            {"name": "description", "label": "Ticket Description", "type": "text", "placeholder": "e.g. Login button broken on mobile"},
            {"name": "channel", "label": "Slack Channel", "type": "text", "placeholder": "e.g. #engineering"},
        ],
        examples=[
            "Create a Jira ticket for the login bug and send it to #engineering",
            "File a ticket about the API error and post the link in Slack",
            "Report the checkout issue in Linear and share it in #bugs",
        ],
        system_prompt_addendum=(
            "After creating the ticket, always copy the URL from the browser address bar, not from any intermediate page. "
            "In Slack, paste only the URL and a brief one-line context."
        ),
    ),
    AgentPreset(
        id="email_triage",
        name="Email Triage",
        display_name="Email Triage",
        category="Communication",
        description="Open your email client, scan unread messages, flag urgent ones, and summarize them to your clipboard.",
        what_it_does=(
            "This preset reads your unread emails and gives you a prioritized summary. It opens your email client (Gmail, Outlook, etc.), "
            "scans the unread list, opens messages that look urgent based on sender or subject keywords, reads the content, "
            "and compiles a concise summary of what needs your attention. The summary is copied to your clipboard for easy pasting."
        ),
        usage=(
            "Use this when you have a backlog of unread emails and need to quickly identify what is urgent. "
            "Great for Monday mornings, post-vacation catch-up, or after focused work sessions."
        ),
        limitations=(
            "The agent can only see emails that are visible without scrolling. Very long inboxes may require multiple runs. "
            "The agent uses simple heuristics (sender name, subject keywords like 'urgent', 'ASAP', 'action required') to flag urgency — "
            "it may miss subtly important emails. It cannot click links inside emails or download attachments."
        ),
        template_id="email_triage",
        params_schema=[
            {"name": "email_url", "label": "Email URL", "type": "text", "placeholder": "e.g. https://mail.google.com"},
        ],
        examples=[
            "Triage my unread emails and copy a summary",
            "Check Gmail for urgent messages and summarize them",
            "Scan my inbox and tell me what needs attention today",
        ],
        system_prompt_addendum=(
            "When triaging emails, categorize each as: Urgent, Important, or Low Priority. "
            "Include sender name and subject line in the summary. Do not copy full email bodies."
        ),
    ),
    AgentPreset(
        id="research_digest",
        name="Research Digest",
        display_name="Research Digest",
        category="Research",
        description="Search the web, open top results, extract key points, and summarize them to your clipboard.",
        what_it_does=(
            "This preset is your research assistant. It opens a search engine, types your query, opens the top 2-3 results, "
            "reads each page, extracts the most relevant points, and compiles a concise digest. The digest is copied to your clipboard "
            "so you can paste it into a note, document, or message."
        ),
        usage=(
            "Use this when you need a quick answer to a question, want to compare information across sources, "
            "or need to gather context before a meeting. Just describe what you are looking for in plain English."
        ),
        limitations=(
            "The agent can only read publicly available web pages. Paywalled content, login-required forums, and PDFs cannot be read. "
            "Search results may be outdated. The agent extracts information from what is visible on screen — it does not scroll infinitely. "
            "Always verify critical facts from primary sources."
        ),
        template_id="research_digest",
        params_schema=[
            {"name": "query", "label": "Search Query", "type": "text", "placeholder": "e.g. Python asyncio best practices"},
        ],
        examples=[
            "Research Python asyncio best practices and summarize",
            "Find the latest remote work productivity tips and copy the best ones",
            "Look up current pricing for RTX 5090 across retailers",
            "Search for Nginx WebSocket configuration guides and summarize the steps",
        ],
        system_prompt_addendum=(
            "When researching, open 2-3 sources and cross-reference key facts. "
            "Summarize in bullet points. Include source URLs in the summary."
        ),
    ),
    AgentPreset(
        id="meeting_prep",
        name="Meeting Prep",
        display_name="Meeting Prep",
        category="Productivity",
        description="Check your calendar for the next meeting, look up attendees, and summarize a brief on each.",
        what_it_does=(
            "This preset helps you walk into meetings prepared. It opens your calendar, reads the next meeting details, "
            "extracts the attendee list, then searches for each attendee on LinkedIn or other public profiles. "
            "It compiles a brief: name, role, company, and any recent updates. The brief is copied to your clipboard."
        ),
        usage=(
            "Use this 5-10 minutes before an important meeting, especially with external stakeholders, clients, or new team members. "
            "You will have context on who you are talking to without manually looking everyone up."
        ),
        limitations=(
            "The agent can only find public profile information. Private profiles or people without an online presence will have minimal briefs. "
            "If attendee names are not visible in the calendar invite (e.g., only email addresses), the search may be less accurate. "
            "The agent cannot access internal HR systems or org charts."
        ),
        template_id="meeting_prep",
        params_schema=[
            {"name": "calendar_url", "label": "Calendar URL", "type": "text", "placeholder": "e.g. https://calendar.google.com"},
        ],
        examples=[
            "Prep me for my next meeting by looking up attendees",
            "Check my calendar and brief me on who I'm meeting",
            "Who am I meeting with at 2pm? Give me a quick brief on each person",
        ],
        system_prompt_addendum=(
            "When prepping for a meeting, focus on: current role, company, and any recent public activity. "
            "Keep each attendee brief to 1-2 sentences."
        ),
    ),
    AgentPreset(
        id="status_update",
        name="Status Update",
        display_name="Status Update",
        category="Productivity",
        description="Gather project status from your project board and send an update to a Slack channel.",
        what_it_does=(
            "This preset automates status updates. It opens your project board (Jira, Notion, Linear), reads the current sprint or project status, "
            "notes completed items, in-progress items, and blockers. It then opens Slack, navigates to your team channel, "
            "and posts a structured status update with this information."
        ),
        usage=(
            "Use this at the end of the day or week to share progress with your team. You can specify the project board URL "
            "and the target Slack channel. The agent compiles and posts the update for you."
        ),
        limitations=(
            "The agent can only read what is visible on the project board. If the board requires scrolling or filtering to see the right view, "
            "some items may be missed. The agent cannot interpret nuanced statuses — it reads labels as-is. "
            "Private channels may need manual navigation."
        ),
        template_id="status_update",
        params_schema=[
            {"name": "project_url", "label": "Project Board URL", "type": "text", "placeholder": "e.g. https://notion.so/..."},
            {"name": "slack_channel", "label": "Slack Channel", "type": "text", "placeholder": "e.g. #general"},
        ],
        examples=[
            "Send a project status update to #general from our Notion board",
            "Post today's Jira sprint status to Slack",
            "Share the weekly progress in #team-updates",
        ],
        system_prompt_addendum=(
            "Structure status updates as: Completed, In Progress, Blocked. "
            "Use bullet points. Keep the entire message under 10 lines."
        ),
    ),
    AgentPreset(
        id="approval_loop",
        name="Approval Loop",
        display_name="Approval Loop",
        category="Productivity",
        description="Open a tool with pending approvals, screenshot each, summarize what needs approval, and ask you yes/no for each.",
        what_it_does=(
            "This preset guides you through pending approvals efficiently. It opens your approvals page (Jira, GitHub PRs, expense tool, etc.), "
            "reads the list of pending items, takes a screenshot of each for context, and presents them to you one by one with a simple yes/no question. "
            "You decide on each item without navigating through multiple pages yourself."
        ),
        usage=(
            "Use this when you have a backlog of PRs, tickets, or expenses awaiting your approval. "
            "The agent brings each item to your attention with context so you can make quick decisions."
        ),
        limitations=(
            "The agent can only see approvals that are visible on screen. If the approvals tool requires pagination, "
            "only the first page will be reviewed. The agent cannot approve on your behalf — it only asks for your decision. "
            "Some tools may require re-authentication."
        ),
        template_id="approval_loop",
        params_schema=[
            {"name": "approvals_url", "label": "Approvals Page URL", "type": "text", "placeholder": "e.g. https://jira.atlassian.com/approvals"},
        ],
        examples=[
            "Run through my pending Jira approvals and ask me for each one",
            "Check my PR approvals and guide me through them",
            "Review my pending expense reports one by one",
        ],
        system_prompt_addendum=(
            "For each approval item, present: title, requester, and a one-line summary of what is being asked. "
            "Keep the question simple: 'Approve this? (yes/no)'."
        ),
    ),
    AgentPreset(
        id="info_gather",
        name="Info Gather",
        display_name="Info Gather",
        category="General",
        description="Describe what information you need and the agent searches across apps to find it.",
        what_it_does=(
            "This is the freeform mode. You describe what information you need in plain English, and the agent dynamically plans "
            "a workflow to find it. It may search your email, calendar, project board, or the web depending on what you ask. "
            "The agent returns a concise answer copied to your clipboard."
        ),
        usage=(
            "Use this for ad-hoc questions that don't fit a specific preset. Examples: 'What is the deadline for the Q3 roadmap?' "
            "or 'What did Sarah say about the API changes in Slack?' The agent figures out which apps to check."
        ),
        limitations=(
            "Because the agent plans dynamically, complex multi-app searches may take longer. "
            "The agent may pause to ask for clarification if your request is ambiguous. "
            "It cannot access apps that require fresh logins or 2FA. The answer quality depends on what is visible on screen."
        ),
        template_id="freeform",
        params_schema=[
            {"name": "query", "label": "What do you need to know?", "type": "text", "placeholder": "e.g. What is the deadline for the Q3 roadmap?"},
        ],
        examples=[
            "Find the Q3 roadmap deadline",
            "What did Sarah say about the API changes in Slack?",
            "Get me the latest sales numbers from the dashboard",
            "When is my next 1:1 with Alex?",
        ],
        system_prompt_addendum=(
            "When the user describes a task freely, break it into milestones before executing. "
            "Confirm ambiguous steps with a decision gate. Prefer keyboard shortcuts over mouse clicks."
        ),
    ),
]


def get_all_agent_presets() -> List[AgentPreset]:
    """Return all agent presets."""
    return list(DEFAULT_AGENT_PRESETS)


def get_agent_preset_by_id(preset_id: str) -> Optional[AgentPreset]:
    """Find an agent preset by ID."""
    for preset in DEFAULT_AGENT_PRESETS:
        if preset.id == preset_id:
            return preset
    return None


def agent_preset_to_dict(preset: AgentPreset) -> dict:
    """Convert an AgentPreset to a dictionary for JSON serialization."""
    return {
        "id": preset.id,
        "name": preset.name,
        "display_name": preset.display_name,
        "category": preset.category,
        "description": preset.description,
        "what_it_does": preset.what_it_does,
        "usage": preset.usage,
        "limitations": preset.limitations,
        "template_id": preset.template_id,
        "params_schema": preset.params_schema,
        "examples": preset.examples,
        "system_prompt_addendum": preset.system_prompt_addendum,
    }
