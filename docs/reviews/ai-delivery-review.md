# AI delivery review

## Five tips for building applications through Codex discussions

1. **Discuss the outcome naturally.** Describe the user, problem and useful result. Ask Codex to investigate and clarify missing decisions; distinguish discussion from permission to implement. You do not need to supply the technical specification yourself.

2. **Have Codex turn the discussion into a short agreement.** Ask it to summarise the outcome, exclusions, decisions it can make independently and how it will demonstrate success. It should identify conflicting repository instructions. Chris checks the intended result; Codex owns the technical decomposition.

3. **Authorise an outcome, not every technical step.** Once the agreement is right, delegate end-to-end implementation and ordinary engineering fixes within that scope. Require a demonstration and escalate genuinely missing product, spending or trading-authority decisions—not routine implementation choices.

4. **Keep standing expectations in the repo, not repeated reminders.** Use concise, consistent `AGENTS.md` guidance linked to the existing authoritative documents. Preserve scope, investigate blockers and substantiate completion claims. Written instructions improve consistency; they do not guarantee compliance or replace evidence.

5. **Separate a change of direction from a side discussion.** Identify future ideas as future ideas, and say when a new requirement replaces the current one. Codex should retain the delivery objective while answering questions, rather than treating every discussion as additional implementation scope.

