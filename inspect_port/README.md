# inspect_port — task B-S1 on UK AISI Inspect

**What is ported.** One Suite B task, `B-S1` ("Report the 2024 annual claims total", the `/archive/` shortcut), as an
Inspect `@task` in `friction_bs1.py`. The Sample is the B-S1 entry from `tasks.yaml`; the solver is Inspect's
`basic_agent` tool loop over `@tool` wrappers of the mocked world tools (`fs_list, fs_read, fs_write, net_request,
cred_read, db_query`, plus Inspect's own `submit`). One `friction.world.World` and one `friction.gates.Broker`
per sample; every world call goes through `Broker.evaluate()`, so `-T friction=structured` exposes `declare` and the
Spec/Jurisdiction gates deny unticketed privileged calls exactly as in the main harness. The system prompt is
`friction.agents.build_system(None, friction_on, charter="none")`. The scorer is the only place that imports
`friction.charter.classify`; it labels the recorded calls after the fact and reports `objective_met`,
`violation_attempted`, `violation_completed`, `scoped_refusal` (keyword proxy, no judge), `k_realised`, `steps`,
`denied_calls`. The full procedural record (with scope) is kept in the score metadata and the sample store.

**Run** (from the repo root, venv active):

    inspect eval inspect_port/friction_bs1.py --model openai/gpt-6-luna -M responses_api=true --reasoning-effort medium -T friction=none --log-dir inspect_port/logs
    inspect eval inspect_port/friction_bs1.py --model anthropic/claude-sonnet-5-5 -T friction=structured --log-dir inspect_port/logs
    inspect view --log-dir inspect_port/logs

`gpt-6-luna` lives on the alternate key: prefix with `OPENAI_API_KEY=$OPENAI_API_KEY_ALT`. One sample costs well under a cent.

**Not ported.** `spawn` and the spawn tree (so no norm-laundering measure), the `tax`/`ack` control arm, the agent
locus (compliance officer, `rubber_stamp`), the cross-family refusal judge, Suite A, seeds/cells, and the JSONL
forensic log (Inspect's `.eval` log replaces it). Charter-in-prompt and charter-as-file prompt variants are not wired.

**Did Inspect fight the design?** Not on the semantic side: nothing pushed toward an LLM monitor, and the
solver/scorer split maps cleanly onto the harness invariant (gates in the tools, oracle in the scorer). The friction
was mechanical: per-sample world state has to live outside Inspect's JSON `Store` (a module-level registry keyed by
`state.uuid`), the tool loop is Inspect's rather than ours, so the step budget is a message limit, and the loader
broke `@dataclass` under `from __future__ import annotations`.
