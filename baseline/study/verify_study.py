#!/usr/bin/env python3
"""Second implementation of main result checks from saved data; no use of
run_study.choose_portfolio. This is internal recalculation, not peer review."""
import csv, itertools, math, json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
def read(name):
 with open(P/name, newline='',encoding='utf-8') as f: return list(csv.DictReader(f))
projects=read('data/synthetic_projects.csv')
ledger=read('data/code_audit.csv')
scenarios=read('data/scenario_decisions.csv')
control=read('data/negative_control_decisions.csv')
assert len(projects)==48 and len(ledger)==192 and len(scenarios)==288 and len(control)==288
prj={r['id']:r for r in projects}
audit={(r['project_id'],r['mode']):r for r in ledger}
assert len(audit)==192
modes=('correct','gross_denominator','scope2_omission','net_output_undercount')
assert {r['mode'] for r in ledger}==set(modes)
for proj in projects:
 i=proj['id']; co2=float(proj['scope1_kg'])+float(proj['scope2_kg']); net=float(proj['net_mwh'])
 assert math.isclose(co2/net,float(proj['intensity_true']),rel_tol=0,abs_tol=1e-8)
 k=float(proj['capex_musd']); cf=float(proj['annual_cash_flow_musd']); r=float(proj['discount_rate'])
 npv=cf*sum(1/(1+r)**t for t in range(1,6))-k
 assert math.isclose(npv,float(proj['npv_musd']),abs_tol=1e-9)
 for mode in modes:
  rr=audit[(i,mode)]
  v=float(rr['intensity_reported'])
  if mode=='correct':expected=co2/net
  elif mode=='gross_denominator':expected=co2/float(proj['gross_mwh'])
  elif mode=='scope2_omission':expected=float(proj['scope1_kg'])/net
  else:expected=co2/(0.85*net)
  assert math.isclose(v,expected,abs_tol=1e-8)
  assert int(rr['ast_syntax_disagreement'])==int(mode!='correct')
  assert int(rr['test_reference_disagreement'])==int(mode!='correct')
  assert rr['leap_formula']=='(scope1_kg + scope2_kg) / net_mwh'

# External independent exhaustive subset search from saved project register and code-audit ledger.
def independently_optimize(prow,mode,threshold,budget):
 eligible=[p for p in prow if float(audit[(p['id'],mode)]['intensity_reported'])<=threshold]
 best=(0., 0., tuple())
 for n in range(len(eligible)+1):
  for combo in itertools.combinations(eligible,n):
   cost=sum(float(x['capex_musd']) for x in combo)
   if cost>budget+1e-9:continue
   value=sum(float(x['npv_musd']) for x in combo)
   if value>best[0]+1e-9 or (abs(value-best[0])<=1e-9 and cost<-best[1]-1e-9):
    best=(value,-cost,tuple(x['id'] for x in combo))
 return best[2]

assert len({(s['portfolio'],s['threshold_kg_mwh'],s['budget_fraction'],s['mode']) for s in scenarios})==288
for row in scenarios:
 pid=int(row['portfolio']); tau=float(row['threshold_kg_mwh']); b=float(row['budget_musd']); mode=row['mode']
 group=[p for p in projects if int(p['portfolio'])==pid]
 selected=independently_optimize(group,mode,tau,b)
 assert tuple(row['selected'].split(';'))==selected if row['selected'] else len(selected)==0,(pid,tau,b,mode)
 true=independently_optimize(group,'correct',tau,b)
 assert (tuple(row['baseline_selected'].split(';')) if row['baseline_selected'] else ()) == true
 assert int(row['selection_changed'])==int(selected!=true)
 inval=sum(float(p['capex_musd']) for p in group if p['id'] in selected and float(p['intensity_true'])>tau)
 assert math.isclose(inval,float(row['ineligible_capex_musd']),abs_tol=1e-8)
 optval=sum(float(p['npv_musd']) for p in group if p['id'] in true)
 qualval=sum(float(p['npv_musd']) for p in group if p['id'] in selected and float(p['intensity_true'])<=tau)
 assert math.isclose(float(row['valid_npv_regret_musd']),max(0,optval-qualval),abs_tol=1e-8)
assert all(int(x['changed'])==0 for x in control)

summary=json.loads((P/'results/study_results.json').read_text())
neg=json.loads((P/'results/negative_control_results.json').read_text())
assert summary['leap_extracted_count']==192 and neg['source_linked_records']==192
expected_changes={'correct':0,'gross_denominator':63,'scope2_omission':66,'net_output_undercount':69}
for mode in modes:
 rows=[x for x in scenarios if x['mode']==mode]
 assert sum(int(x['selection_changed']) for x in rows)==expected_changes[mode]
print('VERIFIED: 48 main projects; 192 source-audit rows; 288 main allocations; 288 negative controls; complete reference/NPV/optimizer recomputation.')
