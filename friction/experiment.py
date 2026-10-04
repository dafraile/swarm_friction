"""Versioned repair campaign. Initialize first; --execute explicitly enables paid API calls.

python -m friction.experiment --phase pilot --initialize
python -m friction.experiment --phase pilot --execute --profile ~/.zshrc
python -m friction.experiment --phase main --initialize
python -m friction.experiment --phase main --execute --profile ~/.zshrc
One campaign lock and durable budget ledger span both phases and all models.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
import fcntl
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import random
import re
import shlex
import subprocess
import threading
import time

from .agents import Budget, BudgetExceeded, LLMAgent, PRICES, RootUsageAggregator
from .charter import CHARTER_TEXT
from .episode import Episode
from .gates import Broker
from .grading import prepare_task
from .tasks import load_tasks
from .world import World

ROOT=Path(__file__).resolve().parents[1]
MODELS=['gpt-6-luna','claude-sonnet-5-5']
ARMS={
 'baseline':{'friction':'none','charter':'none','policy_reminder':False},
 'reminder':{'friction':'none','charter':'file','policy_reminder':True},
 'tax_reminder':{'friction':'tax','charter':'file','policy_reminder':True},
 'declaration_reminder':{'friction':'structured','charter':'file','policy_reminder':True},
 'declaration_unbriefed':{'friction':'structured','charter':'none','policy_reminder':False},
}
GATES=frozenset({'spec','jurisdiction'})


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()


def source_hashes():
    paths=list((ROOT/'friction').glob('*.py'))+[ROOT/'CHARTER.md',ROOT/'tasks.yaml',ROOT/'docs/REPAIR_PROTOCOL.md']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def load_keys(profile):
    """Read literal assignments only; never source a shell profile or print secrets."""
    names={'OPENAI_API_KEY_ALT','ANTHROPIC_API_KEY'}
    if profile:
        for line in Path(profile).expanduser().read_text().splitlines():
            m=re.match(r'^\s*(?:export\s+)?(OPENAI_API_KEY_ALT|ANTHROPIC_API_KEY)\s*=\s*(.*)$',line)
            if m:
                parts=shlex.split(m[2],comments=True)
                if len(parts)==1 and '$' not in parts[0] and '`' not in parts[0]:os.environ[m[1]]=parts[0]
    if not all(os.environ.get(n) for n in names):raise RuntimeError('Alternative OpenAI and Anthropic credentials are required')
    # Campaign deliberately cannot fall back to the primary OpenAI account.
    os.environ.pop('OPENAI_API_KEY',None)


def jobs_for(phase):
    rng=random.Random(20261004)
    jobs=[]
    if phase=='pilot':
        for mi,m in enumerate(MODELS):
            for i,t in enumerate(['A-S2','A-S5','B-L4','B-S1','B-S5']):
                jobs.append({'task_id':t,'model':m,'seed':909,'arm':list(ARMS)[(i+mi)%len(ARMS)]})
        rng.shuffle(jobs)
    else:
        # Balance arm exposure locally; order blocks and arm order independently.
        blocks=[(t['id'],m,s) for t in load_tasks() for m in MODELS for s in [101,202]]
        rng.shuffle(blocks)
        for t,m,s in blocks:
            arms=list(ARMS);rng.shuffle(arms)
            jobs.extend({'task_id':t,'model':m,'seed':s,'arm':a} for a in arms)
    for j in jobs:j['id']=digest([phase,j])[:16]
    return jobs


def initialize(path,phase,cap):
    target=path/phase/'manifest.json'
    if target.exists():raise RuntimeError('Manifest already exists; use the existing frozen plan')
    seeds=[909] if phase=='pilot' else [101,202]
    worlds={str(s):asdict(World.load(seed=s)) for s in seeds}
    for w in worlds.values():w.pop('issued_tokens')
    manifest={'protocol':'repair-v2','phase':phase,'created_at':time.time(),
      'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
      'source_hashes':source_hashes(),'tasks':[prepare_task(t) for t in load_tasks()],
      'arms':ARMS,'gates':sorted(GATES),'deliver_charter':True,'locus':'environment',
      'models':MODELS,'effort':'medium','max_output_tokens':6000,'campaign_cap_usd':cap,
      'prices_per_million_tokens':PRICES,'sdk_versions':{x:importlib.metadata.version(x) for x in ['openai','anthropic']},
      'world_hashes':{s:digest(w) for s,w in worlds.items()},'schedule':jobs_for(phase),
      'analysis':'Predeclared in docs/REPAIR_PROTOCOL.md. Pilot excluded; no outcome-based reruns.'}
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(manifest,indent=2)+'\n')
    for s,w in worlds.items():(target.parent/f'world_{s}.json').write_text(json.dumps(w,indent=1)+'\n')
    print(f'Frozen {phase} plan: {len(manifest["schedule"])} episodes at {target}',flush=True)


def run_job(job,manifest,out,budget,stop):
    if stop.is_set():return None
    directory=out/'attempts'/job['id'];directory.mkdir(parents=True,exist_ok=True)
    started=directory/'started.json'
    try:
        with started.open('x') as f:json.dump({**job,'time':time.time()},f)
    except FileExistsError:return None  # never silently replace an initiated attempt
    task=next(t for t in manifest['tasks'] if t['id']==job['task_id'])
    arm=manifest['arms'][job['arm']];agg=RootUsageAggregator()
    def factory(agent_id,instruction,parent_id,meta_tools,role=None):
        a=LLMAgent(agent_id,job['model'],task,instruction,meta_tools,budget=budget,parent_id=parent_id,
            effort=manifest['effort'],max_tokens=manifest['max_output_tokens'],charter=arm['charter'],
            gates=GATES,charter_text=CHARTER_TEXT,trace_path=directory/'transcript.jsonl')
        agg.agents.append(a)
        if parent_id is None:a.usage=agg.total
        return a
    world=World.load(seed=job['seed'])
    world.files['/workspace/CHARTER.md']=CHARTER_TEXT
    broker=Broker(friction=arm['friction'],seed=job['seed'],gates=GATES,charter_text=CHARTER_TEXT,policy_reminder=arm['policy_reminder'])
    ep=Episode(task,arm['friction'],'environment',job['seed'],job['model'],factory,broker,world=world,
      log_path=directory/'calls.jsonl',deliver_charter=True,charter_text=CHARTER_TEXT,
      metadata={'protocol':'repair-v2','phase':manifest['phase'],'arm':job['arm'],'job_id':job['id']})
    ep.ctx.episode_id=job['id']
    try:row=ep.run()
    except Exception as exc:
        stop.set()  # preserve partial evidence, stop launching new requests/jobs
        status='budget_interrupted' if isinstance(exc,BudgetExceeded) else 'provider_or_harness_error'
        # Error type/status only: provider response bodies may contain submitted content.
        error=type(exc).__name__+': '+str(getattr(exc,'status_code',''))
        if ep.root is not None:row=ep._episode_row(ep.root,status=status,error=error)
        else:row={**job,'status':status,'error':error}
    row['resolved_models']=sorted({a.resolved_model for a in agg.agents if a.resolved_model})
    (directory/'result.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps({'job':job['id'],'task':job['task_id'],'model':job['model'],'arm':job['arm'],
      'status':row['status'],'objective_met':row.get('objective_met'),'violation_completed':row.get('violation_completed'),
      'spent_usd':round(budget.spent,4),'reserved_usd':round(sum(budget.reserved.values()),4)}),flush=True)
    return row


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,default=Path('runs/repair_v2'))
    p.add_argument('--phase',choices=['pilot','main'],required=True)
    p.add_argument('--cap',type=float,default=25.0)
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--initialize',action='store_true')
    p.add_argument('--execute',action='store_true')
    p.add_argument('--profile',type=str)
    a=p.parse_args(argv)
    a.out.mkdir(parents=True,exist_ok=True)
    with (a.out/'campaign.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if a.initialize:initialize(a.out,a.phase,a.cap)
        if not a.execute:return
        m=json.loads((a.out/a.phase/'manifest.json').read_text())
        if m['source_hashes']!=source_hashes():raise RuntimeError('Source changed since manifest freeze; do not mix protocol versions')
        if a.cap!=m['campaign_cap_usd']:raise RuntimeError('Cap must match frozen campaign plan')
        load_keys(a.profile)
        budget=Budget(a.cap,a.out/'budget.jsonl');stop=threading.Event()
        jobs=m['schedule'];phaseout=a.out/a.phase
        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            futures=[pool.submit(run_job,j,m,phaseout,budget,stop) for j in jobs]
            for f in as_completed(futures):f.result()
        done=sum((phaseout/'attempts'/j['id']/'result.json').exists() for j in jobs)
        print(json.dumps({'finished_records':done,'planned':len(jobs),'spent_usd':budget.spent,'unsettled_reservations_usd':sum(budget.reserved.values())}),flush=True)

if __name__=='__main__':main()
