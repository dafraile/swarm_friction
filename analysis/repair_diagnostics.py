"""Descriptive operational diagnostics for repair-v2; no new inferential tests."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import statistics
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from analysis.repair_v2 import load_campaign


def render(root):
    m,rows=load_campaign(root);enriched=[]
    for r in rows:
        if r['status']!='completed':continue
        calls=[json.loads(l) for l in (root/'main/attempts'/r['id']/'calls.jsonl').read_text().splitlines()]
        world=[c for c in calls if not c['meta']]
        enriched.append({**r,'root_read_charter':any(c['agent_id']=='root' and c['tool']=='fs_read' and c['target']=='/workspace/CHARTER.md' and c['executed'] for c in world),
          'child_calls':sum(c['depth']>0 for c in world),'child_instances':len({c['agent_id'] for c in world if c['depth']>0}),
          'child_policy_failures':sum(c['tool']=='spawn' and c['executed'] and c.get('charter_delivered') is not True for c in world)})
    lines=['# Repaired run: operational diagnostics','',
      'Descriptive statistics over completed main-run episodes only. “Attempted” denotes calls processed by the broker; proposals beyond a step limit would remain in the raw API trace. Explicit charter reads are observations, not a randomized mediator. A missing read is not proof of policy ignorance. Costs are per-episode token-rate estimates.','',
      '| Model | Suite | Arm | n | Attempted violation | Mean world steps | Mean meta calls | Mean input tokens | Episode costs (USD) | Root read policy | Child instances |',
      '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for model in m['models']:
        for suite in 'AB':
            for arm in m['arms']:
                rr=[r for r in enriched if r['model']==model and r['suite']==suite and r['arm']==arm]
                if not rr:continue
                avg=lambda k:statistics.mean(r[k] for r in rr)
                lines.append(f"| {model} | {suite} | {arm} | {len(rr)} | {sum(r['violation_attempted'] for r in rr)} | {avg('steps'):.1f} | {avg('meta_calls'):.1f} | {avg('tokens_in'):.0f} | {sum(r['cost_usd'] for r in rr):.4f} | {sum(r['root_read_charter'] for r in rr)} | {sum(r['child_instances'] for r in rr)} |")
    lines+=['',f"Total child instances with logged world calls: {sum(r['child_instances'] for r in enriched)}. Successful child starts missing platform-delivered policy: {sum(r['child_policy_failures'] for r in enriched)}. Root/child identities are counted within each episode, avoiding collisions between names such as root.1 in different episodes.",
      'All agent file/network operations are simulated. The only live network operations performed by this campaign are the model API requests.']
    return '\n'.join(lines)+'\n'

if __name__=='__main__':
    root=Path(sys.argv[1] if len(sys.argv)>1 else 'runs/repair_v2');report=render(root)
    Path('docs/REPAIR_DIAGNOSTICS.md').write_text(report)
    print('Wrote docs/REPAIR_DIAGNOSTICS.md')
