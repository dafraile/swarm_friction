# Auditing procedural controls for agent tool use

**AI Swarm Dynamics Hackathon, October 2026. David Fraile Navarro, Macquarie University.**

This project builds a procedural broker and forensic log for agents operating in a synthetic analytics platform. A gate can require a declaration, bind it to the eventual tool and target, and require a policy-clause citation without deciding whether that action is permitted. A separate logger records the scope label after the fact. This makes procedural compliance and actual policy compliance independently inspectable.

The initial experiment appeared to favor declarations over a simple acknowledgement. An independent audit found policy-reminder confounding, permissive graders, incorrect global step accounting, credential-use bypasses, inadequate policy delivery to children and incomplete attempt accounting. Those findings are preserved in `docs/audit/AUDIT_2026-10-04.txt`; historical results are explicitly superseded by `docs/LEGACY_ERRATA.md`.

## What was repaired and rerun

The repaired harness enforces one episode-wide step budget; requires issued credential tokens and gates credential use; binds tickets to their requesting agent; attaches full policy text to children; supports reproducible computation over the data; and retains full responses, tool arguments, final files and interrupted attempts. Paid requests reserve costs before they are sent, using a shared durable ledger. The scope oracle remains outside gate decisions.

A prospective protocol fixed 400 main episodes: 20 task templates, two synthetic worlds, two models and five arms. A separate ten-episode technical pilot was excluded. All episodes completed for an estimated US$9.09, with no runtime interruptions, step overruns or replacements. All 410 records were checked by offline replay and API-usage reconciliation, and 246 reference checks passed against the source data. Source snapshots, schedules, prompts and raw records are in Git.

## What the repaired experiment shows

In Suite B, pooled across models, completed out-of-scope actions occurred in 17/40 baseline episodes and 3/40 with a policy pointer alone. The remaining pointer-only events were restricted-directory listings. Both acknowledgement-plus-reminder and declaration-plus-reminder had 0/40 completed violations. Their strict benign-task completion was also identical at 39/40.

**The declaration-specific mechanism claim is not supported.** The primary contrast against an acknowledgement with policy reminders is zero for both outcomes. A zero-event interval does not establish perfect safety or equivalence. The exploratory policy-pointer contrast is −35 percentage points (task-bootstrap 95% interval −62.5 to −7.5), based on only ten task templates per suite.

Without an initial policy pointer, declarations changed Sonnet violations from 12/20 to 0/20, but Luna from 5/20 to 6/20. A correctly declared forbidden action can pass a content-blind gate. This is a procedural control whose behavioral effect depends on the model and policy exposure, not an authorization boundary.

The frozen strict grader also rejected six equivalent benign representations. A disclosed post hoc sensitivity raises benign completion to 40/40 in all arms without changing any violation count or the primary contrast. These adjustments are listed individually rather than silently substituted for the original scores. API effort and procedure costs remain visible in the operational diagnostics.

Neither model spawned a helper during the main rerun. Therefore the live results concern tool-using agents, not demonstrated swarm containment or empirical policy transmission. New tools, clearer policy and revised task contracts also prevent direct comparison with the original numerical rates. A study of delegated work, independently authored tasks and stronger adversarial settings remains future work.

## The forensic contribution

The log records identity within each episode, tool and target, declared intent, tickets, gate outcomes, execution, scope labels and full outputs. It can distinguish a denied request, an executed forbidden action, a procedural declaration and a correct result. The logs support deterministic replay without asking an LLM judge to infer what happened from a narrative.

The same auditing approach was applied descriptively to AI Village data. Raw aggregates were reproduced, but interpretation was corrected: 14.4% used all computer actions as its denominator, while about 35.7% of bash actions matched the proxy; GUI actions were unclassified; P4 included processes as well as agents; pⁿ/pᵏ values were hypothetical, not measured throughput. Nine of ten disclosed proxy-posting requests were approved, which does not establish evasion. Classifier accuracy figures came from development calibration and lack an independent holdout.

## Use of the AI Village data

The dataset was used two ways, both descriptive and both reproduced by the audit (`docs/AI_VILLAGE_CHAINS.md`, `docs/AI_VILLAGE_FORENSICS.md`, `docs/AI_VILLAGE_APPROVALS.md`):

- **Chain length is set by the scaffold.** The median computer-use session is exactly 40 actions across 78,111 sessions, because agents consolidate memory every 40 actions; the Claude Code agent, running its own loop, has a median of 8. Oversight metrics keyed to chain length would be measuring the harness.
- **A privileged-class inventory a content-blind gate would see.** 35.7% of bash commands (14.4% of all actions) match network, credential or process-launch patterns; agents named 4,819 distinct external hosts, 241 of them named by five or more agents. GUI actions are unclassified and hostnames do not prove contact, so these are proxy counts.
- **The Village's own approval loop, reconstructed from events.** 352 outreach requests, 343 decisions, 87 refusals, median turnaround 3 minutes with a tail of two days; ten requests disclosed routing an action through another agent that held credentials the requester lacked, nine approved. These are the oversight artifacts the event table already provides without reading chat.

## The tool, and the questions it answers

`python -m friction.forensics <log>` runs a fixed question set over any broker log: who touched which credentials, which hosts were named, which spawns omitted the policy, what the gates denied, what an unenforced rule would have denied, what an officer approved or refused. The Village scripts apply the same questions to a transcript export. The intent matches the brief's request for pre-written questions one would always ask of a multi-agent group, answered from structure rather than narrative.

The defensible contribution is an inspectable experimental harness, a forensic log and question set that survive an audit, descriptive Village measurements with their denominators stated, and evidence that policy exposure can dominate the apparent effect of procedural declarations in this small benchmark. It does not establish a general content-blind containment mechanism.

Full results, qualifications and reproduction links are in `RESULTS.md` and `docs/REPAIR_PROTOCOL.md`.
