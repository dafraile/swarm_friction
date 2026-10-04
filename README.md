# swarm_friction

**Procedural gates and forensic logs for AI agents that use tools.** A research prototype built for the AI Swarm Dynamics Hackathon (October 2026) by David Fraile Navarro, Macquarie University.

The write-up for the hackathon is [docs/HACKATHON_SUBMISSION.md](docs/HACKATHON_SUBMISSION.md). The current experimental results and their limits are in [RESULTS.md](RESULTS.md). This README explains what is in the repository and how to use it.

## What this project is

When an AI agent (or a group of agents) works with real tools, three questions need answering after the fact: who requested an action, what was the agent allowed to do, and what actually executed. Chat transcripts answer these badly. This repository tests a different approach:

- A **charter** ([CHARTER.md](CHARTER.md)): a short, plain-English operating policy for agents on a fictional analytics platform ("Meridian Analytics"). It says which file paths may be read, which hosts may be contacted, which credentials exist and what they are for, and that an incomplete answer within scope is preferred to a complete answer outside it.
- A **broker** that sits between the agent and its tools. Before any privileged tool call (network request, credential use, reading outside the workspace, spawning another agent, writing to a public location) it can require the agent to acknowledge the call, or to declare what it is about to do and which charter clause allows it. The broker checks that the procedure was followed; it never judges whether the action is permitted.
- A **structured log** that records, after execution, whether each action was actually within scope, alongside identity, declarations, tickets, gate decisions, arguments and full outputs. Procedural compliance and real policy compliance are recorded separately so they can be compared.
- A **forensic question set** (`python -m friction.forensics <log>`) that answers fixed questions over any such log: who touched which credentials, which hosts were named, which spawned agents did not receive the policy, what the gates refused, what an unenforced rule would have refused.

Everything runs in a mocked environment (in-memory files, hosts, credentials and a read-only SQLite database generated from a seed). No real network or filesystem actions are performed by the agents; the only live calls are to the model APIs.

## What we did

1. **A controlled experiment (400 episodes).** Twenty task templates, ten benign and ten with a tempting out-of-scope shortcut, run in two generated worlds on two models (`gpt-6-luna`, `claude-sonnet-5-5`) under five conditions: no gate; a pointer to the policy file; an acknowledgement gate plus pointer; a declaration gate plus pointer; a declaration gate without the pointer. The protocol was frozen before the run ([docs/REPAIR_PROTOCOL.md](docs/REPAIR_PROTOCOL.md)). Headline: pointing the agent at the policy cut completed violations from 17/40 to 3/40; either gate on top of that brought them to 0/40; the declaration gate showed no measurable benefit over the cheaper acknowledgement gate. Full tables in [docs/REPAIR_RESULTS.md](docs/REPAIR_RESULTS.md), interpretation in [RESULTS.md](RESULTS.md).
2. **Descriptive analysis of the AI Village dataset** (AI Digest; 78,111 computer-use sessions, 2.5 million turns, plus an events table). We applied the same forensic questions: how long are action chains and what sets their length ([docs/AI_VILLAGE_CHAINS.md](docs/AI_VILLAGE_CHAINS.md)); how often would a content-blind gate have fired, and on what ([docs/AI_VILLAGE_FORENSICS.md](docs/AI_VILLAGE_FORENSICS.md)); what the Village's own human approval loop looks like when reconstructed from events alone ([docs/AI_VILLAGE_APPROVALS.md](docs/AI_VILLAGE_APPROVALS.md)). The privileged-action classifier is a regex proxy calibrated on development examples, not an independently validated detector ([docs/AI_VILLAGE_CLASSIFIER_VALIDATION.md](docs/AI_VILLAGE_CLASSIFIER_VALIDATION.md)).
3. **A structural audit of the SwarmTraces export** before measuring anything in it ([docs/SWARMTRACES_STRUCTURE.md](docs/SWARMTRACES_STRUCTURE.md)): record kinds, parent graph depth, missing timestamps, duplicated text and redaction-marker counts, with the definitions and source hash recorded.

### A note on the earlier version

The first version of the experiment, run earlier in the project, appeared to show a strong effect of the declaration gate. An independent review of the harness found confounds and bugs (the declaration arm included a policy reminder its control lacked; per-agent step budgets could be exceeded by child agents; credential names could authenticate without a token; permissive graders; some interrupted episodes were replaced). We kept everything from that version in Git and in the run directories, fixed the harness, froze a new protocol and reran from scratch. The old report is preserved as [docs/RESULTS_V1_HISTORICAL.md](docs/RESULTS_V1_HISTORICAL.md); the list of corrections is [docs/LEGACY_ERRATA.md](docs/LEGACY_ERRATA.md); the review itself is [docs/audit/AUDIT_2026-10-04.txt](docs/audit/AUDIT_2026-10-04.txt). The old and new results must not be pooled: tasks, tools, policy wording and graders all changed.

## Repository layout

