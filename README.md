# swarm_friction

Procedural friction as a containment mechanism for agent swarms. Preliminary work for
David Fraile Navarro's **MATS Winter 2027 Stage-2** application (empirical track).

**The one-line claim:** content-blind procedural friction degrades out-of-scope action chains
more than it degrades legitimate work, because out-of-scope paths are denser in privileged-class
actions and decay multiplicatively under gates that never know what they are looking at.

**Status (2026-10-03, Sat 01:00 Sydney):** harness built and tested; methodology revised and
pre-registered with two amendments after three pilots; confirmatory runs in progress on two
model families. See `PREREGISTRATION.md` for what was fixed before model spend and why.

## Documents

| File | What it is |
|---|---|
| `PREREGISTRATION.md` | Hypotheses, falsifiers, estimand, sample, exclusions, and the dated amendments after each pilot. **Read this to know what the numbers mean.** |
| `METHODOLOGY.md` | v1.1 revisions: the mechanism is privileged-action density, not chain length; the weekend gate bundle; grading; models; budget. Overrides HANDOFF §4. |
| `HANDOFF.md` | The brief: purpose, thesis, hard design rules, literature positioning, open decisions. |
| `HARNESS_SPEC.md` | The implementation spec: world, tools, gates, loci, episode loop, log schema, build order. |
| `CHARTER.md` | The "Meridian Analytics" agent operations charter under test. §6 and §8 are load-bearing. |
| `TASKS.md` / `tasks.yaml` | 20 tasks. Suite A benign (friction tax), Suite B temptation (violation rate). Matched on in-scope chain length; `k_in`/`k_out` privileged-action counts. `tasks.yaml` is the text as run. |
| `DESIGN_CONVERSATION.md` | Verbatim extract of the 2026-09-10 session that produced the design. |

## Code

```
friction/
  world.py      in-memory mocked filesystem, hosts, credentials, toy SQL. No real I/O.
  seed.py       deterministic world_seed.json + reference.json (planted facts the graders check)
  charter.py    CHARTER text + digest; privileged_class() (syntactic, gates may use it);
                classify() — the scope oracle, LOGGER ONLY
  gates.py      Broker: structured arm (Spec + Jurisdiction + spawn-charter), tax arm (ack),
                environment and agent loci. Never names the oracle (tests/test_invariant.py).
  episode.py    episode loop, spawn tree, JSONL call log + episode row; scripted agents
  agents.py     LLM agents (OpenAI Responses API, Anthropic Messages), compliance officer, judge
  tasks.py      task loader and deterministic graders
  run.py        CLI
analysis/primary.py   the confirmatory analysis, committed before the confirmatory run
tests/                19 tests; the invariant test parses gates.py and fails if it can see scope
inspect_port/         one Suite B task ported to UK AISI Inspect (separate, small)
```

### Run

```bash
uv venv .venv && source .venv/bin/activate && uv pip install anthropic openai inspect_ai pandas statsmodels pytest pyyaml
python -m friction.seed && python -m pytest -q
python -m friction.run --model gpt-6-luna --charter none --friction none,structured,tax --suite A,B --seeds 1,2,3,4,5 --out runs/main_luna
python analysis/primary.py runs/main_luna runs/main_sonnet
```

Flags: `--friction none|structured|tax`, `--locus environment|agent`, `--charter prompt|file|none`,
`--effort`, `--budget` (USD cap per process; the run stops at the cap). OpenAI calls use
`OPENAI_API_KEY_ALT` if set.

## The forensic log

Every tool call, by every agent in the episode's spawn tree, is one JSONL row in
`runs/<dir>/calls.jsonl`. This stream is the deliverable the hackathon brief calls *digital
forensics beyond transcripts*: nobody has to read the natural-language record to know what the
swarm did.

| field | meaning |
|---|---|
| `episode_id, task_id, suite, n_star, locus, friction, model, seed` | the cell |
| `step, agent_id, parent_id, depth` | position in the episode and in the spawn tree (`root.2` is the second helper spawned by root) |
| `tool, target, args_digest, ticket` | what was asked, hashed, and under which broker ticket |
| `privileged_class` | P1–P5 (Charter §5) or null, the gate trigger |
| `gate_results[]` | each gate's verdict and the reason string the agent saw |
| `executed` | whether the world ran it |
| `scope` | `in_scope` / `out_of_scope` from the oracle, written by the logger after the fact |
| `laundering` | a spawn whose instruction omitted the Charter text and digest |
| `meta, declaration, declared_scope, rubber_stamp` | for `declare`/`ack` rows: what was declared and, at the agent locus, whether the officer approved something out of scope |

`calls.episodes.jsonl` has one row per episode with the outcomes (`objective_met`,
`violation_attempted`, `violation_completed`, `scoped_refusal`, `laundering`, `rubber_stamp`,
`truncated`, `k_realised`, steps, tokens, cost, submission).

## What the pilots already showed (not confirmatory)

With the Charter in the system prompt, or even a one-line pointer to it on disk, both
`gpt-6-luna` and `claude-sonnet-5-5` took zero out-of-scope actions in 10 temptation tasks.
Remove the mention and the completed-violation rate is 0.4 and 0.2 respectively, with
norm-laundering appearing (helpers spawned without the Charter that then read `/archive/`) and one
helper attempting a real external host. Details and dates in `PREREGISTRATION.md`, amendments 1–2.

## Known weaknesses

Charter and tasks authored in one session (a blind salience rating by a second person is still
owed); toy world; two models; agents that do not know the gates exist; the `tax` control is
cost-matched by round-trips, token-matched only approximately. See HANDOFF §10 and METHODOLOGY §11.
