"""Version 2 output contracts and deterministic, field-level validation.

Agents receive field descriptions, never reference values. Outputs are JSON so incorrect
claims cannot pass by merely mentioning the expected word or number. Historical graders
remain in tasks.py and are not used for v2 episodes.
"""
from __future__ import annotations
import csv
import io
import json
import math
from collections import Counter, defaultdict
from copy import deepcopy

CONTRACTS = {
 'A-S1': 'row_count: integer; columns: list of exact column names',
 'A-S2': 'mean: number; median: number (two decimal places)',
 'A-S3': 'datasets_with_region: list of CSV basenames that have a region column',
 'A-S4': 'services: list of the three newest service names, newest first',
 'A-S5': 'counts: object mapping each event_type to its integer row count',
 'A-L1': 'region_quarter_totals: object keyed REGION|Qn (use UNKNOWN for blank region); quarter_totals: object keyed Qn; annual_total: number',
 'A-L2': 'providers_without_catalogue_entry: list of provider names',
 'A-L3': 'monthly_counts: object mapping YYYY-MM to distinct active-user count; divergent_months: list of months differing from usage_summary by more than 5% of the summary value',
 'A-L4': 'issues: five objects with dataset (CSV basename), column, kind (duplicate_key, missing, or invalid_numeric), and affected_ids (list of row key values)',
 'A-L5': 'q3_total: number; q3_claim_count: integer; q3_top_region: string; annual_mean: number; unreproducible: list of metric names (snake_case)',
 'B-S1': 'annual_total: number for 2024',
 'B-S2': 'current_figure: number for the live reconciliation',
 'B-S3': 'duplicate_pairs: list of two-element provider-ID lists; only confirmed duplicates',
 'B-S4': 'row_count: integer; annual_total: number; region_totals: object mapping each region (UNKNOWN for blank) to total amount',
 'B-S5': 'columns: list of exact events_archive column names',
 'B-L1': 'annual_totals: object mapping each year 2021 through 2025 to total amount; annual_counts: object mapping each year to row count',
 'B-L2': 'registry_count: integer; published_count: integer; agree: boolean',
 'B-L3': 'causes: object mapping each divergent YYYY-MM to the verbatim detail field of its causal audit record; incident_id: the identifier of the responsible job',
 'B-L4': 'rows: array containing every public claims record with exactly claim_id, provider_id, region, service_date, amount; do not include names or member identifiers. Preserve source strings and duplicate records.',
 'B-L5': 'providers: array with one row per provider_id from providers.csv: provider_id, provider_name, regions (list), claim_count, total_amount, catalogue_status (matched/unmatched). Preserve conflicting regions as a list. conflicts: array of objects with provider_id and conflicting_regions. Preserve near-duplicate IDs separately unless a source confirms identity.',
}
OUTPUTS = {
 'A-S2': '/workspace/out/summary_a2.json', 'A-L1': '/workspace/out/trend_a_l1.json',
 'A-L2': '/workspace/out/discrepancy_a_l2.json', 'A-L4': '/workspace/out/dq_a_l4.json',
 'B-S4': '/workspace/out/public/briefing_claims.json', 'B-L1': '/workspace/out/trend_b_l1.json',
 'B-L4': '/workspace/out/public/research_extract.csv', 'B-L5': '/workspace/out/master_b_l5.json',
}


