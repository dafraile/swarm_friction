"""Offline replay/consistency audit of the repaired API experiment. No provider calls."""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from friction.charter import ToolCall, classify
from friction.gates import Broker
from friction.grading import grade
from friction.world import World


def check(root):
    errors=[];counts={'completed':0,'interrupted':0,'unstarted':0,'replayed_world_calls':0,'responses':0}
    request_usage={'tokens_in':0,'tokens_out':0};row_usage={'tokens_in':0,'tokens_out':0}
    def require(ok,context):
        if not ok:errors.append(context)
    for phase in ['pilot','main']:
        m=json.loads((root/phase/'manifest.json').read_text())
        worlds={s:json.loads((root/phase/f'world_{s}.json').read_text()) for s in m['world_hashes']}
        for s,w in worlds.items():
            require(hashlib.sha256(json.dumps(w,sort_keys=True).encode()).hexdigest()==m['world_hashes'][s],phase+': world hash mismatch '+s)
        for j in m['schedule']:
            directory=root/phase/'attempts'/j['id'];rp=directory/'result.json'
            if not rp.exists():
                counts['interrupted' if (directory/'started.json').exists() else 'unstarted']+=1;continue
            r=json.loads(rp.read_text())
            if r['status']!='completed':counts['interrupted']+=1;continue
            counts['completed']+=1
            context=phase+'/'+j['id']
            rows=[json.loads(l) for l in (directory/'calls.jsonl').read_text().splitlines()]
            w=World(**deepcopy(worlds[str(j['seed'])]));a=m['arms'][j['arm']]
            b=Broker(friction=a['friction'],seed=j['seed'],gates=frozenset(m['gates']),charter_text=w.files['/workspace/CHARTER.md'],policy_reminder=a['policy_reminder'])
            world_rows=[x for x in rows if not x['meta']]
            require([x['step'] for x in world_rows]==list(range(len(world_rows))),context+': nonsequential world steps')
            require(len(world_rows)==r['steps']<=6*r['n_star'],context+': step count/budget mismatch')
            for x in rows:
                c=ToolCall(x['tool'],x['args'],agent_id=x['agent_id'],parent_id=x['parent_id'],ticket=x['ticket'])
                if x['meta']:
                    if c.tool=='declare':ok,payload,_=b.declare(c.agent_id,**c.args)
                    else:ok,payload=b.ack(c.agent_id,**c.args)
                elif c.tool=='submit':ok,payload=True,'submitted (auto)' if x['payload']=='submitted (auto)' else 'submitted'
                else:
                    verdicts=b.evaluate(c)
                    if not all(v.allow for v in verdicts):ok,payload=False,next(v.reason for v in verdicts if not v.allow)
                    elif c.tool=='spawn':
                        ok,payload=(False,'ERROR: helper agents may not spawn further agents') if x['depth']>=1 else (True,'helper started')
                        if ok:require(w.files['/workspace/CHARTER.md'].strip() in x.get('child_instruction',''),context+': child missing full policy')
                    else:
                        try:ok,payload=getattr(w,c.tool)(**c.args)
                        except TypeError as e:ok,payload=False,f'ERROR: bad arguments for {c.tool}: {e}'
                    counts['replayed_world_calls']+=1
                require(ok==x['executed'] and str(payload)==x['payload'],context+': replay mismatch at '+c.tool+' step '+str(x['step']))
                if not x['meta']:
                    require(classify(c,w.restricted_tainted,w.token_to_name)==x['scope'],context+': scope mismatch')
            artifact=json.loads((directory/'artifacts'/f"{j['id']}.json").read_text())
            require(w.snapshot_files()==artifact['files'],context+': final files differ from replay')
            require(w.reference==artifact['reference'],context+': reference changed')
            task=next(t for t in m['tasks'] if t['id']==j['task_id'])
            outcome,_=grade(task,r['submission'],artifact['files'],artifact['reference'])
            require(outcome==r['objective_met'],context+': grade mismatch')
            calls=0;tin=tout=0
            for line in (directory/'transcript.jsonl').read_text().splitlines():
                t=json.loads(line);u=t['response']['usage'];calls+=1
                if j['model'].startswith('claude'):
                    tin+=u['input_tokens']+(u.get('cache_read_input_tokens') or 0)+(u.get('cache_creation_input_tokens') or 0)
                else:tin+=u['input_tokens']
                tout+=u['output_tokens']
            require((tin,tout,calls)==(r['tokens_in'],r['tokens_out'],r['llm_turns']),context+': trace usage mismatch')
            counts['responses']+=calls
            request_usage['tokens_in']+=tin;request_usage['tokens_out']+=tout
            row_usage['tokens_in']+=r['tokens_in'];row_usage['tokens_out']+=r['tokens_out']
    ledger=[json.loads(l) for l in (root/'budget.jsonl').read_text().splitlines()]
    pending={};paid=0;spent=0.;max_committed=0.
    for e in ledger:
        if e['event']=='reserve':
            require(e['id'] not in pending,'duplicate reservation');pending[e['id']]=e['usd']
        elif e['event']=='settle':
            bound=pending.pop(e['id'],None);require(bound is not None and e['usd']<=bound+1e-9,'invalid request settlement');spent+=e['usd'];paid+=1
        max_committed=max(max_committed,spent+sum(pending.values()))
    require(max_committed<=m['campaign_cap_usd']+1e-9,'campaign budget exceeded')
    if not counts['interrupted'] and not counts['unstarted']:require(paid==counts['responses'],'paid response count differs from complete traces')
    return {'counts':counts,'errors':errors,'confirmed_cost_usd':spent,'pending_reservations_usd':sum(pending.values()),'max_committed_usd':max_committed,'usage':row_usage}

if __name__=='__main__':
    root=Path(sys.argv[1] if len(sys.argv)>1 else 'runs/repair_v2');result=check(root)
    if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    sys.exit(bool(result['errors']))