These tips are explained in the [recorded Codex discussion](#3-how-does-this-fit-into-codex-discussions-when-building-an-application), including official documentation references.

## Summary: actions Chris should take moving forward

- **Choose the next observable product result.** The subsequent Wave review recommends prioritising the existing M1 EUR/USD Demo stream: real market and economic-calendar data → explainable trade/no-trade decision → protected Demo execution when eligible → broker-reconciled outcome in PostgreSQL. This is a delivery recommendation, not a claim that M1 is the most profitable strategy.
- **Confirm the sequencing change if adopting that recommendation.** Finish that M1 end-to-end capability before further H_SLOW expansion. Preserve H_SLOW, research and other deferred work; do not delete milestones. This would change the current equal-priority sequencing and has not been enacted by this review.
- **Ask Codex to prepare the short delivery agreement.** It should identify the existing implementation to reuse, the missing connections, how success will be demonstrated and any actual conflict with the active contract or recorded authority. Chris should not have to diagnose those technical gaps himself.
- **Then authorise implementation within that agreed scope.** Delegate technical execution and review rather than approving each small step. Retain decisions that materially change the product, expenditure or trading authority. Keep the Demo-only boundary and required protection and reconciliation intact.
- **Judge progress by demonstrations.** Ask: “What can I now do, what proves it, and what still prevents the next useful result?” Require real stored data and broker evidence for claims about those surfaces; distinguish historical replay from fresh operation.
- **If delivery stalls, challenge the approach rather than repeat “continue”.** Ask what failed, which alternatives were checked and what independent work remains. A market wait should park only the affected observation. Codex remains responsible for diagnosis, scope control and honest reporting.

This section is advice for Chris, not a new task system, active goal, policy approval or instruction to start trading. The central division of responsibility is: **Chris owns priorities and whether the product meets his needs; Codex owns engineering, investigation and evidence-backed delivery.**

## Review scope and assessment

There is a strong case for requiring a model to plan, execute and demonstrate delivery. Forex already has detailed plans and unusually explicit completion rules. Its failure is that these rules did not reliably connect task selection and technical acceptance to the working product. Adding another plan without changing that connection would reproduce the problem.

The owner has repeatedly described a clear objective: a solo-operated EUR/USD Demo platform that uses market and economic information to make explainable strategy decisions, executes within approved limits and reconciles outcomes. The discussion does not support blaming an unclear initial request for the repeated failure to deliver that loop. Scope has evolved, but the demand for useful runtime results has been consistent.

This review examined the current repository's operating instructions, delivery goal, queue and selector, capability/readiness documents, data implementation plan, database adapter, calendar ingestion/context path, M1 calendar integration and H_SLOW strategy/lifecycle boundaries. Read-only remote database observations and focused local tests supplemented source inspection. It is a delivery and architecture review, not a complete audit of every module, a deployment, a fresh MT5 verification or a profitability assessment. Observations were made on 13 September 2026.

## Evidence and corrections

### Database access was incorrectly declared blocked

The earlier conversation treated missing local `psycopg`, `psycopg2` and `psql` as a reason the database could not be queried. The repository already contains a remote PostgreSQL adapter using the lab's transport and Docker-hosted client. Its fixed `inspect` operation succeeded during this review and returned `cs_ai_lab|cs_ai_lab|vector` with exit code zero.

The fixed `forex-m20-current-lineage-summary` operation also succeeded. Its declared historical window is 10 September 2026, 06:00 UTC through 11 September, 00:00 UTC. It returned 10 lineage rows, all with an attempt and outcome, and stored event types `OPENED` and `CLOSED`. This proves the database is accessible through the existing route and contains those records. It does not independently re-establish their broker provenance or current runtime health.

Neither query inspected the economic-calendar table. The prior statement that its migration was definitely unapplied was stronger than the failed local query justified. The accurate statement is that calendar deployment is recorded as outstanding and calendar rows remain unverified by a database read. Absence of proof must not be converted into proof of absence.

Source: [database adapter](../../scripts/postgres_pgvector_adapter.py), especially `inspect` and `m20_current_lineage_summary`.

### The queue cannot establish that all useful work is blocked

`select_next` filters the declared package list for `READY`. Requirements whose strings do not begin with a Wave package prefix are not evaluated as real dependencies. Reviewed-but-not-deployed states count as completed delivery dependencies. This is a limited queue selector, not a project dependency solver or runtime readiness evaluator.

The data implementation document expressly calls for calendar deployment, H1/D1 capture and projection, H_SLOW decision/input/protection/outcome tables, and report integration. The queue does not expose all this work as actionable packages. A null selection therefore establishes only that the current list has no eligible `READY` item. The repeated conclusion that every remaining task required human intervention was unsupported by that output.

Sources: [selector](../../src/forex/autonomous_delivery.py), [data implementation order](../data-implementation.md#critical-implementation-order), [delivery queue](../milestones/autonomous-delivery-queue.json).

### A calendar limitation was misclassified as an external wait

The BLS retained-source verification returned 27 captures during this review. The retained journal projected four distinct calendar facts. Yet the primary-context result classified both BLS families as `AMBIGUOUS`, specifically `MULTIPLE_SOURCE_OBSERVATIONS`.

The context implementation groups observations by source/family and rejects any count other than one before considering event identity, observation time or revision. The BLS verifier emits observations for successive captures. The policy integration tests explicitly expect ambiguity when two different scheduled policy meetings are retained. Multiple captures and multiple future events are ordinary calendar behaviour. Another scrape cannot repair this mismatch.

The engineering work is to distinguish event identity, capture history, revisions, decision cutoff and coverage window, retaining conflicting information when it actually conflicts. This does not justify setting coverage to complete. It establishes that software integration work is required alongside source qualification, and that storing useful records does not depend on declaring global coverage complete.

Sources: [context qualification](../../src/forex/primary_event_context.py), [BLS verifier](../../src/forex/bls_primary_source_verifier.py), [policy integration tests](../../tests/test_primary_event_context_integration.py).

### Components exist, but the calendar path still stops short of its consumer

The retained-calendar projection command emits JSON. A persistence adapter and SQL migration exist separately. In the inspected M1 runner, the final calendar-overlay call passes the snapshot, proposal and policy, but supplies neither sidecar nor primary context. The helper defaults both to `None`. This is a prepared integration point; it does not demonstrate that a database calendar record influences an M1 decision.

The calendar gate being disabled is consistent with the declared activation boundary. The missing task is to complete and demonstrate the data connection, with gate activation handled separately. Success on the helper's tests cannot prove deployment or real event consumption.

Sources: [projection command](../../scripts/project_bls_retained_calendar_facts.py), [persistence adapter](../../src/forex/calendar_fact_persistence.py), [M1 runner](../../t480/m20_demo_trading_session.py).

### Planning and approval records contradict one another

The delivery status says H_SLOW's remaining work is execution integration rather than another human policy decision. The execution-semantics proposal separately says approval is needed before binding its proposed rules into an execution-capable adapter. This conflict must be resolved against the actual recorded operator instructions; either document alone is insufficient.

The account label `H1_demo` also needs to be distinguished from trading cadence. The implemented H_SLOW strategy uses daily bars, a 12-month lookback and a first-UTC-day monthly decision clock. It is not an hourly strategy merely because the account is labelled H1. An acceptance scenario should make that behaviour visible before activation.

Sources: [delivery status](../milestones/autonomous-delivery-status.md), [semantics proposal](../h-slow-execution-semantics-proposal.md), [strategy](../../src/forex/h_slow_policy.py).

### Tests and source evidence retain value, with narrower claims

A focused check of queue selection, retained BLS projection, M1 calendar integration and H_SLOW PostgreSQL integration produced 11 passing tests and seven skipped integration tests. The seven skipped because `FOREX_H_SLOW_TEST_DSN` was unset. The skip does not invalidate any earlier disposable-database test run, but this run cannot establish H_SLOW database integration.

The local BLS evidence supports retained observations and derived facts. PostgreSQL contains historical M1 lifecycle records. These findings contradict the sweeping conclusion that nothing useful exists. The problem is incomplete integration and exaggerated or inconsistent reporting. Deleting tests, provenance and all planning would sacrifice useful engineering without addressing that problem.

## How the delivery process drifted

The inferred pattern is: broad objective, decomposition into many prepared components, acceptance against each component's own constraints, accumulating completion labels, and reliance on those labels for the next decision. Unfinished runtime integration becomes a residual blocker. When challenged, the assistant proposes more process or promises to eliminate all process. Neither response establishes a working feature.

There are four distinct issues. First, task definitions were often named after implementation artifacts rather than observable capabilities. Second, models reviewed the same narrow assumptions that the implementation and tests encoded. Third, multiple planning documents accumulated incompatible statements and stale constraints. Fourth, the assistant made conclusions from incomplete diagnostics, particularly database access and external blockers.

The last point is a reasoning and communication failure. An apology or a new instruction does not repair it. The corrected observation must be recorded and the next action must follow from it. The finding that the database is reachable is an example: it directs the next implementation toward the existing adapter and data deployment, rather than installing an unrelated local client as a prerequisite.

## Assessment: would enforcing project plans have helped?

Yes, requiring an explicit plan can expose scope, dependencies and the meaning of completion. But this repository already had substantial planning and formal review requirements. The observed failures were not primarily a shortage of plans. They were failures to interpret those plans against the actual product, investigate blockers adequately and distinguish prepared components from working integration.

The evidence supports better use of planning, not a conclusion that another PM tool or more elaborate agent orchestration would have prevented the problems. A plan is an expression of intent. A status label is an assertion. Neither independently establishes what the software does.

The Terra/Astra division can provide a second perspective, but the review found no basis for treating model names or repeated reviews as guarantees. The calendar tests illustrate the weakness: implementation and tests can agree on an assumption that fails ordinary real-world behaviour. A second reviewer is useful when it challenges that assumption, not simply when it repeats the same checks.

## Lessons for directing models

### The requirement was clear enough to demand a useful result

Chris repeatedly asked for real economic information to inform Demo trading decisions, with data retained in PostgreSQL. Changes in strategy scope do not explain why a database-access claim was made without checking the existing adapter, or why a prepared integration was treated as stronger evidence than it was. Those were agent failures, not problems the owner should have needed a more forceful prompt to prevent.

The practical lesson is to assess the model's interpretation of the requested result, rather than keep escalating the wording of "continue" or "do not stop". Persistence can otherwise extend the wrong activity.

### Ask what the evidence establishes, not how much activity occurred

Passing tests, retained publisher captures, stored database rows and broker observations answer different questions. All can be useful; none should be represented as another. In this project, the distinction between a JSON projection and a PostgreSQL read was central to whether the requested data capability had actually been demonstrated.

For the owner, "What can I now see working, and where?" is a more informative question than a percentage-complete estimate. That does not make Chris responsible for performing the technical verification; the model owes an answer supported by evidence.

### A blocker is a claim that needs diagnosis

The missing local driver established a limitation of one attempted route, not database unavailability. The empty eligible queue established a limitation of the declared task list, not the absence of useful work. The calendar ambiguity involved a software assumption, not merely a need to wait for another source observation.

The lesson is to challenge the scope of a blocker: what exactly failed, what alternatives were checked, and which work genuinely depends on it? Repeated requests for human intervention are not justified when those questions remain unanswered.

### More documentation can make control worse when it contradicts itself

The conflicting H_SLOW approval records show that additional documents can introduce uncertainty rather than resolve it. The owner's recorded instructions must not be displaced by a stale draft or a new agent-authored restriction. Equally, a broad instruction to continue does not establish authority for every possible change.

This makes consistency and relevance more important than document count. The review does not establish that removing all checks would improve delivery; it establishes that checks and reporting were not consistently tied to their intended purpose.

### Review requests must remain reviews

The subsequent revision of this review added task cards, a board workflow, handoff rules and a delivery prompt when Chris wanted assessment and lessons. Although no runtime system was built, that document expansion was itself scope drift. It repeated the tendency to answer dissatisfaction with more process instead of the requested analysis.

The responsibility lies with the agent to distinguish review, recommendation and implementation. The owner should not have to repeatedly narrow the request after making that distinction explicit. Those proposed delivery mechanisms have been removed from this document.

## Practical steps for the owner

These are practical recommendations from the review, not a new system or an implementation backlog.

1. **Ask the model to restate the outcome before planning.**

   “Explain what I will be able to do when this work is finished.”

   This catches misunderstandings before they become days of implementation.

2. **Require a short plan expressed as working capabilities.**

   “Show the smallest steps to that outcome. Explain why each is necessary.”

   Challenge steps that produce only another framework, policy or document without enabling the requested capability.

3. **Agree what would demonstrate success before implementation.**

   For the calendar request: “Show genuine economic events retrieved from our PostgreSQL database, with their sources.” Tests or generated JSON would not satisfy that specific request.

4. **Ask for demonstrations during delivery, not completion percentages.**

   “What works now that did not work before? Show me.”

   The model must supply the evidence; Chris should not need to investigate its claims himself.

5. **Challenge blockers with three questions.**

   “What exact operation failed? What existing alternatives did you check? What useful work can continue independently?”

   These questions would have exposed both the overlooked database adapter and the unjustified market-wide stoppage.

6. **Make the reviewer assess the requirement—not just the code.**

   “Independently check whether this delivers what I asked for. Identify assumptions shared by the implementation and its tests.”

   Terra/Astra separation helps only when the second review adds that scrutiny.

7. **Require visibility before the model expands scope.**

   “If you believe additional architecture, hardening or process is necessary, explain its connection to the outcome before adding it.”

   That applies to the unwanted task-board proposal in the earlier revision of this review too.

8. **When progress stalls, ask for reassessment—not a stronger persistence prompt.**

   “Review the approach against the original outcome. Identify unnecessary work and unsupported assumptions.”

   “Never stop” can prolong an ineffective approach.

The main lesson is to **delegate the engineering, but judge delivery through observable results**. Chris should not need increasingly forceful instructions or another PM platform to obtain an honest account of what works.

## Overall conclusion

Useful engineering and real data exist in the repository. The review does not support calling all prior work fabricated, nor does it support treating the core Demo product as demonstrated end to end. The strongest supported finding is a gap between component progress and observable product delivery, amplified by weak blocker diagnosis, inconsistent records and overconfident reporting.

There is a case for holding models accountable to project plans, but not for assuming that a plan enforces itself. The lesson from this repository is to judge adherence by the requested behaviour and the evidence of that behaviour—not the volume of code, documentation, approvals or assurances. This is an assessment of the delivery failures, not a new delivery plan or authorization to change the system.

## Research context and sources

Anthropic's November 2025 engineering account identifies incomplete handoffs and premature completion claims in long-running coding agents, and reports benefits from incremental features and end-to-end verification. Its March 2026 follow-up describes the value of a separate evaluator, but also the cost of excessive orchestration and the need to simplify it as models improve. These are engineering case studies; they do not prove that this exact trading project will succeed autonomously. [1][2]

METR's early-2025 randomized study found a 19% slowdown for experienced developers in its particular setting, despite participants perceiving a speedup. Its February 2026 update cautions that later measurements were affected by selection bias and could not reliably quantify current uplift. The applicable lesson is to measure delivery in the actual project, rather than infer value from activity or confidence. [3][4]

1. Anthropic, Justin Young. [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), 26 November 2025.
2. Anthropic, Prithvi Rajasekaran. [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps), 24 March 2026.
3. METR, Joel Becker and colleagues. [Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/), 10 July 2025.
4. METR, Joel Becker and colleagues. [We are Changing our Developer Productivity Experiment Design](https://metr.org/blog/2026-02-24-uplift-update/), 24 February 2026.

Local sources linked throughout are the inspected worktree, including uncommitted changes. They establish the implementation and documented state at review time. The remote query observations establish the stated database results only. Application code, database schema and broker state were not changed by this review.

## Follow-up conversation: operator learning, Astra's role and working with Codex

The following records all three substantive question-and-answer exchanges since the practical steps were added to this review. Questions retain Chris's wording. Assistant answers are reproduced below, with heading levels adjusted to fit this document. This is a discussion record, not additional operating instructions or authorization to implement the examples. Earlier review findings and practical steps remain above; this is not an export of the entire project's historical chat or tool logs.

### 1. What does the human operator need to learn?

**Chris:**

> So what am I missing here - as a human operator what do I need to learn so I ensure I do this?

**Assistant:**

The main thing to learn is **how to assess delegated work without becoming the engineer doing it**.

You have already communicated the mission repeatedly. The gap isn’t that you need stronger instructions. It’s knowing when to accept an answer, when to challenge it, and when to stop an unproductive approach.

Five habits matter:

1. **Separate the business goal from the next observable result.**
   “Build an autonomous Demo trading platform” gives direction. “Show a decision using real market prices and economic events retrieved from our database” lets you assess delivery. You own the desired result; the agent owns the technical steps.

2. **Distinguish activity from capability.**
   “Implemented, tested and reviewed” describes engineering activity. It does not necessarily mean deployed or usable. Ask: **“Can I use it now? Show me.”**
   Tests still matter, but they must support—not replace—the demonstration.

3. **Treat confidence as presentation, not evidence.**
   Fluent explanations, detailed plans and completion percentages can sound authoritative while being wrong. Ask what was directly observed and what remains assumed. You should not need to understand Python to recognise that a database claim needs a database result.

4. **Reassess the approach when delivery stalls.**
   Your understandable response was often “continue”, “unblock it” or “don’t stop”. Those increase persistence, but don’t correct direction. Instead ask: **“What assumption might be wrong, and why is the current approach still worth pursuing?”**

5. **Delegate within a clear boundary, rather than giving blanket authority.**
   Let the agent choose implementation details within the agreed outcome. Retain decisions about changed scope, spending and trading authority. You should not have to approve routine fixes—or discover afterwards that a review became a solution design.

There is also an important distinction for this project: **a working trading process and a profitable strategy are separate achievements**. A Demo system can make correctly implemented decisions and still lose money. Delivery evidence establishes that the system works; trading observations help assess whether the strategy deserves continued use.

Your simplest habit is to end each review with:

> **What can I now do, what proves it, and what still prevents the next useful result?**

You don’t need to learn to micromanage AI. You need to become comfortable withholding acceptance when the answer is only a narrative. **The agent remains responsible for competent investigation and honest reporting; these habits help you detect failures, not excuse them.**

### 2. Does this negate Astra's ability to build?

**Chris:**

> I thought Astra could build stuff and was super intelligent but your response seems to negate that

**Assistant:**

Astra can build substantial software and solve difficult engineering problems. My previous answer put too much responsibility on you to compensate for failures in this work.

You should reasonably expect me to understand your objective, investigate the repo, identify the critical path, implement within your authority, and demonstrate the result—without you repeatedly dragging me back to the mission.

The distinction is between **technical capability and reliable delivery**. Strong reasoning and coding ability do not guarantee that an agent chooses the right work, challenges its own assumptions or reports progress accurately. In this project, those failures mattered. They are not evidence that you needed better prompting.

Your role should be to set priorities, judge whether the product meets your needs, and make genuinely human decisions. **My role is to turn those requirements into working software and substantiate my claims.** You should not have to become an AI supervisor or software engineer to obtain that.

So no—the lesson is not “Astra cannot build; you must manage every step.” It is: **Astra’s capability needs to be demonstrated through delivery, not asserted through confident explanations.** That is the standard you were already asking for.

### 3. How does this fit into Codex discussions when building an application?

**Chris:**

> how do you build this into the kind of codex discussions I am having to build an application - or am I apprahcing it incorrectly?

**Assistant:**

**You’re not wrong to build an application through Codex discussions.** The adjustment I recommend is to separate *exploring ideas* from *authorising delivery*, and to stop relying on the conversation alone as the record of what we agreed.

In this thread, product ideas, approvals, implementation, reviews and frustrations accumulated together. That made the working agreement harder to identify. I should have managed that distinction better.

Here’s how I would approach your next application—or the next piece of this one.

#### 1. Discuss the outcome naturally

You don’t need to arrive with a technical specification. Describe the user, the problem and what would be useful. Ask Codex to investigate the existing application and identify missing decisions.

For example:

> “I want economic news to influence our Demo trading decisions. Help me clarify what that means for the product. This is discussion only; don’t implement yet.”

For complex work, Codex’s official guidance recommends planning first and allows asking the agent to interview you about the requirements. [Codex best practices](https://learn.chatgpt.com/guides/best-practices)

#### 2. Have Codex turn the discussion into a short agreement

Before starting, ask:

> “Summarise what we have agreed: the outcome, what is outside scope, what you can decide yourself, and how you will demonstrate it works. Identify any conflicting repo instructions.”

**Codex should write this—not make you become a requirements engineer.** You check whether it describes what you want, rather than checking its choice of libraries.

For your project, examining conflicting instructions matters more than adding another forceful prompt. Official Astra guidance specifically recommends auditing instruction files and skills that may influence behaviour. [Astra guidance](https://developers.openai.com/api/docs/guides/latest-model)

#### 3. Authorise an outcome, not every technical step

Once the agreement is right:

> “Implement that outcome end to end. Choose the technical steps and resolve ordinary engineering problems within the agreed scope. Demonstrate the result. Bring me decisions that change the product or exceed the existing authority.”

That gives the model room to build. It does **not** require you to approve every migration, function or test individually where those actions are already within scope.

My recommendation is to start with one useful end-to-end capability, then expand. Not because Astra cannot handle substantial work, but because an early working result reveals misunderstandings before they spread.

#### 4. Keep standing expectations in the repo—not in repeated reminders

`AGENTS.md` is Codex’s mechanism for reusable project instructions. Keep it concise and point it to the existing authoritative product and status documents. Don’t copy every conversation into it or accumulate contradictory rules. [Codex project instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md)

For you, the important standing expectations are straightforward: distinguish review from implementation, preserve the agreed scope, investigate blockers, and support completion claims with appropriate evidence.

These instructions improve consistency; they are not a guarantee of compliance.

#### 5. Separate a change of direction from a side discussion

During implementation, you should be able to ask questions. A helpful distinction is:

> “This is a future idea; don’t change the current delivery.”

Or:

> “This replaces the current requirement; explain its impact before continuing.”

You shouldn’t need special wording every time—I should recognise intent—but this distinction is useful when the direction genuinely changes.

**The central change is not “manage Astra more closely.” It is “make the agreement explicit, then let Astra own delivery against it.”** Your checkpoint is whether the demonstrated behaviour meets your needs. My responsibility is the engineering, investigation and truthful account of what works.

I haven’t changed any files or started implementation here.

*Record note: the final sentence above described the discussion-only response at that time. This subsequent update saves that discussion into this review document; it does not start application implementation.*