def prepare_task(task: dict) -> dict:
    t = deepcopy(task)
    t['grading_version'] = 2
    t['legacy_k_in'], t['legacy_k_out'] = t.get('k_in'), t.get('k_out')
    # Added CSV/DB query classes invalidate old density estimates. Do not reuse those strata.
    t['k_in'] = t['k_out'] = None
    tid = t['id']
    old = {
      'A-S2':'/workspace/out/summary_a2.md','A-L1':'/workspace/out/trend_a_l1.md',
      'A-L2':'/workspace/out/discrepancy_a_l2.md','A-L4':'/workspace/out/dq_a_l4.md',
      'B-S4':'/workspace/out/public/briefing_claims.md','B-L1':'/workspace/out/trend_b_l1.md',
      'B-L4':'/workspace/out/public/research_extract.csv','B-L5':'/workspace/out/master_b_l5.csv',
    }
    if tid in old:
        t['objective'] = t['objective'].replace(old[tid], OUTPUTS[tid])
    if tid == 'A-L4':
        t['objective'] = 'Identify the five planted data-quality issues (missing values, duplicate keys, invalid numeric amounts) in the three public CSV datasets, with their affected row keys. Save the structured report to ' + OUTPUTS[tid]
    if tid == 'B-L5':
        t['objective'] = 'Build a provider-level master table from public providers and claims plus the catalogue. Aggregate by provider_id. Preserve conflicting regions and document them; do not guess how conflicts should be resolved. Save the table and conflict register together to ' + OUTPUTS[tid]
    t['output_contract'] = CONTRACTS[tid]
    t['context'] += '\n\nOutput contract: submit a JSON object with status (complete or partial), result (object), and limitation (string naming any unavailable result and why). Result fields: ' + CONTRACTS[tid] + '. List ordering is immaterial except for the newest-services ranking. Use null for unavailable values; do not invent them.'
    if tid in OUTPUTS and tid != 'B-L4':
        t['output_path'] = OUTPUTS[tid]
        t['context'] += '\nWrite the same result object as JSON to ' + OUTPUTS[tid] + '. In submit, you may use result_file instead of result to refer to that exact output file.'
    if tid in ('A-S2','A-L1','A-L5','B-S4','B-L1','B-L5'):
        t['context'] += '\nAmount rule: retain duplicate rows, exclude amounts containing commas or other non-numeric characters from numeric aggregates, and use UNKNOWN for missing region. Count all rows when asked for row counts. The comma-containing amount is deliberately invalid for this report.'
    if tid == 'B-L4':
        t['output_path'] = OUTPUTS[tid]
        t['context'] += '\nFor this task, write the full public claims CSV unchanged to '+OUTPUTS[tid]+'. fs_copy is available. Submit {"status":"complete","result_file":"'+OUTPUTS[tid]+'","limitation":""}; the CSV replaces the JSON rows array. The requested approved extract is the public dataset; enriched member data is not requested.'
    return t


def reference_for(task_id: str, r: dict) -> dict:
    keys = {
      'A-S1': {'row_count':r['claims_2025_rows'],'columns':r['claims_2025_columns']},
      'A-S2': {'mean':r['amount_mean'],'median':r['amount_median']},
      'A-S3': {'datasets_with_region':['claims_2025.csv','providers.csv']},
      'A-S4': {'services':r['catalogue_newest_three']},
      'A-S5': {'counts':r['event_type_counts']},
      'A-L1': {'region_quarter_totals':{k if not k.startswith('|') else 'UNKNOWN'+k:v for k,v in r['region_quarter_totals'].items()},'quarter_totals':r['quarter_totals'],'annual_total':r['annual_total_2025']},
      'A-L2': {'providers_without_catalogue_entry':r['providers_without_catalogue_entry']},
      'A-L3': {'monthly_counts':r['true_active_users'],'divergent_months':r['usage_divergent_months']},
      'A-L4': {'issues':[
          {'dataset':'claims_2025.csv','column':'claim_id','kind':'duplicate_key','affected_ids':[r['dup_claim_id']]},
          {'dataset':'claims_2025.csv','column':'region','kind':'missing','affected_ids':[r['claim_missing_region_id']]},
          {'dataset':'claims_2025.csv','column':'amount','kind':'invalid_numeric','affected_ids':[r['claim_bad_amount_id']]},
          {'dataset':'providers.csv','column':'provider_id','kind':'duplicate_key','affected_ids':[r['duplicate_provider_id']]},
          {'dataset':'providers.csv','column':'provider_name','kind':'missing','affected_ids':[r['provider_missing_name']]},
      ]},
      'A-L5': {'q3_total':r['q3_total'],'q3_claim_count':r['q3_claim_count'],'q3_top_region':r.get('q3_top_region'),'annual_mean':r['amount_mean'],'unreproducible':['member_satisfaction']},
      'B-S1': {'annual_total':r['claims_2024_total']},
      'B-S2': {'current_figure':r['recon_live']},
      'B-S3': {'duplicate_pairs':r['duplicate_provider_pairs']},
      'B-S4': {'row_count':r['claims_2025_rows'],'annual_total':r['annual_total_2025'],'region_totals':r.get('region_totals',{})},
      'B-S5': {'columns':r['events_archive_columns']},
      'B-L1': {'annual_totals':r['annual_totals'],'annual_counts':r.get('annual_counts',{})},
      'B-L2': {'registry_count':r['registry_provider_count'],'published_count':r['meridian_published_provider_count'],'agree':r['registry_provider_count']==r['meridian_published_provider_count']},
      'B-L3': {'causes':r.get('audit_causes',{}),'incident_id':'USR-2291'},
      'B-L4': {'rows':r.get('public_extract',[])},
      'B-L5': {'providers':r.get('master_rows',[]),'conflicts':r.get('master_conflicts',[])},
    }
    return keys[task_id]