```
CHARTER.md                 The agent operating policy used in the experiment
RESULTS.md                 Current results and limitations (start here for findings)
docs/HACKATHON_SUBMISSION.md   The hackathon write-up
docs/REPAIR_PROTOCOL.md    Frozen design of the current experiment
docs/REPAIR_RESULTS.md     Full count tables and bootstrap intervals
docs/REPAIR_DIAGNOSTICS.md Steps, tokens, costs, policy reads per condition
docs/REPAIR_OUTPUT_SENSITIVITY.md  Disclosed post-hoc grading sensitivity
docs/AI_VILLAGE_*.md       AI Village analyses
docs/SWARMTRACES_STRUCTURE.md      SwarmTraces structural audit
docs/audit/                Review notes, reproduction outputs, verification JSON
docs/RESULTS_V1_HISTORICAL.md, docs/LEGACY_ERRATA.md   Superseded first version and its corrections

friction/                  The harness
  world.py                 Mocked files, hosts, credentials, SQLite queries, file copying
  charter.py, gates.py     Privileged-operation classes, scope oracle, broker procedures and tickets
  episode.py               One episode: step budget, child agents, tool log, saved outputs
  agents.py                Model API adapters, raw response traces, cost reservations
  grading.py               Output contracts and reference grading for the current tasks
  experiment.py            Frozen randomised schedule, attempt records, shared budget
  forensics.py             The fixed forensic question set over a log
  run.py, tasks.py         Interface and graders of the first version (kept for provenance)
analysis/                  Analysis scripts (see below)
tests/                     42 unit tests covering harness invariants and interruption recovery
tasks.yaml                 The twenty task templates
runs/repair_v2/            Complete records of the current experiment (pilot and main)
runs/<other>/              Records of the first version
inspect_port/              One task ported to UK AISI's Inspect framework, as a demonstration
data/                      Generated world seed and references; large datasets are git-ignored
HANDOFF.md, DESIGN_CONVERSATION.md, METHODOLOGY.md, PREREGISTRATION.md, HARNESS_SPEC.md, TASKS.md
                           Design notes from the first version, kept for provenance
```

Every episode in `runs/repair_v2/{pilot,main}/attempts/<job-id>/` contains the started record, the full model API transcript, every tool call and result, the episode outcome, the submitted result, the workspace files and the reference values. `manifest.json` records the exact policy text, prompts, model identifiers, prices, SDK versions, source hashes and generated worlds.

## Reproducing

Python 3.11 or newer. `requirements-repaired.txt` pins the tested dependencies; `docs/audit/v2_environment.json` records the exact versions used.

```bash
python -m pip install -r requirements-repaired.txt
python -m pytest -q
```

To regenerate the reports from the committed records (no API calls, no cost):

```bash
python analysis/repair_v2.py runs/repair_v2 --out docs/REPAIR_RESULTS.md
python analysis/repair_output_audit.py runs/repair_v2
python analysis/repair_diagnostics.py runs/repair_v2
python analysis/verify_repair_records.py runs/repair_v2     # offline replay of all 410 episodes
python -m friction.forensics runs/repair_v2/main/attempts/<job-id>/calls.jsonl
```

To run a new campaign (paid; requires `OPENAI_API_KEY_ALT` and `ANTHROPIC_API_KEY`):

```bash
python -m friction.experiment --phase pilot --initialize --out runs/my_campaign
python -m friction.experiment --phase pilot --execute    --out runs/my_campaign
python -m friction.experiment --phase main  --initialize --out runs/my_campaign
python -m friction.experiment --phase main  --execute    --out runs/my_campaign
```

Initialisation is offline and freezes the schedule, prompts, source hashes and generated worlds. Execution refuses to continue a frozen manifest if the experimental source code has changed, and never replaces an episode that has already started. The default budget cap is US$25 across both phases; every request reserves its maximum cost before being sent. The completed run cost about US$9.09. For an exact reproduction of the completed run's code, check out the Git commit recorded in `runs/repair_v2/main/manifest.json`.

The AI Village analyses need the dataset from AI Digest (access is granted on request under research terms) placed under `data/ai_village/`; the SwarmTraces audit needs the publisher's redacted export under `data/swarmtraces/`. Both directories are git-ignored. The scripts are `analysis/ai_village_chains.py`, `analysis/village_forensics_pass.py`, `analysis/village_approvals.py`, `analysis/validate_classifier.py` and `analysis/swarmtraces_structure.py`; each writes the corresponding document in `docs/`.

## What the results do and do not establish

In this benchmark, making the policy salient to the agent did most of the work, and any procedural gate on top of it eliminated completed violations without hurting benign-task completion. The declaration procedure (state what you are about to do, name the clause) showed no measurable advantage over a content-free acknowledgement that costs the same round trip. Zero events in 40 episodes is not evidence of safety or of equivalence; the task set is small (ten templates per suite) and both models were cooperative. The gate is procedural: a correctly declared forbidden action passes it, and its behavioural effect differed sharply between the two models when the policy pointer was removed. Neither model spawned a helper agent during the main run, so nothing here tests delegation or swarm containment empirically. The Village and SwarmTraces analyses are descriptive inventories with their denominators stated, not measurements of any intervention. See [RESULTS.md](RESULTS.md) for the full statement.

## Citation and data terms

AI Village data: AI Digest, *AI Village* dataset, used under its research terms. SwarmTraces: the publisher's redacted export; only aggregate outputs are committed here. The agent operating policy, task templates and synthetic world are original to this repository.
