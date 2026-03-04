#!/usr/bin/env python3
"""LinkedIn Business Post Generator — Silver Tier Skill Implementation.

Generates professional LinkedIn post drafts and saves them to
Pending_Approval/LINKEDIN_<YYYYMMDD_HHMMSS>.md for human review.

Implements: .claude/skills/generate-linkedin-business-post/SKILL.md
"""

import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone

VAULT_DIR = os.path.dirname(os.path.abspath(__file__))
PENDING_APPROVAL_DIR = os.path.join(VAULT_DIR, "Pending_Approval")
LOG_FILE = os.path.join(VAULT_DIR, "watcher.log")

VALID_GOALS = {"awareness", "lead_generation", "update"}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] [linkedin-gen] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Input extraction from task content
# ---------------------------------------------------------------------------

def extract_marketing_params(task_content: str) -> dict:
    """Parse topic, audience, and goal from a task's markdown content.

    Looks for explicit fields first (e.g. 'Topic: ...' or 'Audience: ...'),
    then falls back to extracting from Task Description.
    """
    topic = ""
    audience = ""
    goal = "awareness"

    # Try explicit field extraction
    topic_match = re.search(r"(?i)(?:topic|subject)\s*[:=]\s*(.+)", task_content)
    if topic_match:
        topic = topic_match.group(1).strip().strip('"\'')

    audience_match = re.search(r"(?i)audience\s*[:=]\s*(.+)", task_content)
    if audience_match:
        audience = audience_match.group(1).strip().strip('"\'')

    goal_match = re.search(r"(?i)goal\s*[:=]\s*(\w+)", task_content)
    if goal_match:
        g = goal_match.group(1).strip().lower()
        if g in VALID_GOALS:
            goal = g

    # Fallback: extract from Task Description section
    if not topic:
        desc_match = re.search(
            r"## Task Description\s*\n(.*?)(?=\n##|\Z)",
            task_content,
            re.DOTALL,
        )
        if desc_match:
            desc = desc_match.group(1).strip()
            # Use first meaningful line as topic
            for line in desc.split("\n"):
                line = line.strip().strip("-*> ")
                if len(line) > 10:
                    topic = line[:200]
                    break

    # Fallback audience from description keywords
    if not audience:
        audience = "business professionals"

    return {"topic": topic, "audience": audience, "goal": goal}


# ---------------------------------------------------------------------------
# Post generation
# ---------------------------------------------------------------------------

GOAL_PROMPTS = {
    "awareness": (
        "Write a LinkedIn post using this structure:\n"
        "1. Hook — a punchy, attention-grabbing opening line\n"
        "2. Insight — share a valuable perspective or data point\n"
        "3. Value statement — explain why this matters to the reader\n"
        "4. CTA — 'Follow for more insights on...' or 'Share if this resonates'\n"
        "5. 3-5 relevant hashtags\n\n"
        "Tone: Thought leadership, confident, informative."
    ),
    "lead_generation": (
        "Write a LinkedIn post using this structure:\n"
        "1. Pain point — identify a specific problem the audience faces\n"
        "2. Solution — present how this is solved\n"
        "3. Proof/credibility — social proof, stats, or results\n"
        "4. CTA — 'DM me...' or 'Comment [keyword] to get...' or 'Link in comments'\n"
        "5. 3-5 relevant hashtags\n\n"
        "Tone: Problem-solution, empathetic, action-oriented."
    ),
    "update": (
        "Write a LinkedIn post using this structure:\n"
        "1. Announcement — clear statement of what's new\n"
        "2. Context — why this matters, what led to this\n"
        "3. Impact — what it means for the audience\n"
        "4. CTA — 'Learn more at...' or 'Stay tuned for...'\n"
        "5. 3-5 relevant hashtags\n\n"
        "Tone: Professional, direct, excited but not overhyped."
    ),
}


