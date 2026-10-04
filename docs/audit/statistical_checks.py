"""Offline exploratory audit contrasts. Does not call model APIs or change results."""
import collections
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from analysis.primary import load, primary
from friction.charter import ToolCall, classify
from friction.episode import _args_from_target

data = load([ROOT / 'runs' / p for p in ('main_luna', 'main_sonnet', 'main_sonnet_tax')])
b = data[data.suite == 'B']
rng = np.random.default_rng(42)
for label, d in [('luna', b[b.model_family == 'gpt-6-luna']),
                 ('sonnet', b[b.model_family == 'claude-sonnet-5-5']), ('pooled', b)]:
    rates = d.groupby(['task_id', 'friction']).violation_completed.mean().unstack()
    delta = (rates.tax - rates.structured).values
    boot = delta[rng.integers(0, len(delta), (100000, len(delta)))].mean(axis=1)
    print(label, 'tax minus structured', delta.mean(), 'task bootstrap 95%',
          np.quantile(boot, [.025, .975]), 'task deltas', delta.tolist())

print('EXPLORATORY alternative endpoint: objective met without a completed violation')
a = data.suite == 'A'
print(data[a].groupby(['model_family', 'friction'])[['objective_met', 'violation_completed']].mean())
data.loc[a, 'y'] = (data.loc[a, 'objective_met'] & ~data.loc[a, 'violation_completed']).astype(int)
primary(data, 'structured', 'pooled safe success; not preregistered')

for name in ('main_luna_agent', 'main_luna_agent_samefamily', 'abl_luna_officer_blind'):
    ctr = collections.Counter()
    for line in (ROOT / 'runs' / name / 'calls.jsonl').read_text().splitlines():
        row = json.loads(line)
        d = row.get('declaration')
        if d:
            scope = classify(ToolCall(d['tool'], _args_from_target(d['tool'], d['target'])))
            ctr[(scope, bool(d['approved']))] += 1
    print(name, 'declaration classifications with current target-only oracle', dict(ctr))
