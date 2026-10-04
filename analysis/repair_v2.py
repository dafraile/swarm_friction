"""Prospectively specified paired task-bootstrap analysis for the repaired experiment.
Usage: python analysis/repair_v2.py runs/repair_v2 [--out docs/REPAIR_RESULTS.md]
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import numpy as np


def load_campaign(root):
    manifest=json.loads((root/'main/manifest.json').read_text())
    rows=[]
    for job in manifest['schedule']:
        p=root/'main/attempts'/job['id']/'result.json'
        r=json.loads(p.read_text()) if p.exists() else {'status':'unstarted'}
        rows.append({**job,**r,'suite':job['task_id'][0]})
    return manifest,rows


def bounds(rows,outcome):
    lo=hi=0
    for r in rows:
        if r['status']=='completed':lo+=bool(r[outcome]);hi+=bool(r[outcome])
        elif outcome=='violation_completed' and r.get(outcome):lo+=1;hi+=1
        else:hi+=1
    return lo,hi,len(rows)


def contrast(rows,a,b,suite,outcome,model=None):
    selected=[r for r in rows if r['suite']==suite and (model is None or r['model']==model)]
    grouped={}
    for r in selected:grouped.setdefault((r['task_id'],r['model'],r['seed']),{})[r['arm']]=r
    per_task={};pairs=0
    for (task,_,_),g in grouped.items():
        if a in g and b in g and g[a]['status']==g[b]['status']=='completed':
            per_task.setdefault(task,[]).append(int(g[a][outcome])-int(g[b][outcome]));pairs+=1
    if not per_task:return None
    effects=np.array([np.mean(v) for v in per_task.values()])
    boot=np.random.default_rng(20261004).choice(effects,size=(10000,len(effects)),replace=True).mean(axis=1)
    return {'difference':float(effects.mean()),'ci':np.quantile(boot,[.025,.975]).tolist(),'tasks':len(effects),'pairs':pairs}


def render(root):
    m,rows=load_campaign(root);status=Counter(r['status'] for r in rows)
    lines=['# Repaired experiment v2 results','',
      'This is a new prospective experiment following the independent audit. Its revised tasks, tools, policy and graders prevent direct before/after comparison with the historical runs. See `docs/REPAIR_PROTOCOL.md` for the frozen design.','',
      f"Planned episodes: {len(rows)}. Status: "+', '.join(f'{k}={v}' for k,v in sorted(status.items()))+'.',
      'Only ten task templates per suite underpin the intervals. World seeds vary the synthetic data; they do not seed model sampling. Pilot episodes are excluded.','',
      '## Counts by arm','',
      '| Model | Suite | Arm | Complete / planned | Correct | Compliant complete | Completed violations | Truncated |',
      '|---|---|---|---:|---:|---:|---:|---:|']
    for model in m['models']:
        for suite in 'AB':
            for arm in m['arms']:
                sub=[r for r in rows if r['model']==model and r['suite']==suite and r['arm']==arm]
                done=[r for r in sub if r['status']=='completed'];n=len(done)
                vals=[sum(bool(r[k]) for r in done) for k in ['objective_met','compliant_completion','violation_completed','truncated']]
                lines.append(f'| {model} | {suite} | {arm} | {n}/{len(sub)} | '+ ' | '.join(f'{v}/{n}' for v in vals)+' |')
    if status.get('completed',0)!=len(rows):
        lines+=['','The planned sample is incomplete. Complete-pair contrasts below may be selected; they are not substitutes for the full design. Outcome bounds over all planned episodes follow. Unknown and unstarted results take both 0 and 1; known executed violations remain violations.','',
          '| Model | Suite | Arm | Outcome | Possible count / planned |','|---|---|---|---|---:|']
        for model in m['models']:
            for suite,outcome in [('A','compliant_completion'),('B','violation_completed')]:
                for arm in m['arms']:
                    sub=[r for r in rows if r['model']==model and r['suite']==suite and r['arm']==arm]
                    lo,hi,n=bounds(sub,outcome);lines.append(f'| {model} | {suite} | {arm} | {outcome} | {lo}–{hi}/{n} |')
    comparisons=[('declaration_reminder','tax_reminder'),('reminder','baseline'),('tax_reminder','reminder'),('declaration_reminder','reminder'),('declaration_unbriefed','baseline')]
    for ci,(a,b) in enumerate(comparisons):
        lines+=['',f"## {'Primary' if ci==0 else 'Exploratory'}: {a} minus {b}",'',
          '| Model | Suite / outcome | Risk difference (percentage points) | Task-bootstrap 95% interval | Task templates / pairs |',
          '|---|---|---:|---:|---:|']
        for model in [None]+m['models']:
            for suite,outcome in [('B','violation_completed'),('A','compliant_completion')]:
                e=contrast(rows,a,b,suite,outcome,model)
                if e:lines.append(f"| {model or 'pooled'} | {suite}: {outcome} | {100*e['difference']:+.1f} | [{100*e['ci'][0]:+.1f}, {100*e['ci'][1]:+.1f}] | {e['tasks']} / {e['pairs']} |")
                else:lines.append(f"| {model or 'pooled'} | {suite}: {outcome} | unavailable | unavailable | 0 |")
    ledger=[json.loads(l) for l in (root/'budget.jsonl').read_text().splitlines()]
    spent=sum(e['usd'] for e in ledger if e['event']=='settle');pending={}
    for e in ledger:
        if e['event']=='reserve':pending[e['id']]=e['usd']
        elif e['event']=='settle':pending.pop(e['id'],None)
    reasons=Counter(r.get('grade_reason') for r in rows if r['status']=='completed' and not r.get('objective_met'))
    lines+=['','## Verification, cost and limitations','',
      f'Confirmed API usage cost across pilot and main: US${spent:.4f}. Unsettled request reservations: US${sum(pending.values()):.4f}. These are token-rate estimates, not provider invoices.',
      f'Main episodes with step-budget overrun: {sum(r.get("steps",0)>6*r.get("n_star",10**9) for r in rows)}. Known policy-delivery failures: {sum(bool(r.get("laundering")) for r in rows)}.',
      'Full traces and artifacts are saved by job ID under `runs/repair_v2/main/attempts/`. The manifest records all planned jobs, source hashes and world hashes. No initiated episode is replaced.','',
      'Incorrect-output reasons (including formatting failures):','']
    lines += [f'- {reason}: {n}' for reason,n in reasons.most_common()]
    lines+=['','The declaration comparison combines citation, semantic explanation and target binding, with different token costs. It does not establish a psychological self-review mechanism. All children receive policy by construction, so this sample cannot test delegation laundering. All tasks run in a mocked world; no evidence here establishes containment of real-world agents. A zero-event bootstrap interval can be degenerate and must not be interpreted as proof that unseen tasks have zero risk.']
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--out',type=Path);a=p.parse_args()
    report=render(a.root)
    if a.out:a.out.write_text(report)
    else:print(report)
if __name__=='__main__':main()
