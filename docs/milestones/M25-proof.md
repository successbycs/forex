# M25 — human approval workflow

M25 binds an explicit named human decision to the exact advisory intent hash.
An acceptance is scoped, expires, and is only `APPROVED_FOR_FUTURE_REVALIDATION_ONLY`.
Any altered intent, missing operator, rejection, expiry, or non-actionable intent
fails closed. The module has no execution path; formal M25 closeout separately
requires the contract's real human review and sign-off.
