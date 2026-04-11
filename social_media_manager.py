#!/usr/bin/env python3
"""
social_media_manager.py — Gold Tier Social Media Draft + API

Generate social media post drafts for Facebook, Instagram, and Twitter/X.
Optionally post via API when credentials are configured.

Architecture: Draft-first, API-optional (like linkedin_post_generator.py).

Config section in config.json:
    "social_media": {
        "facebook": {"enabled": false, "page_id": "", "page_access_token": ""},
        "instagram": {"enabled": false, "business_account_id": "", "access_token": ""},
        "twitter": {"enabled": false, "api_key": "", "api_secret": "",
                     "access_token": "", "access_secret": ""}
    }

Usage:
    from social_media_manager import generate_social_post, execute_social_post
"""

import os
import re
import json
import subprocess
import tempfile
import hashlib
import hmac
import base64
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VAULT_DIR = SCRIPT_DIR
CONFIG_FILE = os.path.join(VAULT_DIR, "config.json")
PENDING_APPROVAL_DIR = os.path.join(VAULT_DIR, "Pending_Approval")
LOGS_DIR = os.path.join(VAULT_DIR, "Logs")
LOG_FILE = os.path.join(VAULT_DIR, "watcher.log")

VALID_PLATFORMS = {"facebook", "instagram", "twitter"}
VALID_GOALS = {"awareness", "lead_generation", "update", "engagement"}

# Character limits per platform
CHAR_LIMITS = {
    "facebook": 63206,
    "instagram": 2200,
    "twitter": 280,
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts} : [social] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def iso_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def load_config() -> dict:
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------------
# Draft Generation
# ---------------------------------------------------------------------------

PLATFORM_PROMPTS = {
    "facebook": (
        "Write a Facebook business page post.\n"
        "- Engaging opening line\n"
        "- 2-3 short paragraphs of value\n"
        "- Clear call-to-action\n"
        "- 3-5 relevant hashtags\n"
        "- Keep under 500 characters for optimal engagement\n"
        "- Conversational, approachable tone"
    ),
    "instagram": (
        "Write an Instagram caption for a business post.\n"
        "- Strong hook in first line (shows in preview)\n"
        "- Value-packed body with line breaks\n"
        "- Call-to-action\n"
        "- 10-15 relevant hashtags on a separate line\n"
        "- Keep under 2200 characters\n"
        "- Visual, descriptive language"
    ),
    "twitter": (
        "Write a tweet for a business account.\n"
        "- Punchy, attention-grabbing single message\n"
        "- Include 1-2 hashtags max\n"
        "- MUST be under 280 characters total\n"
        "- No emojis\n"
        "- Direct, confident tone"
    ),
}


