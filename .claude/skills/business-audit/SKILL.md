# Skill: Business Audit

**Trigger**: Scheduled (configurable day/hour) or manual invocation.

**Purpose**: Analyze system efficiency — task throughput, approval pipeline, error patterns, watcher health — and produce actionable optimization suggestions with efficiency scores (A-D).

**Entry point**: `python business_audit.py`

**Output**: `Reports/AUDIT_WEEK_YYYY-MM-DD.md`

**Sections**: Efficiency Scores, Task Throughput, Approval Pipeline, Error Analysis, Watcher Health, Optimization Suggestions.

**Schedule**: Configurable in config.json — `gold.audit_day` (default: friday), `gold.audit_hour_utc` (default: 18).
