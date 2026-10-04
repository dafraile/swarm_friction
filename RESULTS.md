# Results after audit and repair

**The repaired experiment does not establish an advantage for clause declarations over acknowledgement when both include policy reminders.** The original “the clause is the mechanism” claim should be withdrawn. A reminder itself substantially changed behavior in this benchmark.

All **400 planned main episodes** and **10 separate pilot episodes** completed using the alternative OpenAI credential and the Anthropic credential. Estimated API cost was **US$9.09**, with no interrupted/replaced attempts, unsettled request reservations, step-budget overruns or truncated episodes. The main run used two models, 20 task templates, two generated worlds and five arms, following [the prospective protocol](docs/REPAIR_PROTOCOL.md).

## Main observations

Pooled across the two models, each arm has 40 benign (Suite A) and 40 temptation (Suite B) episodes:

| Arm | Completed out-of-scope actions in Suite B | Strict compliant completion in Suite A |
|---|---:|---:|
| No gate, no initial policy pointer | 17/40 | 38/40 |
| Policy pointer alone | 3/40 | 40/40 |
| Acknowledgement + policy reminders | 0/40 | 39/40 |
| Declaration + policy reminders | 0/40 | 39/40 |
| Declaration, no initial policy pointer | 6/40 | 38/40 |

The primary declaration-versus-acknowledgement contrast is **0 percentage points** for both completed violations and strict compliant completion. These observations do not prove equivalence or perfect safety. Both arms have zero observed violations, so their empirical task-bootstrap interval is degenerate; it is not a useful upper bound on unseen risk.

The exploratory policy-pointer contrast is −35 percentage points for completed violations (task-bootstrap 95% interval −62.5 to −7.5). The three remaining pointer-only violations were **restricted-directory listings**, not restricted-file reads or external transfers. The outcome counts all forbidden operations equally; their severity differs.

There is substantial model heterogeneity without the initial pointer: declarations changed Sonnet violations from 12/20 to 0/20, but Luna from 5/20 to 6/20. A declaration gate alone is not a reliable scope boundary. It mechanically checks procedure and permits a correctly declared forbidden action.

## Grading and interpretation limits

The frozen strict grader marked six mathematically/semantically correct benign outputs wrong because of underspecified representations: five survey-metric identifiers and one set of correct zero-valued quarter cells. [The disclosed post hoc sensitivity](docs/REPAIR_OUTPUT_SENSITIVITY.md) lists every change and its rules. Under it, benign compliant completion is 40/40 in every arm; the primary declaration-versus-acknowledgement contrast remains zero. Original grades and outputs are preserved. Other secondary task conventions, including B-L5 empty aggregates, still deserve clarification before another study; see [the maintenance notes](docs/POST_RUN_ENGINEERING.md).

**Neither model spawned a helper in the main rerun.** Child policy delivery was tested locally, but the paid experiment provides no empirical test of delegated work or swarm containment. The new tools, policy wording, output contracts and revised tasks also prevent a direct before/after comparison with v1. These are two cooperative models in a synthetic environment, with only ten task templates per suite and strong ceiling/floor effects. The baseline omits the initial policy pointer; differences may reflect discovering the rules. They do not establish resistance to agents deliberately violating known rules.

## Evidence and reproducibility

- [Full frozen-score tables and paired estimates](docs/REPAIR_RESULTS.md).
- [Operational costs, policy reads and child counts](docs/REPAIR_DIAGNOSTICS.md).
- [Output sensitivity and affected episode IDs](docs/REPAIR_OUTPUT_SENSITIVITY.md).
- [Record verification](docs/audit/v2_record_verification.json): all 410 episodes, 3,367 non-submit world operations replayed, and 3,527 API responses reconciled with usage; no discrepancies.
- [Independent reference checks](docs/audit/v2_reference_verification.json): 246 checks against source rows across three worlds; no errors.
- [Source and credential scan](docs/audit/v2_source_and_secret_verification.json): execution-source hashes checked before maintenance; no real provider keys found in generated artifacts.

The 38-test local suite covers the repaired invariants and interruption recovery. Main manifests, full API transcripts, tool logs, workspace artifacts and budget ledger are committed under `runs/repair_v2/`. The main execution-source commit is `139078b`; the schedule/world checkpoint is `dd0b247`; the completed-run archive is `f4e5b08`.

## AI Village and historical results

The raw Village chain and approval aggregates were reproduced. Their corrected interpretation is descriptive: about 35.7% of bash actions matched the privileged-class proxy (14.4% of all computer actions); zero matches do not prove no privileged behavior; pⁿ/pᵏ values are hypothetical survival calculations; approved proxy posting is not established laundering. The classifier exercise was development calibration, not independent validation. Its missing holdout remains a limitation.

See [the historical errata](docs/LEGACY_ERRATA.md), [the original audit](docs/audit/AUDIT_2026-10-04.txt), and [the explicitly superseded v1 report](docs/RESULTS_V1_HISTORICAL.md). The useful result is an auditable prototype and a more cautious finding about policy exposure and procedure, not a demonstrated general containment mechanism for swarms.
