# Skill: generate-linkedin-business-post

## Tier
Silver

## Purpose

Generate a professional, platform-optimized LinkedIn post for business growth. Produces ready-to-review draft content with appropriate tone, structure, and call-to-action based on the target audience and campaign goal.

## Trigger

When a task requires marketing content, lead generation material, or a business update post for LinkedIn. Can be invoked directly or triggered by a task classified as `message` or `general` with marketing-related context.

## Input

```json
{
  "topic": "string",
  "audience": "string",
  "goal": "awareness | lead_generation | update"
}
```

| Field      | Type     | Description                                                                 |
|------------|----------|-----------------------------------------------------------------------------|
| `topic`    | `string` | The subject of the post (e.g., "new AI consulting service launch")         |
| `audience` | `string` | Target audience (e.g., "startup founders", "HR directors", "CTOs")         |
| `goal`     | `string` | Campaign objective: `awareness`, `lead_generation`, or `update`            |

## Output

```json
{
  "post_content": "string",
  "draft_path": "Pending_Approval/LINKEDIN_<YYYYMMDD_HHMMSS>.md"
}
```

## Execution Steps

1. **Validate input** — Confirm `topic` and `audience` are present and non-empty. Default `goal` to `awareness` if not provided. If `topic` or `audience` is missing, fail with a logged alert.
2. **Select tone and structure** based on `goal`:

   | Goal              | Tone                  | Structure                                      |
   |-------------------|-----------------------|------------------------------------------------|
   | `awareness`       | Thought leadership    | Hook → Insight → Value statement → CTA         |
   | `lead_generation` | Problem-solution      | Pain point → Solution → Proof/credibility → CTA |
   | `update`          | Professional, direct  | Announcement → Context → Impact → CTA          |

3. **Generate post content**:
   a. **Hook** (line 1) — Attention-grabbing opening line. Short, punchy, no fluff.
   b. **Body** (3–6 short paragraphs) — Deliver the core message using the structure for the selected goal. Use line breaks between paragraphs for LinkedIn readability.
   c. **Call-to-action** — Clear, specific next step aligned with the goal:
      - `awareness`: "Follow for more insights on..." / "Share if this resonates"
      - `lead_generation`: "DM me..." / "Comment [keyword] to get..." / "Link in comments"
      - `update`: "Learn more at..." / "Stay tuned for..."
   d. **Hashtags** — 3–5 relevant hashtags at the end.

4. **Optimize for LinkedIn**:
   - Keep total length under 1,300 characters (optimal engagement range).
   - Use short paragraphs (1–2 sentences each).
   - No markdown formatting (LinkedIn doesn't render it) — use plain text with line breaks.
   - Avoid emojis unless explicitly requested.
   - Use "you" language directed at the audience.

5. **Save draft** — Write the post to `Pending_Approval/` as a structured markdown file for human review. Create the directory if it does not exist.

6. **Return output** — Return the post content and draft file path.

## Draft File Format

```markdown
---
type: linkedin_post
goal: <awareness|lead_generation|update>
topic: <topic>
audience: <audience>
status: pending_approval
created: <ISO 8601 UTC timestamp>
---

## Post Content

<generated post text — plain text, LinkedIn-ready>

## Metadata
- **Character count**: <count>
- **Goal**: <goal>
- **Target audience**: <audience>
- **Hashtags included**: <count>

## Review Notes
- [ ] Tone appropriate for audience
- [ ] CTA is clear and actionable
- [ ] No confidential information disclosed
- [ ] Approved for publishing
```

## Side Effects

- Creates a draft file in `Pending_Approval/` directory.
- Creates the `Pending_Approval/` directory if it does not exist.

## Constraints

- Operates only within the vault root directory.
- Does **not** publish or send any content externally — output is a local draft file only.
- All generated content requires human approval before use (saved to `Pending_Approval/`, not `Done/`).
- Follows all policies defined in `Company_Handbook.md`.
- Draft filenames use the pattern: `LINKEDIN_<YYYYMMDD_HHMMSS>.md`.

## Failure Conditions

- Missing or empty `topic` — log alert in `Dashboard.md`, do not generate draft.
- Missing or empty `audience` — log alert in `Dashboard.md`, do not generate draft.
- Invalid `goal` value (not one of `awareness`, `lead_generation`, `update`) — default to `awareness` and proceed.

## Example Usage

**Input**:
```json
{
  "topic": "Launch of AI-powered document automation service",
  "audience": "SMB owners and operations managers",
  "goal": "lead_generation"
}
```

**Generated file**: `Pending_Approval/LINKEDIN_20260224_140000.md`

**Post content**:
```
You're still manually processing documents in 2026.

Your team spends 12+ hours a week on paperwork that adds zero revenue.
Meanwhile, your competitors automated this months ago.

We just launched an AI-powered document automation service built for small and mid-size businesses.

No enterprise pricing. No 6-month onboarding.
Just faster operations from week one.

Early clients are seeing 60% less time spent on document handling.

If you want to see how this works for your business, drop "AUTOMATE" in the comments or send me a DM.

#DocumentAutomation #AIforBusiness #SMBGrowth #OperationsEfficiency
```

## Invocation

Use this skill when a task requires LinkedIn content creation. Integrates into the Silver Tier pipeline — typically invoked after `generate-plan-md` identifies a marketing action step, or directly when a content request arrives in `Needs_Action/`.
