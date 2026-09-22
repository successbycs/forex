# Deliver the operator workflow dashboard

## Purpose and scope

Implement the design in docs/listener-operator-view.md under PLANS.md. Chris
can run `python3 scripts/m20_listener_dashboard.py` in VS Code and follow price,
assessment, decision, execution and reconciliation in one full terminal view.
This is local read-only presentation work within active M30. Existing M20
readers and M30 Wave 3 exact-identity evidence semantics are reused. M29's
approved topology exception remains unchanged; no recovery proof is claimed.
M30 still requires its natural protected lifecycle, verification and formal
review; this UI cannot close it. Web and Discord delivery are deferred.

## Progress

<!-- forex-work-projection:start task=LISTENER-WORKFLOW-VIEW schema=forex.execution-work-projection.v1 -->
<!-- forex-work-item id=implementation state=DONE -->
- [x] implementation — Build and verify the workflow dashboard (DONE)
<!-- forex-work-projection:end -->

## Context and implementation

The existing dashboard script owns the command and full candle/context detail.
The evidence-view script reads the fixed latest-assessment export; the ledger
script reads the fixed PostgreSQL lifecycle summary. Add scripts/listener_workflow_report.py
to collect these and the deployed-account identity with bounded waits, then
build a JSON-serializable report without broker mutation. Render five numbered
stages, independent active/history rows, source fetch times and missing-data
warnings. Only enrich risk from the exact same proposal. Preserve full existing
details below the workflow. Wrap output to terminal width and expose --json for
future presentation consumers. No new dependencies or remote deployment.

## Acceptance and concrete steps

From /home/chris/projects/forex run focused pytest checks for the dashboard,
ledger, evidence view and new report. Exercise mismatched identities, an older
open trade alongside NO_TRADE, stale/unavailable observations, accepted/rejected
execution and verified/unverified outcomes. Run the dashboard --once and --json
against existing read-only sources; inspect source errors explicitly. Width 60
must preserve text without overflowing lines. Run git diff --check and milestone
validation. Obtain a separate read-only code review before marking complete.
Owned paths are this plan, the design, the dashboard, new report, and report tests.

## Recovery and evidence

All reads can be repeated. Stop with Ctrl+C. Roll back only the local dashboard
integration if needed; existing individual views remain available. Never clear
or modify evidence. A failed read shows UNKNOWN; historical protection and
balance changes never prove current protection or a trade's profit.

## Decisions and discoveries

2026-09-22: Preserve the existing command and full detail renderer. Build a
plain report model to support later web/Discord renderers. Use fresh reads per
refresh rather than caching old values, eliminating silent stale reuse.

## Surprises & Discoveries

The live ledger includes 45 historical/unresolved rows. Summarising their count
keeps the header usable without claiming these are current positions. The live
view showed three closed verified trades (+0.27, +0.18, +0.10 AUD). A subsequent
read encountered T480 timeouts and correctly kept the ledger visible while
marking remote sources unavailable. A later JSON read succeeded with listener
state WAITING_FOR_FRESH_MT5_QUOTE and 106 ledger rows. These are observations,
not M30 closeout evidence. Quote, forming candle, size and risk fields can be
UNKNOWN because the existing sources omit them.

## Outcomes & Retrospective

Implemented the existing command with numbered workflow stages, full original
detail, source warnings, local times, independent trade history, exact proposal
risk joins and reusable JSON output. Normal and 60-column live outputs inspected.
Focused tests passed; final check count recorded in the task JSON. Separate
read-only reviewer /root/view_review identified stale-warning, source-error,
outcome detail and numeric P&L issues; all were repaired. Unrelated adapter edits
were preserved. No deployment or formal milestone change was needed.

Revision note 2026-09-22: updated progress and outcomes after implementation,
live observation and reviewer-directed repairs. This task does not complete the
ongoing M30 trading goal.
