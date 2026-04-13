Project Overview

  Gold Tier AI Employee — a file-driven autonomous agent with 3 tiers (Bronze → Silver → Gold), 21      
  Python/Shell scripts, and a 10-phase continuous pipeline.

  Current state: 5 pending tasks in Needs_Action/, 17 completed in Done/, 10 pending approvals.

  ---
  Running Commands

  Main Entry Points (Gold Tier — Recommended)

  cd /mnt/e/AI_Employ_Vault/Bronce-tiar

  # Continuous loop (runs every 5 min, Ctrl+C to stop)
  ./run_gold.sh

  # Single cycle then exit
  ./run_gold.sh --once

  # Analyze only — no execution
  ./run_gold.sh --dry-run

  # Generate CEO report now
  ./run_gold.sh --report

  # Run business audit now
  ./run_gold.sh --audit

  # Run watchers only (scan inputs)
  ./run_gold.sh --watchers

  Silver Tier (Legacy)

  ./run_silver.sh full         # watchers + reasoning loop
  ./run_silver.sh --watchers   # watchers only
  ./run_silver.sh --loop       # reasoning loop only
  ./run_silver.sh --dry-run    # analyze without executing

  Individual Python Modules

  # Gold loop directly
  python3 gold_loop.py              # continuous
  python3 gold_loop.py --once       # single cycle
  python3 gold_loop.py --dry-run    # analyze only

  # Silver loop
  python3 silver_loop.py

  # Watchers (perception layer)
  python3 watcher_manager.py --once  # all 3 watchers (single scan)
  python3 watcher_manager.py        # all 3 watchers (continuous)
  python3 watcher.py                # filesystem only (Inbox/)
  python3 gmail_watcher.py --once   # Gmail only
  python3 whatsapp_watcher.py --once # WhatsApp Web only (requires Playwright setup)
  python3 whatsapp_watcher.py --setup # first-time QR code login

  # Reports
  python3 ceo_report_generator.py                    # CEO weekly report
  python3 ceo_report_generator.py --since 2026-04-01 # custom period
  python3 business_audit.py                           # efficiency audit

  # Social media
  python3 social_media_manager.py --test  # generate test draft

  # LinkedIn
  python3 linkedin_post_generator.py "topic" "audience" goal

  # Odoo ERP
  python3 odoo_client.py --test   # config check

  # Scheduling
  ./schedule_setup.sh             # install daily cron
  ./schedule_setup.sh --status    # check schedule
  ./schedule_setup.sh --remove    # remove schedule

  # Backup
  ./backup.sh                    # create vault .tar.gz backup

  Monitoring

  tail -f watcher.log              # live log
  cat Dashboard.md                 # system state
  tail -20 Logs/actions.jsonl      # recent actions
  cat .gold_retry_state.json       # retry state
  ls Needs_Action/                 # pending tasks
  ls In_Progress/                  # executing tasks
  ls Done/                         # completed tasks
  ls Pending_Approval/             # awaiting human review
  ls Reports/                      # generated reports

  WSL2 / Windows Task Scheduler

  Program: wsl
  Arguments: bash -c "cd /mnt/e/AI_Employ_Vault/Bronce-tiar && ./run_gold.sh --once"

  ---
  Quickest way to see it work: ./run_gold.sh --once — this will process the 5 pending tasks in
  Needs_Action/ through the full 10-phase pipeline in a single cycle.