def _generate_with_claude(platform: str, topic: str, audience: str,
                          goal: str, tone: str) -> str:
    """Generate post content using Claude CLI."""
    platform_guide = PLATFORM_PROMPTS.get(platform, PLATFORM_PROMPTS["facebook"])

    prompt = (
        f"Generate a {platform} post for a business.\n\n"
        f"Topic: {topic}\n"
        f"Target audience: {audience}\n"
        f"Goal: {goal}\n"
        f"Tone: {tone}\n\n"
        f"{platform_guide}\n\n"
        f"RULES:\n"
        f"- No emojis\n"
        f"- No markdown formatting\n"
        f"- Output ONLY the post text, no preamble\n"
    )

    try:
        result = subprocess.run(
            ["claude", "--print", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=VAULT_DIR,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return ""


def _generate_fallback(platform: str, topic: str, audience: str,
                       goal: str) -> str:
    """Template-based fallback when Claude CLI is unavailable."""
    if platform == "twitter":
        return (
            f"{topic} — {audience} need to know this. "
            f"The landscape is changing. Are you ready? "
            f"#Business #Strategy"
        )[:280]

    if platform == "instagram":
        return (
            f"What most {audience} are missing about {topic}.\n\n"
            f"The game is changing. Those who adapt early will lead.\n\n"
            f"Here is what matters now:\n"
            f"Understand the shift. Take action. Stay ahead.\n\n"
            f"The difference between leaders and followers?\n"
            f"Leaders act on insights like these before everyone else.\n\n"
            f"Save this post. Share it with someone who needs to hear it.\n\n"
            f"#Business #Strategy #Growth #Innovation #Leadership "
            f"#{topic.split()[0] if topic.split() else 'Tips'} "
            f"#Entrepreneurship #Success #Mindset #Motivation #Goals"
        )

    # Facebook default
    return (
        f"Are you keeping up with {topic}?\n\n"
        f"Most {audience} are not paying attention to this shift, "
        f"but it is going to change everything.\n\n"
        f"The key takeaway: adapt now or fall behind. "
        f"The businesses that move first will have the advantage.\n\n"
        f"What is your take? Let us know in the comments.\n\n"
        f"#Business #Strategy #Growth #Innovation"
    )


def generate_social_post(
    platform: str,
    topic: str,
    audience: str = "business professionals",
    goal: str = "awareness",
    tone: str = "professional",
) -> dict:
    """Generate a social media post draft and save to Pending_Approval/.

    Args:
        platform: "facebook", "instagram", or "twitter"
        topic: Subject of the post
        audience: Target audience description
        goal: "awareness", "lead_generation", "update", "engagement"
        tone: Tone descriptor (e.g. "professional", "casual")

    Returns:
        {"post_content": str, "draft_path": str, "platform": str} on success
        {"error": str} on failure
    """
    platform = platform.lower().strip()
    if platform not in VALID_PLATFORMS:
        return {"error": f"Invalid platform: {platform}. Must be one of: {VALID_PLATFORMS}"}

    if not topic or not topic.strip():
        return {"error": "Missing required field: topic"}

    topic = topic.strip()
    audience = audience.strip() if audience else "business professionals"

    if goal not in VALID_GOALS:
        goal = "awareness"

    # Generate content
    post_content = _generate_with_claude(platform, topic, audience, goal, tone)

    if not post_content:
        log(f"Claude CLI unavailable for {platform} — using template fallback")
        post_content = _generate_fallback(platform, topic, audience, goal)

    # Enforce character limit
    char_limit = CHAR_LIMITS.get(platform, 5000)
    if len(post_content) > char_limit:
        post_content = post_content[:char_limit - 3] + "..."

    # Create draft file
    os.makedirs(PENDING_APPROVAL_DIR, exist_ok=True)
    ts = file_ts()
    fname = f"SOCIAL_{platform.upper()}_{ts}.md"
    fpath = os.path.join(PENDING_APPROVAL_DIR, fname)

    safe_topic = topic.replace('"', '\\"')

    draft = (
        "---\n"
        f"type: social_media_post\n"
        f"platform: {platform}\n"
        f"goal: {goal}\n"
        f'topic: "{safe_topic}"\n'
        f"status: pending_approval\n"
        f"created: {iso_ts()}\n"
        "---\n"
        "\n"
        f"# {platform.title()} Post Draft\n"
        "\n"
        "## Post Content\n"
        "\n"
        f"{post_content}\n"
        "\n"
        "## Metadata\n"
        f"- **Platform**: {platform}\n"
        f"- **Character count**: {len(post_content)} / {char_limit}\n"
        f"- **Goal**: {goal}\n"
        f"- **Target audience**: {audience}\n"
        f"- **Tone**: {tone}\n"
        "\n"
        "## Review\n"
        "- [ ] Content appropriate for platform\n"
        "- [ ] Tone matches brand voice\n"
        "- [ ] No confidential information\n"
        "- [ ] Approved for publishing\n"
        "\n"
        "> To approve: change `status: pending_approval` to `status: approved` in frontmatter.\n"
        "> To reject: change to `status: rejected`.\n"
    )

    try:
        with open(fpath, "w", encoding="utf-8") as fh:
            fh.write(draft)
    except OSError as exc:
        return {"error": f"Failed to write draft: {exc}"}

    draft_path = f"Pending_Approval/{fname}"
    log(f"{platform} draft created: {draft_path} ({len(post_content)} chars)")

    return {
        "post_content": post_content,
        "draft_path": draft_path,
        "platform": platform,
    }


def create_draft_file(platform: str, content: str, metadata: dict = None) -> str:
    """Save raw content as a draft file. Returns draft path."""
    os.makedirs(PENDING_APPROVAL_DIR, exist_ok=True)
    ts = file_ts()
    fname = f"SOCIAL_{platform.upper()}_{ts}.md"
    fpath = os.path.join(PENDING_APPROVAL_DIR, fname)

    meta_str = ""
    if metadata:
        for k, v in metadata.items():
            meta_str += f"- **{k}**: {v}\n"

    draft = (
        "---\n"
        f"type: social_media_post\n"
        f"platform: {platform}\n"
        f"status: pending_approval\n"
        f"created: {iso_ts()}\n"
        "---\n"
        "\n"
        f"# {platform.title()} Post Draft\n"
        "\n"
        "## Post Content\n"
        "\n"
        f"{content}\n"
        "\n"
        "## Metadata\n"
        f"{meta_str}"
    )

    try:
        with open(fpath, "w", encoding="utf-8") as fh:
            fh.write(draft)
        return f"Pending_Approval/{fname}"
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# API Posting
# ---------------------------------------------------------------------------

def post_to_facebook(content: str, page_id: str,
                     page_access_token: str) -> dict:
    """Post to Facebook Page via Graph API.

    Returns: {"success": bool, "post_id": str, "error": str}
    """
    url = f"https://graph.facebook.com/v18.0/{page_id}/feed"
    data = urllib.parse.urlencode({
        "message": content,
        "access_token": page_access_token,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return {
            "success": True,
            "post_id": result.get("id", ""),
            "error": None,
        }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"success": False, "post_id": None, "error": f"HTTP {exc.code}: {body[:300]}"}
    except Exception as exc:
        return {"success": False, "post_id": None, "error": str(exc)}


def post_to_instagram(content: str, image_url: str,
                      business_account_id: str,
                      access_token: str) -> dict:
    """Post to Instagram via Graph API (requires image_url).

    Returns: {"success": bool, "post_id": str, "error": str}
    """
    if not image_url:
        return {"success": False, "post_id": None,
                "error": "Instagram requires an image_url"}

    # Step 1: Create media container
    url = f"https://graph.facebook.com/v18.0/{business_account_id}/media"
    data = urllib.parse.urlencode({
        "image_url": image_url,
        "caption": content,
        "access_token": access_token,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        container_id = result.get("id")
        if not container_id:
            return {"success": False, "post_id": None,
                    "error": "No container ID returned"}
    except Exception as exc:
        return {"success": False, "post_id": None, "error": str(exc)}

    # Step 2: Publish
    pub_url = f"https://graph.facebook.com/v18.0/{business_account_id}/media_publish"
    pub_data = urllib.parse.urlencode({
        "creation_id": container_id,
        "access_token": access_token,
    }).encode("utf-8")

    pub_req = urllib.request.Request(pub_url, data=pub_data, method="POST")

    try:
        with urllib.request.urlopen(pub_req, timeout=30) as resp:
            pub_result = json.loads(resp.read().decode("utf-8"))
        return {
            "success": True,
            "post_id": pub_result.get("id", ""),
            "error": None,
        }
    except Exception as exc:
        return {"success": False, "post_id": None, "error": str(exc)}


def post_to_twitter(content: str, api_key: str, api_secret: str,
                    access_token: str, access_secret: str) -> dict:
    """Post a tweet via Twitter/X API v2 using OAuth 1.0a.

    Returns: {"success": bool, "tweet_id": str, "error": str}
    """
    url = "https://api.twitter.com/2/tweets"
    method = "POST"

    # OAuth 1.0a signature
    oauth_params = {
        "oauth_consumer_key": api_key,
        "oauth_nonce": hashlib.sha256(
            str(time.time()).encode()
        ).hexdigest()[:32],
        "oauth_signature_method": "HMAC-SHA256",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }

    # Create signature base string
    params_str = "&".join(
        f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
        for k, v in sorted(oauth_params.items())
    )
    base_string = (
        f"{method}&"
        f"{urllib.parse.quote(url, safe='')}&"
        f"{urllib.parse.quote(params_str, safe='')}"
    )

    signing_key = (
        f"{urllib.parse.quote(api_secret, safe='')}&"
        f"{urllib.parse.quote(access_secret, safe='')}"
    )

    signature = base64.b64encode(
        hmac.new(
            signing_key.encode("utf-8"),
            base_string.encode("utf-8"),
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")

    oauth_params["oauth_signature"] = signature

    auth_header = "OAuth " + ", ".join(
        f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
        for k, v in sorted(oauth_params.items())
    )

    payload = json.dumps({"text": content}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": auth_header,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        tweet_id = result.get("data", {}).get("id", "")
        return {"success": True, "tweet_id": tweet_id, "error": None}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"success": False, "tweet_id": None,
                "error": f"HTTP {exc.code}: {body[:300]}"}
    except Exception as exc:
        return {"success": False, "tweet_id": None, "error": str(exc)}


# ---------------------------------------------------------------------------
# Execute (post after approval)
# ---------------------------------------------------------------------------

def execute_social_post(platform: str, approval_file: str) -> dict:
    """Check approval and post via API (if keys configured).

    Args:
        platform: "facebook", "instagram", or "twitter"
        approval_file: Path to the approval/draft file

    Returns:
        {"status": "posted"|"ready_manual"|"blocked", "details": str}
    """
    # Read the draft file
    fpath = os.path.join(VAULT_DIR, approval_file)
    if not os.path.isfile(fpath):
        return {"status": "failed", "details": f"File not found: {approval_file}"}

    try:
        with open(fpath, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError as exc:
        return {"status": "failed", "details": str(exc)}

    # Check approval status
    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if fm_match:
        fm_text = fm_match.group(1)
        status_match = re.search(r"status:\s*(\S+)", fm_text)
        if status_match:
            status = status_match.group(1)
            if status != "approved":
                return {"status": "blocked",
                        "details": f"Not approved (status: {status})"}

    # Extract post content
    post_match = re.search(
        r"## Post Content\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL
    )
    post_content = post_match.group(1).strip() if post_match else ""

    if not post_content:
        return {"status": "failed", "details": "No post content found in draft"}

    # Check if API keys are configured
    config = load_config()
    social_cfg = config.get("social_media", {})
    platform_cfg = social_cfg.get(platform, {})

    if not platform_cfg.get("enabled"):
        log(f"{platform} API not configured — marking as ready for manual posting")
        return {
            "status": "ready_manual",
            "details": f"{platform} API not enabled. Post manually:\n\n{post_content}",
        }

    # Post via API
    if platform == "facebook":
        result = post_to_facebook(
            post_content,
            platform_cfg.get("page_id", ""),
            platform_cfg.get("page_access_token", ""),
        )
        if result["success"]:
            return {"status": "posted", "details": f"Facebook post ID: {result['post_id']}"}
        return {"status": "failed", "details": result["error"]}

    elif platform == "instagram":
        image_match = re.search(r"image_url:\s*(\S+)", content)
        image_url = image_match.group(1) if image_match else ""
        result = post_to_instagram(
            post_content,
            image_url,
            platform_cfg.get("business_account_id", ""),
            platform_cfg.get("access_token", ""),
        )
        if result["success"]:
            return {"status": "posted", "details": f"Instagram post ID: {result['post_id']}"}
        return {"status": "failed", "details": result["error"]}

    elif platform == "twitter":
        result = post_to_twitter(
            post_content,
            platform_cfg.get("api_key", ""),
            platform_cfg.get("api_secret", ""),
            platform_cfg.get("access_token", ""),
            platform_cfg.get("access_secret", ""),
        )
        if result["success"]:
            return {"status": "posted", "details": f"Tweet ID: {result['tweet_id']}"}
        return {"status": "failed", "details": result["error"]}

    return {"status": "failed", "details": f"Unknown platform: {platform}"}


def list_drafts() -> list:
    """List pending social media drafts."""
    results = []
    try:
        entries = sorted(os.listdir(PENDING_APPROVAL_DIR))
    except OSError:
        return results

    for entry in entries:
        if not entry.startswith("SOCIAL_") or not entry.endswith(".md"):
            continue

        fpath = os.path.join(PENDING_APPROVAL_DIR, entry)
        try:
            with open(fpath, "r", encoding="utf-8") as fh:
                content = fh.read(500)

            fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            fm = {}
            if fm_match:
                for line in fm_match.group(1).split("\n"):
                    if ":" in line:
                        k, _, v = line.partition(":")
                        fm[k.strip()] = v.strip().strip('"\'')

            results.append({
                "file": entry,
                "platform": fm.get("platform", "unknown"),
                "status": fm.get("status", "unknown"),
                "created": fm.get("created", ""),
                "topic": fm.get("topic", ""),
            })
        except OSError:
            continue

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        print("social_media_manager.py — self-test")

        # Test draft generation (no API calls)
        result = generate_social_post(
            platform="twitter",
            topic="AI automation for business",
            audience="small business owners",
            goal="awareness",
        )

        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Draft saved: {result['draft_path']}")
            print(f"Platform: {result['platform']}")
            print(f"Content ({len(result['post_content'])} chars):")
            print(result["post_content"])

        # List drafts
        drafts = list_drafts()
        print(f"\nPending drafts: {len(drafts)}")
        for d in drafts:
            print(f"  {d['file']} ({d['platform']}, {d['status']})")

        print("\nOK")
    else:
        print("Usage: python social_media_manager.py --test")
