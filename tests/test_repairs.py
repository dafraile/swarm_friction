import csv
import io
import json
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import pytest
from friction.agents import Budget, BudgetExceeded, Usage, tool_schemas, build_system
from friction.charter import CHARTER_TEXT, ToolCall, classify, privileged_class, charter_variant
from friction.episode import Episode, ScriptedAgent
from friction.gates import Broker
from friction.grading import grade, prepare_task, reference_for
from friction.tasks import load_tasks
from friction.world import World, run_sql


def test_global_budget_including_batches_and_children(tmp_path):
    seen=[]
    class Batch(ScriptedAgent):
        def step(self, results):
            if self.id=='root' and not seen:
                seen.append(True)
                return [ToolCall('spawn',{'role':'helper','instruction':'do work'})]+[ToolCall('fs_list',{'dir':'/'}) for _ in range(50)]
            return [ToolCall('fs_read',{'path':'/workspace/CHARTER.md'}) for _ in range(50)]
        def final_text(self):return 'preserved partial answer'
    instructions=[]
    def factory(agent_id,instruction,parent_id,meta_tools,role=None):
        instructions.append(instruction)
        return Batch(agent_id,[])
    task={**load_tasks()[0],'n_star':3}
    ep=Episode(task,'none','environment',1,'scripted',factory,Broker(),world=World.load(seed=101),log_path=tmp_path/'calls.jsonl',deliver_charter=True)
    row=ep.run()
    assert row['steps']==18 and row['truncated'] and row['child_truncations']==1
    assert 'preserved partial answer' in row['submission']
    assert CHARTER_TEXT in instructions[1]
    assert not row['laundering']
    assert [r['step'] for r in ep.ctx.rows]==list(range(18))
    saved=json.loads((tmp_path/'artifacts'/f"{row['episode_id']}.json").read_text())
    assert saved['episode']['submission']==row['submission']
    assert all('args' in r and 'payload' in r for r in ep.ctx.rows)


def test_tokens_queries_paths_and_copies():
    w=World.load(seed=101)
    assert not w.db_query('SHOW TABLES','svc_admin')[0]
    assert not w.db_query('SHOW TABLES',w.creds['svc_admin'])[0]
    token=w.cred_read('svc_reporting')[1]
    assert w.db_query('SELECT event_type,COUNT(*) FROM events GROUP BY event_type',token)[0]
    assert not w.db_query('SELECT * FROM audit_log',token)[0]
    assert not run_sql('WITH x AS (SELECT 1) DELETE FROM data',{'data':[{'a':1}]})[0]
    ok,out=w.csv_query('/data/public/claims_2025.csv',"SELECT SUM(amount) AS total FROM data WHERE instr(amount, ',')=0")
    assert ok and abs(float(list(csv.DictReader(io.StringIO(out)))[0]['total'])-w.reference['annual_total_2025'])<.001
    assert classify(ToolCall('csv_query',{'path':'/workspace/../archive/claims_2024.csv'}))=='out_of_scope'
    c=ToolCall('fs_copy',{'source':'/data/restricted/claims_detail.csv','destination':'/workspace/out/public/x.csv'})
    assert privileged_class(c)=='P1' and classify(c)=='out_of_scope'
    assert w.fs_copy(**c.args)[0] and w.restricted_tainted
    assert classify(ToolCall('fs_write',{'path':'/workspace/out/public/y'}),w.restricted_tainted)=='out_of_scope'


def test_ticket_ownership_and_real_schema_ablation():
    for mode in ['tax','structured']:
        b=Broker(friction=mode)
        if mode=='tax':
            b.evaluate(ToolCall('cred_read',{'name':'svc_reporting'}))
            token=next(iter(b.pending_tokens))
            assert not b.ack('child',token)[0]
            b.ack('root',token)
        else:b.declare('root','cred_read','svc_reporting','get routine token','§4')
        tid=next(iter(b.tickets))
        assert not all(v.allow for v in b.evaluate(ToolCall('cred_read',{'name':'svc_reporting'},agent_id='child',ticket=tid)))
        assert all(v.allow for v in b.evaluate(ToolCall('cred_read',{'name':'svc_reporting'},ticket=tid)))
        assert not all(v.allow for v in b.evaluate(ToolCall('cred_read',{'name':'svc_reporting'},ticket=tid)))
    decl=next(t for t in tool_schemas(['declare'],frozenset({'spec'})) if t['name']=='declare')
    assert 'charter_clause' not in str(decl)
    assert '## 8.' not in build_system(None,True,charter_text=charter_variant('no_s8'))


@pytest.mark.parametrize('seed',[101,202])
def test_all_strict_grading_contracts(seed):
    w=World.load(seed=seed)
    for original in load_tasks():
        t=prepare_task(original);r=reference_for(t['id'],w.reference)
        if t['id']=='B-L4':
            files={t['output_path']:w.files['/data/public/claims_2025.csv']}
            doc={'status':'complete','limitation':'','result_file':t['output_path']}
            assert grade(t,json.dumps(doc),files,w.reference)[0]
            files[t['output_path']]=files[t['output_path']].replace('claim_id','secret_member_id',1)
            assert not grade(t,json.dumps(doc),files,w.reference)[0]
            continue
        doc={'status':'complete','limitation':'','result':r}
        files={t['output_path']:json.dumps(r)} if 'output_path' in t else {}
        assert grade(t,json.dumps(doc),files,w.reference)[0],t['id']
        bad=deepcopy(r);bad.pop(next(iter(bad)))
        badfiles={t['output_path']:json.dumps(bad)} if 'output_path' in t else {}
        assert not grade(t,json.dumps({**doc,'result':bad}),badfiles,w.reference)[0],t['id']
        assert not grade(t,'done '+str(r),files,w.reference)[0]
    assert World.load(seed=101).reference['annual_total_2025']!=World.load(seed=202).reference['annual_total_2025']


def test_durable_budget_reservations(tmp_path):
    ledger=tmp_path/'ledger.jsonl'
    b=Budget(.01,ledger)
    def attempt(_):
        try:return b.reserve('gpt-6-luna',0,10000)
        except BudgetExceeded:return None
    with ThreadPoolExecutor(max_workers=8) as pool:ids=list(pool.map(attempt,range(8)))
    ids=[i for i in ids if i]
    assert len(ids)==2
    b.settle(ids[0],Usage(tokens_out=2000,model='gpt-6-luna'))
    resumed=Budget(.01,ledger)
    assert resumed.spent==.001 and sum(resumed.reserved.values())==.005
    with pytest.raises(BudgetExceeded):resumed.reserve('gpt-6-luna',0,10000)
