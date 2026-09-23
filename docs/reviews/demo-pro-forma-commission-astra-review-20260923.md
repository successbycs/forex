# Astra review: Demo pro-forma commission design

Date: 2026-09-23. Reviewer: Astra, independent read-only review. Verdict:
**NEEDS_REVISION**. No files, database rows, MT5 settings or broker orders were
changed by the review.

## Findings and disposition

1. HIGH — Original cost components can disagree with a repaired reconciled net.
   The original formula used gross/fee/swap fields while the current ledger can
   replace only net P&L through a reconciliation revision. Disposition: revise
   to `actual net − actual commission + modelled commission`, require a complete
   same-version source and an exact component consistency check; otherwise mark
   the projection unavailable.

2. HIGH — Original projection identity could freeze an open quote or conflict
   with repaired outcomes. Disposition: first release is closed-trade-only;
   identity now includes immutable profile version, calculation version and a
   canonical source fingerprint. Changed source creates a new projection.

3. MEDIUM — Profile status/effective-date selection could be ambiguous.
   Disposition: every profile version is immutable and explicit. First release
   supports only `ASSUMED_GO_PLUS_AUD_V1`; a future change is a successor and
   requires separate scenario-selection authority.

4. MEDIUM — Open positions lacked an attributable, timestamped valuation
   surface. Disposition: excluded from MVP; future support requires fixed
   position snapshots, freshness, volume and attribution evidence.

5. MEDIUM — Rounding, nonzero actual commission and broker fee display were
   underspecified. Disposition: define PostgreSQL numeric rounding per side,
   require tests for nonzero/repaired/partial data, and show actual broker fee,
   swap and commission separately.

The revised plan is
`docs/plans/demo-pro-forma-commission-design-review.md`. It remains a design;
it does not authorise implementation or alter the M32-proven Demo MVP.
