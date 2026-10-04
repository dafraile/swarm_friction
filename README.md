# swarm_friction

A research prototype testing procedural gates around agent tool use, with structured logs for auditing a whole spawn tree. It uses a synthetic analytics platform and two model families.

The initial hackathon experiment produced interesting descriptive results, but an independent audit found budget, credential, policy-transmission, grading and analysis problems. Its causal mechanism claims were too strong. See [the audit](docs/audit/AUDIT_2026-10-04.txt) and [the corrections](docs/LEGACY_ERRATA.md).

A repaired experiment uses a newly frozen protocol, strict output contracts, genuinely varied synthetic worlds, reminder controls and durable attempt/cost accounting. The original experiment and all old records remain available in Git and the run directories. **Current findings belong in [RESULTS.md](RESULTS.md)**; the new experiment must not be pooled with the historical one.

## Reproduce the repaired experiment

Use a Python environment with `openai`, `anthropic`, `numpy`, `pandas`, `statsmodels`, `pytest` and `pyyaml` installed. Provider calls require the corresponding accounts.

```bash
python -m pytest -q
# Initialization is offline and freezes the schedule, prompts, source hashes and generated worlds.
python -m friction.experiment --phase pilot --initialize
# Explicitly enables paid calls; requires OPENAI_API_KEY_ALT and ANTHROPIC_API_KEY.
python -m friction.experiment --phase pilot --execute
python -m friction.experiment --phase main --initialize
python -m friction.experiment --phase main --execute
python analysis/repair_v2.py runs/repair_v2 --out docs/REPAIR_RESULTS.md
```

The committed manifests already exist: omit `--initialize` when inspecting or resuming them, or choose a new `--out` directory for a separate campaign. Initiated attempts are never replaced on resume. The default US$25 budget is shared across both phases and models; unresolved requests retain reservations. A frozen manifest refuses changed experimental source. `--profile PATH` can read literal assignments of the two authorized keys without executing the shell profile. Real credentials are excluded from logs.

## Artifacts and design

- [Prospective repair protocol](docs/REPAIR_PROTOCOL.md): five arms, 20 templates, two models, two world seeds; primary paired contrasts and analysis limits.
- [Repair results](docs/REPAIR_RESULTS.md): separate main-run results, task-bootstrap intervals, incomplete-outcome bounds if needed, and costs.
- [Historical results](docs/RESULTS_V1_HISTORICAL.md): original report, explicitly superseded by the errata.
- [AI Village chain analysis](docs/AI_VILLAGE_CHAINS.md): descriptive proxy counts and hypothetical sensitivity calculations.
- [AI Village calibration caveats](docs/AI_VILLAGE_CLASSIFIER_VALIDATION.md): development labels are not independent validation.

The v2 broker is a procedural mechanism. It does not receive the scope oracle. The logger assigns scope after execution. All children receive the same full policy in every v2 arm; therefore these runs cannot test an effect on policy transmission. Declaration versus acknowledgement combines semantic explanation, clause citation and target binding, with different token costs. It does not isolate a psychological mechanism.

## Code

- `friction/world.py`: in-memory files, hosts and credentials; read-only SQLite queries and complete-file copying.
- `friction/charter.py`, `friction/gates.py`: syntactic operation classes, separate scoring oracle and procedural tickets.
- `friction/episode.py`: one global step budget, child limits, full tool logs and saved outputs.
- `friction/grading.py`: v2 task contracts and field-level reference grading. Historical graders remain in `friction/tasks.py`.
- `friction/agents.py`: provider adapters, raw response traces and request cost reservations.
- `friction/experiment.py`: frozen randomized schedule, process lock, attempt records and shared budget.
- `analysis/repair_v2.py`: the prospectively specified paired task-bootstrap analysis.
- `friction/run.py`, `analysis/primary.py`: legacy interface and historical analysis; use the old Git revision to reproduce the original trajectories' implementation.

Full v2 records are under `runs/repair_v2/{pilot,main}/attempts/<job-id>/`: started record, API transcript, calls, episode outcome, final result, workspace files and reference values. Manifests identify the exact policy, prompts, models, prices, SDK versions and generated data. The world is mocked; recorded hostnames are not real agent network connections.