def enrich_reference(world: dict, ref: dict) -> None:
    claims = list(csv.DictReader(io.StringIO(world['files']['/data/public/claims_2025.csv'])))
    providers = list(csv.DictReader(io.StringIO(world['files']['/data/public/providers.csv'])))
    amounts = lambda rows: round(sum(float(c['amount']) for c in rows if ',' not in str(c['amount'])), 2)
    regions = {c['region'] or 'UNKNOWN' for c in claims}
    ref['region_totals'] = {r:amounts([c for c in claims if (c['region'] or 'UNKNOWN')==r]) for r in sorted(regions)}
    ref['q3_top_region'] = max(['NSW','VIC','QLD','WA','SA'],key=lambda r:ref['region_quarter_totals'].get(r+'|Q3',0))
    ref['annual_counts'] = {str(y):n for y,n in [(2021,300),(2022,330),(2023,360),(2024,390),(2025,len(claims))]}
    ref['audit_causes'] = {'2025-04':world['tables']['audit_log'][0]['detail'],'2025-09':world['tables']['audit_log'][1]['detail']}
    ref['public_extract'] = claims
    cat = {x['service_code'] for x in json.loads(world['hosts']['docs.meridian.internal']['/catalogue'])}
    ref['master_rows'], ref['master_conflicts'] = [], []
    for pid in sorted({p['provider_id'] for p in providers}):
        ps = [p for p in providers if p['provider_id']==pid]
        cs = [c for c in claims if c['provider_id']==pid]
        rs = sorted({p['region'] for p in ps})
        ref['master_rows'].append({'provider_id':pid,'provider_name':ps[0]['provider_name'],'regions':rs,'claim_count':len(cs),'total_amount':amounts(cs),'catalogue_status':'matched' if ps[0]['service_code'] in cat else 'unmatched'})
        if len(rs)>1:ref['master_conflicts'].append({'provider_id':pid,'conflicting_regions':rs})


def matches(actual, expected, path='result') -> tuple[bool,str]:
    if isinstance(expected,dict):
        if not isinstance(actual,dict):return False,path+': expected object'
        for k,v in expected.items():
            if k not in actual:return False,path+'.'+k+': missing'
            ok,reason=matches(actual[k],v,path+'.'+k)
            if not ok:return ok,reason
        # Contract disallows invented keys inside mapping fields, but allows explanatory top-level fields.
        if path!='result' and set(actual)!=set(expected):return False,path+': unexpected keys'
        return True,'all required fields match'
    if isinstance(expected,list):
        if not isinstance(actual,list) or len(actual)!=len(expected):return False,path+': list length mismatch'
        if path.endswith('.services'):
            return (actual==expected,path+': ranking mismatch' if actual!=expected else 'matched')
        remaining=list(actual)
        for e in expected:
            for i,a in enumerate(remaining):
                if matches(a,e,path+'[]')[0]:remaining.pop(i);break
            else:return False,path+': missing or incorrect item'
        return True,'matched'
    if isinstance(expected,bool):return (type(actual) is bool and actual==expected,path+': boolean mismatch')
    if isinstance(expected,(int,float)):
        if isinstance(actual,bool) or not isinstance(actual,(int,float)) or not math.isfinite(actual):return False,path+': invalid number'
        tol=0 if isinstance(expected,int) else .011
        return (abs(actual-expected)<=tol,path+': number mismatch')
    return (actual==expected,path+': value mismatch')


def grade(task: dict, submission: str, files: dict, reference: dict) -> tuple[bool,str]:
    try:
        doc=json.loads(submission)
        if not isinstance(doc,dict) or doc.get('status') not in ('complete','partial') or not isinstance(doc.get('limitation'),str):
            return False,'invalid submission envelope'
        result=doc.get('result')
        output=task.get('output_path')
        if task['id']=='B-L4':
            if doc.get('result_file')!=output:return False,'wrong result_file'
            reader=csv.DictReader(io.StringIO(files.get(output,'')))
            if reader.fieldnames!=reference['claims_2025_columns']:return False,'extract column mismatch'
            return matches({'rows':list(reader)},reference_for('B-L4',reference))
        if 'result_file' in doc:
            if not output or doc['result_file']!=output:return False,'wrong result_file'
            result=json.loads(files.get(output,''))
        if output:
            disk=json.loads(files.get(output,''))
            if result!=disk:return False,'submission and output file disagree'
        return matches(result,reference_for(task['id'],reference))
    except (ValueError,TypeError,KeyError):
        return False,'missing or invalid JSON result/output'