def _generate_with_claude(topic: str, audience: str, goal: str) -> str:
    """Try to generate post content using Claude CLI."""
    structure = GOAL_PROMPTS.get(goal, GOAL_PROMPTS["awareness"])

    prompt = (
        f"Generate a LinkedIn post for a business.\n\n"
        f"Topic: {topic}\n"
        f"Target audience: {audience}\n"
        f"Goal: {goal}\n\n"
        f"{structure}\n\n"
        f"RULES:\n"
        f"- Keep total length under 1,300 characters.\n"
        f"- Use short paragraphs (1-2 sentences each).\n"
        f"- Use plain text only — no markdown, no bold, no bullets.\n"
        f"- Use line breaks between paragraphs for LinkedIn readability.\n"
        f"- No emojis.\n"
        f"- Address the audience directly using 'you' language.\n"
        f"- Output ONLY the post text (no preamble, no explanation)."
    )

    result = subprocess.run(
        ["claude", "--print", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=VAULT_DIR,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return ""


def _generate_fallback(topic: str, audience: str, goal: str) -> str:
    """Template-based fallback when Claude CLI is unavailable."""
    if goal == "lead_generation":
        return (
            f"Are you still struggling with {topic}?\n\n"
            f"Most {audience} spend too much time on this "
            f"without seeing real results.\n\n"
            f"There is a better way. We have helped teams "
            f"cut their effort in half while getting better outcomes.\n\n"
            f"The difference is not working harder. "
            f"It is working with the right approach.\n\n"
            f"Want to see how this works for your situation? "
            f"Drop \"INFO\" in the comments or send me a DM.\n\n"
            f"#Business #Growth #Innovation #Strategy"
        )
    elif goal == "update":
        return (
            f"Exciting news: {topic}.\n\n"
            f"We have been working on this for a while, "
            f"and today we are ready to share it with {audience}.\n\n"
            f"This means faster results, better outcomes, "
            f"and a smoother experience for everyone involved.\n\n"
            f"Stay tuned for more details. "
            f"Follow along to be the first to know what is next.\n\n"
            f"#Update #Innovation #Business #Growth"
        )
    else:  # awareness
        return (
            f"Here is something most {audience} are not paying attention to: "
            f"{topic}.\n\n"
            f"The landscape is shifting. Those who adapt early "
            f"will have a significant advantage.\n\n"
            f"The key insight is this: the old playbook no longer works. "
            f"What matters now is speed, adaptability, and willingness "
            f"to rethink the fundamentals.\n\n"
            f"Follow for more insights on navigating this shift. "
            f"Share if this resonates with your experience.\n\n"
            f"#ThoughtLeadership #Business #Innovation #Strategy"
        )


def generate_linkedin_post(
    topic: str,
    audience: str,
    goal: str = "awareness",
) -> dict:
    """Generate a LinkedIn post draft and save to Pending_Approval/.

    Args:
        topic: Subject of the post.
        audience: Target audience description.
        goal: One of 'awareness', 'lead_generation', 'update'.

    Returns:
        {"post_content": str, "draft_path": str} on success.
        {"error": str} on validation failure.
    """
    # Validate inputs
    if not topic or not topic.strip():
        log("ERROR: missing topic — cannot generate post")
        return {"error": "Missing required field: topic"}

    if not audience or not audience.strip():
        log("ERROR: missing audience — cannot generate post")
        return {"error": "Missing required field: audience"}

    topic = topic.strip()
    audience = audience.strip()

    if goal not in VALID_GOALS:
        log(f"WARNING: invalid goal '{goal}', defaulting to 'awareness'")
        goal = "awareness"

    # Generate content
    post_content = ""
    try:
        post_content = _generate_with_claude(topic, audience, goal)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    if not post_content:
        log("Claude CLI unavailable — using template fallback")
        post_content = _generate_fallback(topic, audience, goal)

    # Ensure under 1300 chars
    if len(post_content) > 1300:
        post_content = post_content[:1297] + "..."

    # Create draft file
    os.makedirs(PENDING_APPROVAL_DIR, exist_ok=True)
    ts = datetime.now(timezone.utc)
    ts_str = ts.strftime("%Y%m%d_%H%M%S")
    iso_ts = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    fname = f"LINKEDIN_{ts_str}.md"
    fpath = os.path.join(PENDING_APPROVAL_DIR, fname)

    # Sanitize for YAML
    safe_topic = topic.replace('"', '\\"')
    safe_audience = audience.replace('"', '\\"')

    draft = (
        f"---\n"
        f'type: linkedin_post\n'
        f'goal: {goal}\n'
        f'topic: "{safe_topic}"\n'
        f'audience: "{safe_audience}"\n'
        f'status: pending_approval\n'
        f'created: {iso_ts}\n'
        f"---\n\n"
        f"## Post Content\n\n"
        f"{post_content}\n\n"
        f"## Metadata\n"
        f"- **Character count**: {len(post_content)}\n"
        f"- **Goal**: {goal}\n"
        f"- **Target audience**: {audience}\n"
        f"- **Hashtags included**: {post_content.count('#')}\n\n"
        f"## Review Notes\n"
        f"- [ ] Tone appropriate for audience\n"
        f"- [ ] CTA is clear and actionable\n"
        f"- [ ] No confidential information disclosed\n"
        f"- [ ] Approved for publishing\n"
    )

    # Atomic write
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=PENDING_APPROVAL_DIR, suffix=".tmp"
        )
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            fh.write(draft)
        os.replace(tmp_path, fpath)
    except OSError as exc:
        log(f"ERROR writing draft: {exc}")
        return {"error": f"Failed to write draft: {exc}"}

    draft_rel = f"Pending_Approval/{fname}"
    log(f"LinkedIn draft created: {draft_rel} ({len(post_content)} chars)")

    return {"post_content": post_content, "draft_path": draft_rel}


# ---------------------------------------------------------------------------
# CLI entry point (for standalone testing)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python linkedin_post_generator.py <topic> <audience> [goal]")
        print("  goal: awareness (default) | lead_generation | update")
        sys.exit(1)

    _topic = sys.argv[1]
    _audience = sys.argv[2]
    _goal = sys.argv[3] if len(sys.argv) > 3 else "awareness"

    result = generate_linkedin_post(_topic, _audience, _goal)
    if "error" in result:
        print(f"Error: {result['error']}")
        sys.exit(1)
    else:
        print(f"Draft saved: {result['draft_path']}")
        print(f"---\n{result['post_content']}")