##### About Project ////////////////////////////////////////////////////////////

 ---
  What Is This Project?

  A file-driven autonomous AI employee that runs through your filesystem. Instead of chatting, it       
  reads/writes markdown files. The flow is simple:

  YOU drop input → Watchers detect it → Task created → Agent processes it → Result in Done/

  ---
  The 4 Folders You Need to Understand
  Folder: Inbox/
  What It Is: Drop zone for raw input files
  Your Role: YOU put files here
  ────────────────────────────────────────
  Folder: Needs_Action/
  What It Is: Tasks waiting to be processed
  Your Role: System creates these (or you can manually)
  ────────────────────────────────────────
  Folder: Pending_Approval/
  What It Is: Actions needing YOUR permission
  Your Role: YOU approve/reject these
  ────────────────────────────────────────
  Folder: Done/
  What It Is: Completed tasks (permanent archive)
  Your Role: Read results here
  How they connect:

  YOU                          SYSTEM                         YOU
   │                             │                              │
   ├─ Drop file in Inbox/        │                              │
   │         ──────────────►  Watcher creates TASK_*.md         │
   │                          in Needs_Action/                  │
   │                             │                              │
   │                          Agent processes task              │
   │                             │                              │
   │                          Needs approval? ──YES──►  APPROVAL_*.md in
   │                             │                      Pending_Approval/
   │                             │                              │
   │                             │                  YOU change status: approved
   │                             │                              │
   │                          Task completes ──────────►  Result in Done/
   │                             │                              │
   │                          Dashboard.md updated              │

  ---
  Step-by-Step: Setting Up From Scratch

  1. Check Python is installed

  python3 --version   # needs 3.6+

  2. Verify the vault

  cd /mnt/e/AI_Employ_Vault/Bronce-tiar
  ls Needs_Action/ Done/ Pending_Approval/ Inbox/

  3. (Optional) Set up Gmail watcher

  Edit config.json — fill in your Gmail email and App Password:
  {
    "gmail": {
      "email": "your.email@gmail.com",
      "app_password": "your-16-char-app-password"
    }
  }

  4. (Optional) Set up WhatsApp watcher

  pip install playwright
  playwright install chromium
  python3 whatsapp_watcher.py --setup   # scan QR code with your phone

  ---
  How to Create Tasks (3 Ways)

  Way 1: Drop a file in Inbox/

  cp any-file.txt Inbox/
  The filesystem watcher auto-creates a TASK_*.md in Needs_Action/.

  Way 2: Let Gmail/WhatsApp watchers create tasks automatically

  Emails and WhatsApp messages are auto-converted to tasks when watchers run.

  Way 3: Create a task manually (most direct)

  cat > Needs_Action/my-task.md << 'EOF'
  ---
  type: general
  priority: medium
  status: pending
  created: 2026-04-13T12:00:00Z
  source: manual_drop
  ---

  ## Task Description
  Summarize the top 3 benefits of cloud computing for small businesses.

  ## Required Outcome
  A markdown list with one-sentence descriptions.

  ## Processing Checklist
  - [ ] analyze task
  - [ ] generate plan
  - [ ] complete objective
  EOF

  Required fields in every task:
  ┌──────────┬───────────────────────────────────────────────────┬─────────────────────────────────┐    
  │  Field   │                      Values                       │             Meaning             │    
  ├──────────┼───────────────────────────────────────────────────┼─────────────────────────────────┤    
  │ type     │ general, email, message, marketing, finance, file │ What kind of task               │    
  ├──────────┼───────────────────────────────────────────────────┼─────────────────────────────────┤    
  │ priority │ high, medium, low                                 │ Processing order                │    
  ├──────────┼───────────────────────────────────────────────────┼─────────────────────────────────┤    
  │ status   │ pending                                           │ Must be "pending" for new tasks │    
  ├──────────┼───────────────────────────────────────────────────┼─────────────────────────────────┤    
  │ created  │ ISO timestamp                                     │ When created                    │    
  ├──────────┼───────────────────────────────────────────────────┼─────────────────────────────────┤    
  │ source   │ any string                                        │ Where it came from              │    
  └──────────┴───────────────────────────────────────────────────┴─────────────────────────────────┘    
  ---
  How to Process Tasks (Running the System)

  Single cycle (recommended for beginners):

  ./run_gold.sh --once

  This runs ONE full cycle:
  1. Scans watchers for new input
  2. Picks up tasks from Needs_Action/
  3. Processes each task (AI reasoning via Claude)
  4. Moves completed tasks to Done/
  5. Updates Dashboard.md
  6. Exits

  Continuous mode (production):

  ./run_gold.sh
  Runs every 5 minutes in a loop. Press Ctrl+C to stop gracefully.

  Dry run (see what would happen without doing it):

  ./run_gold.sh --dry-run

  Run watchers only (just scan for new input):

  ./run_gold.sh --watchers

  ---
  How Pending Approval Works

  Some tasks need YOUR permission before the system acts. These are:
  ┌───────────┬───────────────────────────────┐
  │ Task Type │      Why Approval Needed      │
  ├───────────┼───────────────────────────────┤
  │ email     │ System wants to send an email │
  ├───────────┼───────────────────────────────┤
  │ marketing │ LinkedIn/social media post    │
  ├───────────┼───────────────────────────────┤
  │ finance   │ Invoice creation, payments    │
  └───────────┴───────────────────────────────┘
  When approval is needed, the system:

  1. Creates Pending_Approval/APPROVAL_*.md
  2. Pauses the task
  3. Waits for you

  How YOU approve:

  # 1. See what's pending
  ls Pending_Approval/

  # 2. Read the approval request
  cat Pending_Approval/APPROVAL_20260412_235954.md

  The file looks like:
  ---
  status: pending          # ← THIS IS WHAT YOU CHANGE
  action_type: send_email
  risk_level: medium
  ---

  To approve — open the file and change:
  status: approved

  To reject — change to:
  status: rejected

  Save the file. On the next run, the system picks it up and proceeds (or skips if rejected).

  Approval expiry:
  ┌────────────┬───────────────┐
  │ Risk Level │ Expires After │
  ├────────────┼───────────────┤
  │ Low        │ 72 hours      │
  ├────────────┼───────────────┤
  │ Medium     │ 48 hours      │
  ├────────────┼───────────────┤
  │ High       │ 24 hours      │
  └────────────┴───────────────┘
  Expired approvals are auto-rejected.

  ---
  How to Read Results

  After processing, check Done/:

  # List completed tasks
  ls Done/

  # Read a specific result
  cat Done/TASK_20260325_142445.md

  Each completed task has:
  - ## Result — the AI's output
  - ## Processing Checklist — all items checked [x]
  - ## Completion Notes — timestamp and summary
  - status: completed in frontmatter

  ---
  All Commands Reference

  # ═══════════════════════════════════════════
  # MAIN COMMANDS (start here)
  # ═══════════════════════════════════════════
  ./run_gold.sh --once        # process all pending tasks (single cycle)
  ./run_gold.sh               # continuous mode (every 5 min)
  ./run_gold.sh --dry-run     # preview only, no changes

  # ═══════════════════════════════════════════
  # WATCHERS (scan for new input)
  # ═══════════════════════════════════════════
  python3 watcher_manager.py --once   # all watchers, single scan
  python3 watcher.py                  # filesystem watcher only
  python3 gmail_watcher.py --once     # Gmail only
  python3 whatsapp_watcher.py --once  # WhatsApp only
  python3 whatsapp_watcher.py --setup # WhatsApp QR login (first time)

  # ═══════════════════════════════════════════
  # REPORTS (on demand)
  # ═══════════════════════════════════════════
  ./run_gold.sh --report      # CEO weekly report
  ./run_gold.sh --audit       # business audit
  python3 ceo_report_generator.py     # direct
  python3 business_audit.py           # direct

  # ═══════════════════════════════════════════
  # SOCIAL MEDIA & LINKEDIN
  # ═══════════════════════════════════════════
  python3 social_media_manager.py --test
  python3 linkedin_post_generator.py "topic" "audience" lead_generation

  # ═══════════════════════════════════════════
  # MONITORING (check system state)
  # ═══════════════════════════════════════════
  cat Dashboard.md                    # system status
  tail -f watcher.log                 # live log
  ls Needs_Action/                    # pending tasks
  ls Pending_Approval/                # awaiting your review
  ls Done/                            # completed tasks
  ls In_Progress/                     # currently executing
  ls Reports/                         # generated reports
  tail -20 Logs/actions.jsonl         # recent actions

  # ═══════════════════════════════════════════
  # SCHEDULING (auto-run daily)
  # ═══════════════════════════════════════════
  ./schedule_setup.sh                 # install daily cron
  ./schedule_setup.sh --status        # check schedule
  ./schedule_setup.sh --remove        # remove schedule

  # ═══════════════════════════════════════════
  # UTILITIES
  # ═══════════════════════════════════════════
  ./backup.sh                         # backup vault
  cat .gold_retry_state.json          # see retry state

  ---
  Your Current State Right Now
  ┌────────────────────────────────┬───────┬───────────────────────────────────────────────────────────┐  │              Item              │ Count │                       Action Needed                       │  ├────────────────────────────────┼───────┼───────────────────────────────────────────────────────────┤  │ Pending tasks in Needs_Action/ │ 5     │ Run ./run_gold.sh --once to process                       │  ├────────────────────────────────┼───────┼───────────────────────────────────────────────────────────┤  │ Pending approvals              │ 10    │ Open each file, change status: pending → status: approved │  ├────────────────────────────────┼───────┼───────────────────────────────────────────────────────────┤  │ Completed tasks in Done/       │ 17    │ No action needed (archive)                                │  ├────────────────────────────────┼───────┼───────────────────────────────────────────────────────────┤  │ Reports generated              │ 4     │ Read in Reports/                                          │  └────────────────────────────────┴───────┴───────────────────────────────────────────────────────────┘  Quick start right now:

  cd /mnt/e/AI_Employ_Vault/Bronce-tiar

  # Step 1: Process pending tasks
  ./run_gold.sh --once

  # Step 2: Check if any need approval
  ls Pending_Approval/

  # Step 3: Approve what you want (edit each file, change status to approved)

  # Step 4: Run again to execute approved actions
  ./run_gold.sh --once

  # Step 5: See results
  ls Done/
  cat Dashboard.md

  ---
  Typical Daily Workflow

  Morning:
    1. ./run_gold.sh --once          ← process overnight inputs
    2. ls Pending_Approval/          ← review approvals
    3. (approve/reject as needed)
    4. ./run_gold.sh --once          ← execute approved actions
    5. cat Dashboard.md              ← check status

  Or just leave it running:
    ./run_gold.sh                    ← runs continuously every 5 min
    (check Pending_Approval/ periodically to approve things)

