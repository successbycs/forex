# M31 short-window capture assessment

This is an implementer assessment, not independent approval or formal proof.

The live worker session 62713 finished with exit 0. The retained bundle is
`runs/evidence/M31/mvp-20260923T012500Z-afce837`, evaluated by revision
`afce837c1b51d252761542ee05cab43ac1a89166`. Its declared interval was
2026-09-23T01:15:00Z inclusive through 01:25:00Z exclusive. It contains ten
PostgreSQL decisions, all NO_TRADE, and zero selected/closed outcomes.
The raw bundle remains unchanged.

The capture script required the retained protocol's from_utc and to_utc values
to be supplied as environment variables by the waiting worker: its embedded
Python does not export those variables to the parent shell. The worker supplied
only the exact retained bounds. Repair this orchestration defect before reuse.

The existing verifier passed hash and deterministic-scorecard checks, but that
does not establish M31-C1 through C4. The scorecard reports UNKNOWN application
revision/configuration and an empty limitations list. It lacks decision refusal
reasons, comparable historical baseline evidence, and a demonstrated broker-to-
ledger cross-check. The manifest lacks the registry's configuration and full
proof metadata. These are required evaluation repairs, not reasons to extend
the observation interval or force trading. Reuse retained data where adequate;
do not rewrite the declaration or manufacture performance evidence.

At 2026-09-23T02:05:21Z the fixed latest-assessment operation reported fresh
quotes, completed M1 candles, normal spread, and active lease, but
no_existing_position=false. The fixed m20_listener_account_identity operation
confirmed four open positions on GOMarketsMU-Demo/AUD, account scope
sha256:4b12a2cebac68fadc4009c52f46e1cda20bd3c731ef94428ed2b47a2d29faabf.
The runner sets this gate from visible EURUSD positions. This establishes a
current entry blocker; it does not establish individual ownership or protection
of those positions. Earlier claims that lack of setups alone explained the
absence of trades were incomplete. No positions were changed.

Next work: identify existing position ownership through fixed read-only
evidence; repair evaluation omissions and obtain independent review. M31
remains unproven and M32 remains gated. A ten-minute NO_TRADE capture proves
observed decision persistence, not the entire requested outcome evaluation.

Follow-up from the retained broker history: positions 43135808, 43135809,
43135810, and 43135811 each have one BUY entry of 0.02 EURUSD at 1.14518,
magic=0, reason=0, and no matched opening-context position identifier in the
retained listener lifecycle extract. Their signed remaining volumes are each
0.02 lots in that history. This supports desktop-origin/manual attribution,
not identification of the person who submitted them. The raw broker timestamp
is 1790124764; using the export's declared +10800-second offset gives
2026-09-22T21:52:44Z (09:52:44 NZST on 23 September).
MetaQuotes documents desktop-origin deals under DEAL_REASON_CLIENT:
https://www.mql5.com/en/docs/constants/tradingconstants/dealproperties
No operator position is to be closed or adopted by the strategy without a
specific operator instruction. That decision does not block local evaluator
repairs. The capture launcher now explicitly reads validated interval bounds
into its parent shell rather than depending on ambient environment variables.

Repair update: supplemental v2 data recovered all ten original decision rows
unchanged, adding consistent runtime/configuration/strategy provenance and
Demo/EURUSD/M1 session scope. The raw refusal text is generic; it does not
identify the existing-position gate for each interval decision. Broker history
confirms zero EURUSD deals during the declared interval. The historical
NO_CHANGE source is retained as a null-policy comparison, not an active H1/M1
performance comparison. See `m31-retained-evaluation-review-2026-09-23.md`
for the separate successful repair review and exact reviewed code hashes.
