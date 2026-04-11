# Skill: Gold Autonomous Loop

**Trigger**: Scheduled execution or manual invocation via `run_gold.sh`.

**Purpose**: Top-level Gold Tier orchestrator — continuous autonomous loop with retry, In_Progress tracking, verification, and scheduled report generation. Supersedes Silver loop for Gold Tier operations.

**Entry points**:
- `python gold_loop.py` — continuous mode (default)
- `python gold_loop.py --once` — single cycle
- `python gold_loop.py --dry-run` — analyze only
- `./run_gold.sh` — full pipeline entry point

**10-Phase Pipeline**:
1. Initialize — load policies, ensure Gold dirs
2. Run Watchers — perception scan via watcher_manager.py
3. Analyze — scan Needs_Action/, classify tasks
4. Plan — validate schemas, generate plans
5. Track — move tasks to In_Progress/
6. Execute — run with retry wrapper (exponential backoff)
7. Verify — post-execution checks
8. Report Check — generate CEO report / audit if due
9. Update Dashboard — enhanced Gold Tier metrics
10. Sleep or Exit — continuous or single cycle

**Completion condition**: In continuous mode, runs until SIGINT/SIGTERM. In --once mode, exits after one cycle.
