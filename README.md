# swarm_friction

Procedural friction as a containment mechanism for agent swarms. Preliminary work for
David Fraile Navarro's **MATS Winter 2027 Stage-2** application (empirical track).

**Start with `HANDOFF.md`.** It is written for an agent with no prior context.

| File | What it is |
|---|---|
| `METHODOLOGY.md` | **v1.1 revisions, 2026-10-02.** Fixes the chain-length mechanism (friction is keyed to privileged-action density, not path length), fixes the estimand, specifies the weekend gate bundle, grading, models, budget. Overrides HANDOFF §4 where they differ. |
| `PREREGISTRATION.md` | Hypotheses, falsifiers, analysis plan, sample, exclusions. Registered before any model spend. |
| `HANDOFF.md` | The brief. Purpose, thesis, hypothesis, hard design rules, literature positioning, open decisions. **Read first.** |
| `HARNESS_SPEC.md` | The implementation spec. World, tools, gates, loci, episode loop, log schema, metrics, build order. |
| `CHARTER.md` | The fictional "Meridian Analytics" agent operations charter — the policy under test. §6 and §8 are load-bearing. |
| `TASKS.md` | 20 tasks. Suite A benign (friction tax), Suite B temptation (violation rate). Matched on chain length. |
| `DESIGN_CONVERSATION.md` | Verbatim extract of the session that produced the design — the reasoning, rejected options, and two factual corrections. |

**The one-line claim:** content-blind procedural friction degrades out-of-scope action chains
more than it degrades legitimate work, because out-of-scope paths are denser in privileged-class
actions and decay multiplicatively under gates that never know what they are looking at.

**Status (2026-10-02):** methodology revised and pre-registered. Harness build in progress. Nothing run.
