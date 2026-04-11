# Skill: CEO Weekly Report

**Trigger**: Scheduled (configurable day/hour) or manual invocation.

**Purpose**: Generate a comprehensive weekly CEO briefing from Done/, Logs/, and Dashboard.md. Collects task metrics, approval stats, error rates, financial data (if Odoo configured), and social media activity.

**Entry point**: `python ceo_report_generator.py`

**Output**: `Reports/CEO_REPORT_WEEK_YYYY-MM-DD.md`

**Sections**: Executive Summary, Task Performance, Communication Activity, Financial Overview, Social Media, Issues & Alerts, Recommendations.

**Schedule**: Configurable in config.json — `gold.report_day` (default: monday), `gold.report_hour_utc` (default: 7).
