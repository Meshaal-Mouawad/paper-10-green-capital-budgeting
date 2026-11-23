#!/usr/bin/env python3
"""Predeclared distance-to-boundary negative control for the IJFS scenario study.

48 separate synthetic projects, same financial inputs as main scenarios, but
reference intensities far enough from every studied threshold that all
three designed defect operators preserve classification. 288 conditions.
"""
import sys, csv, json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'study'))
from run_study import (generate_projects, MODES, THRESHOLDS, BUDGET_FRACTIONS,
                       choose_portfolio, RETURN_EXPR, emit_fixture, write_csv,
                       find_kpis_in_directory)

def main():
    base=generate_projects()
    distant_bases=(180.,220.,260.,560.,620.,700.)
    sample=[]; j=0
    for x in base:
        p=x['portfolio']-1
        ind=j%6
        y=dict(x)
        y['id']=f'NC{p+1:02d}_{ind+1:02d}'
        y['intensity_true']=distant_bases[ind] + (p-3.5)*2
        new_total=y['intensity_true']*y['net_mwh']
        y['scope1_kg']=new_total*(1-y['scope2_fraction'])
        y['scope2_kg']=new_total*y['scope2_fraction']
        sample.append(y);j+=1
    folder=ROOT/'study'/'negative_control_kpi_sources'
    folder.mkdir(exist_ok=True)
    for x in sample:
        for m in MODES:emit_fixture(x,m,folder)
    extracted,stats=find_kpis_in_directory(str(folder),include_stats=True)
    assert len(extracted)==192, len(extracted)
    decision=[]
    for pid in range(1,9):
        pool=[x for x in sample if x['portfolio']==pid]
        for tau in THRESHOLDS:
            for budget_pct in BUDGET_FRACTIONS:
                budget=sum(x['capex_musd'] for x in pool)*budget_pct
                true_score={x['id']:x['intensity_true'] for x in pool}
                ref=choose_portfolio(pool,true_score,tau,budget)
                for m in MODES:
                    expr_scores={}
                    for x in pool:
                        if m=='correct': v=x['intensity_true']
                        elif m=='gross_denominator':v=(x['scope1_kg']+x['scope2_kg'])/x['gross_mwh']
                        elif m=='scope2_omission':v=x['scope1_kg']/x['net_mwh']
                        else:v=(x['scope1_kg']+x['scope2_kg'])/(x['net_mwh']*.85)
                        expr_scores[x['id']]=v
                        assert (v<=tau)==(x['intensity_true']<=tau), (m,x['id'],v,x['intensity_true'],tau)
                    actual=choose_portfolio(pool,expr_scores,tau,budget)
                    assert actual==ref,(pid,tau,budget,m,ref,actual)
                    decision.append({'portfolio':pid,'threshold':tau,'budget_fraction':budget_pct,
                                     'mode':m,'changed':int(actual!=ref)})
    write_csv(ROOT/'data'/'negative_control_projects.csv',sample,list(sample[0]))
    write_csv(ROOT/'data'/'negative_control_decisions.csv',decision,list(decision[0]))
    record={'negative_control_projects':len(sample),'source_fixtures':len(extracted),'decision_conditions':len(decision),
       'changes':sum(x['changed'] for x in decision),
       'thresholds':THRESHOLDS,'budget_fractions':BUDGET_FRACTIONS,
       'description':'Distant-intensity source/error controls preserve eligibility and allocation for every studied threshold/budget',
       'source_linked_records':len(extracted)}
    (ROOT/'results'/'negative_control_results.json').write_text(json.dumps(record,indent=2))
    print(json.dumps(record,indent=2))

if __name__=='__main__':main()
