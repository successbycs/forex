# Golden principles

## 1. Preserve architecture boundaries
- UI must not directly access databases or external APIs.
- Business rules belong in services.
- External systems are accessed through providers/adapters.
- Data persistence is accessed through repositories.

## 2. Prefer proven shared utilities
- Check existing dependencies and internal utilities before writing a helper.
- A new helper must have a specific owner and tests if it encodes an invariant.
- Do not duplicate validation, date, ID, retry, logging or error-handling logic.

## 3. No guessed data shapes
- Do not infer API/database/file shapes from examples alone.
- Validate inputs at boundaries.
- Prefer generated clients, typed SDKs, schemas and explicit contracts.
- Record any unknown or unverified field as an assumption in the Plane issue.

## 4. Evidence before completion
- No issue is Done without changed-file summary, test results and verification evidence.
- Material changes require a rollback note.
- Keep changes scoped to one Plane issue.

## 5. Safe agent behaviour
- Never expose secrets, alter production data or run destructive commands without explicit approval.
- Prefer small, reversible commits.