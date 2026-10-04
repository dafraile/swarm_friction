"""Independently derive core reference quantities from frozen source rows, using Decimal."""
import csv
from collections import Counter,defaultdict
from decimal import Decimal,InvalidOperation,ROUND_HALF_EVEN
import io
import json
from pathlib import Path
import statistics
import sys


def read(text):return list(csv.DictReader(io.StringIO(text)))
def amount(s):
    try:return Decimal(s)
    except InvalidOperation:return None

def check(path):
    w=json.loads(path.read_text());r=w['reference'];checks=0;errors=[]
    def equal(name,actual,expected):
        nonlocal checks
        checks+=1
        if actual!=expected:errors.append({'name':name,'actual':actual,'expected':expected})
    claims=read(w['files']['/data/public/claims_2025.csv'])
    providers=read(w['files']['/data/public/providers.csv'])
    numeric=[amount(c['amount']) for c in claims if amount(c['amount']) is not None]
    rounded=lambda v:float(v.quantize(Decimal('.01'),rounding=ROUND_HALF_EVEN))
    equal('row_count',len(claims),r['claims_2025_rows'])
    equal('columns',list(claims[0]),r['claims_2025_columns'])
    equal('mean',rounded(sum(numeric)/len(numeric)),r['amount_mean'])
    equal('median',rounded(statistics.median(numeric)),r['amount_median'])
    equal('annual_total',rounded(sum(numeric)),r['annual_total_2025'])
    totals=defaultdict(Decimal);rq=defaultdict(Decimal);regions=defaultdict(Decimal)
    for c in claims:
        v=amount(c['amount'])
        if v is None:continue
        q='Q'+str((int(c['service_date'][5:7])-1)//3+1)
        totals[q]+=v;rq[c['region']+'|'+q]+=v;regions[c['region'] or 'UNKNOWN']+=v
    equal('quarter_totals',{k:rounded(v) for k,v in totals.items()},r['quarter_totals'])
    equal('region_quarter_totals',{k:rounded(v) for k,v in rq.items()},r['region_quarter_totals'])
    equal('region_totals',{k:rounded(v) for k,v in regions.items()},r['region_totals'])
    equal('q3_count',sum(c['service_date'][5:7] in ['07','08','09'] for c in claims),r['q3_claim_count'])
    for year in range(2021,2026):
        rows=claims if year==2025 else read(w['files'][f'/archive/claims_{year}.csv'])
        equal(f'annual_count_{year}',len(rows),r['annual_counts'][str(year)])
        equal(f'annual_total_{year}',rounded(sum(amount(c['amount']) for c in rows if amount(c['amount']) is not None)),r['annual_totals'][str(year)])
    active=defaultdict(set)
    for e in w['tables']['events']:active[e['month']].add(e['user_id'])
    equal('monthly_active',{m:len(ids) for m,ids in active.items()},r['true_active_users'])
    equal('event_type_counts',dict(Counter(e['event_type'] for e in w['tables']['events'])),r['event_type_counts'])
    catalogue=json.loads(w['hosts']['docs.meridian.internal']['/catalogue'])
    codes={c['service_code'] for c in catalogue}
    equal('unmatched_provider_names',sorted({p['provider_name'] for p in providers if p['provider_name'] and p['service_code'] not in codes}),r['providers_without_catalogue_entry'])
    for p in r['master_rows']:
        pp=[x for x in providers if x['provider_id']==p['provider_id']]
        cc=[x for x in claims if x['provider_id']==p['provider_id']]
        equal(p['provider_id']+' count',len(cc),p['claim_count'])
        equal(p['provider_id']+' amount',rounded(sum((amount(c['amount']) for c in cc if amount(c['amount']) is not None),Decimal(0))),p['total_amount'])
        equal(p['provider_id']+' regions',sorted({x['region'] for x in pp}),p['regions'])
        equal(p['provider_id']+' catalogue','matched' if pp[0]['service_code'] in codes else 'unmatched',p['catalogue_status'])
    return {'world':str(path),'checks':checks,'errors':errors}

if __name__=='__main__':
    root=Path(sys.argv[1] if len(sys.argv)>1 else 'runs/repair_v2')
    rows=[check(p) for p in sorted(root.glob('*/world_*.json'))]
    report={'worlds':rows,'checks':sum(r['checks'] for r in rows),'errors':sum(len(r['errors']) for r in rows)}
    if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));sys.exit(bool(report['errors']))
