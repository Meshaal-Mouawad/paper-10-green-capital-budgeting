#!/usr/bin/env python3
"""Controlled LEAP/green-investment decision-sensitivity study.

Research units: 48 synthetic projects arranged in 8 designed six-project
portfolios; three deliberate source-implementation defects plus control;
three analytical eligibility thresholds and three capital budgets.
This is an exact deterministic scenario experiment, not a sampled survey.
"""
import ast
import csv
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LEAP_ROOT = ROOT / 'source_snapshot'
if not LEAP_ROOT.is_dir():
    LEAP_ROOT = ROOT / 'reproducibility' / 'leap_extract_core'
if not LEAP_ROOT.is_dir():
    raise SystemExit('LEAP source modules are required for actual extraction. See README.')
# Import the byte-preserved LEAP extractor and its relative formula-parser
# dependency without executing the optional Bluebook web/AI pipeline imported
# by the package-level __init__.py. The files themselves are unchanged.
from types import ModuleType
from importlib import import_module
package_dir = LEAP_ROOT / 'bluebook_generator'
if not (package_dir / 'kpi_extractor.py').is_file():
    raise SystemExit(f'Cannot load frozen LEAP extractor from {package_dir}')
package = ModuleType('bluebook_generator')
package.__path__ = [str(package_dir)]
sys.modules['bluebook_generator'] = package
find_kpis_in_directory = import_module('bluebook_generator.kpi_extractor').find_kpis_in_directory

N_PORTFOLIOS = 8
N_PROJECTS = 6
DISCOUNT_YEARS = 5
THRESHOLDS = (380.0, 400.0, 420.0)  # kgCO2e/MWh, *study-defined policy*, not external law
BUDGET_FRACTIONS = (0.45, 0.60, 0.75)
MODES = ('correct', 'gross_denominator', 'scope2_omission', 'net_output_undercount')
FORMULA = '(scope1_kg + scope2_kg) / net_mwh'
RETURN_EXPR = {
    'correct': '(scope1_kg + scope2_kg) / net_mwh',
    'gross_denominator': '(scope1_kg + scope2_kg) / gross_mwh',
    'scope2_omission': 'scope1_kg / net_mwh',
    'net_output_undercount': '(scope1_kg + scope2_kg) / (net_mwh * 0.85)',
}


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)


def stable_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def generate_projects():
    projects=[]
    bases=(330., 378., 392., 407., 429., 465.)
    for p in range(N_PORTFOLIOS):
        for j in range(N_PROJECTS):
            net_mwh=80000 + 4500*j + 2750*p + ((p*j)%3)*700
            target_intensity = bases[j] + (p-3.5)*4.0 + ((((p+1)*(j+2))%4)-1.5)*2.0
            scope2_share = 0.09 + 0.025*((p+j)%5)
            total_emissions = target_intensity*net_mwh
            scope1 = total_emissions*(1.0-scope2_share)
            scope2 = total_emissions*scope2_share
            gross_mwh = net_mwh*(1.07 + 0.025*((p+j)%5))
            capex=18.0 + 5*j + 2*(p%3) + ((j+2*p)%3)*2
            discount=0.07 + 0.01*((p+j)%4)
            annual=capex*(0.25 +0.02*((p*3+j*2)%6))
            npv = -capex + sum(annual/(1.0+discount)**t for t in range(1,DISCOUNT_YEARS+1))
            projects.append({'id':f'P{p+1:02d}_{j+1:02d}', 'portfolio':p+1,
                'net_mwh':net_mwh, 'gross_mwh':gross_mwh,
                'scope1_kg':scope1, 'scope2_kg':scope2,
                'intensity_true':(scope1+scope2)/net_mwh,
                'capex_musd':capex,'annual_cash_flow_musd':annual,
                'discount_rate':discount,'npv_musd':npv,
                'scope2_fraction':scope2_share})
    return projects


def emit_fixture(project,mode,folder):
    fn=f'{project["id"]}_{mode}.py'
    path=folder/fn
    expr=RETURN_EXPR[mode]
    content=f'''# KPI: Synthetic Green Financing Emissions Intensity {project["id"]} {mode}\n# Description: Source-traceable emissions intensity for investment screening.\n# Objective: Test a study-defined eligibility rule for SDG-linked capital allocation.\n# Formula: {FORMULA}\n# Unit: kgCO2e/MWh\n# Data Source: deterministic synthetic project register; Scope 1 and Scope 2.\n# Accountable Owner: Scenario Researcher\n# Input: scope1_kg, scope2_kg, net_mwh, gross_mwh.\ndef calculate_intensity(scope1_kg, scope2_kg, net_mwh, gross_mwh):\n    return {expr}\n'''
    path.write_text(content, encoding='utf-8')
    return path


def expr_canonical(expr):
    return ast.dump(ast.parse(expr, mode='eval').body, annotate_fields=True, include_attributes=False)


def choose_portfolio(pool, scores, threshold, budget):
    """Exact exhaustive 2^6 binary portfolio choice; maximize total discounted NPV.
    Tie-break by lower capital and lexicographically sorted IDs.
    """
    eligible=[x for x in pool if scores[x['id']]<=threshold]
    winner=(0.0,0.0,tuple())
    for bits in itertools.product((0,1), repeat=len(eligible)):
        selected=tuple(x for x,b in zip(eligible,bits) if b)
        capex=sum(x['capex_musd'] for x in selected)
        if capex > budget+1e-10:continue
        gain=sum(x['npv_musd'] for x in selected)
        cand=(gain,-capex,tuple(x['id'] for x in selected))
        if (cand[0]>winner[0]+1e-10 or
            (abs(cand[0]-winner[0])<=1e-10 and cand[1]>winner[1]+1e-10)):
            winner=cand
    return winner[2]


def main():
    data=ROOT/'data'; results=ROOT/'results'; fixture_dir=ROOT/'study'/'finance_kpi_sources'
    fixture_dir.mkdir(parents=True, exist_ok=True)
    results.mkdir(parents=True, exist_ok=True)
    projects=generate_projects()
    scores={mode:{} for mode in MODES}
    fixture_paths={}
    for x in projects:
        for mode in MODES:
            path=emit_fixture(x,mode,fixture_dir)
            fixture_paths[(x['id'],mode)]=path
            ns={}
            compiled=compile(path.read_text(encoding='utf-8'),str(path),'exec')
            exec(compiled,ns,ns)
            scores[mode][x['id']]=ns['calculate_intensity'](x['scope1_kg'],x['scope2_kg'],x['net_mwh'],x['gross_mwh'])
            assert math.isfinite(scores[mode][x['id']])
            if mode=='correct':
                assert abs(scores[mode][x['id']]-x['intensity_true'])<1e-9
    # ACTUAL LEAP extraction: no simulation of what its code returns
    extracted,stats=find_kpis_in_directory(str(fixture_dir),include_stats=True)
    extracted_by_file={Path(r['file_path']).resolve():r for r in extracted}
    assert len(extracted)==len(fixture_paths),(len(extracted),len(fixture_paths))
    mutation=[]
    for x in projects:
        for mode in MODES:
            path=fixture_paths[(x['id'],mode)]
            record=extracted_by_file.get(path.resolve())
            assert record is not None, str(path)
            assert record['formula'].strip()==FORMULA, (record['formula'],FORMULA)
            source_return=next(n.value for n in ast.walk(ast.parse(path.read_text())) if isinstance(n,ast.Return))
            formula_tree=expr_canonical(record['formula'])
            expr_tree=ast.dump(source_return,annotate_fields=True,include_attributes=False)
            # A separately implemented syntax match applied to LEAP's evidence record;
            # it is NOT represented as a native semantic-verification feature of LEAP.
            syntax_mismatch=(expr_tree != formula_tree)
            numeric_mismatch=abs(scores[mode][x['id']]-x['intensity_true'])>1e-7
            assert syntax_mismatch==(mode!='correct')
            assert numeric_mismatch==(mode!='correct')
            mutation.append({'project_id':x['id'],'mode':mode,
                'source_file':path.name,'source_line':record['file_line'],
                'leap_detected_name':record['name'],
                'leap_detection_kind':record.get('detection_kind',''),
                'leap_formula':record['formula'],
                'implemented_expression':ast.unparse(source_return),
                'source_anchored':bool(record.get('code_context')),
                'ast_syntax_disagreement':int(syntax_mismatch),
                'test_reference_disagreement':int(numeric_mismatch),
                'intensity_true':x['intensity_true'],
                'intensity_reported':scores[mode][x['id']],
                'error_kg_mwh':scores[mode][x['id']]-x['intensity_true'],
                'source_sha256':stable_hash(path)})
    decisions=[]
    for pid in range(1,N_PORTFOLIOS+1):
        pool=[x for x in projects if x['portfolio']==pid]
        total_cost=sum(x['capex_musd'] for x in pool)
        truth={x['id']:x['intensity_true'] for x in pool}
        for threshold in THRESHOLDS:
            for budget_frac in BUDGET_FRACTIONS:
                budget=budget_frac*total_cost
                true_sel=choose_portfolio(pool,truth,threshold,budget)
                true_npv=sum(x['npv_musd'] for x in pool if x['id'] in true_sel)
                for mode in MODES:
                    actual_sel=choose_portfolio(pool,scores[mode],threshold,budget)
                    actual_npv=sum(x['npv_musd'] for x in pool if x['id'] in actual_sel)
                    valid_sel=[x for x in pool if x['id'] in actual_sel and x['intensity_true']<=threshold]
                    valid_npv=sum(x['npv_musd'] for x in valid_sel)
                    violation_capex=sum(x['capex_musd'] for x in pool if x['id'] in actual_sel and x['intensity_true']>threshold)
                    false_eligible=sum(scores[mode][x['id']]<=threshold and x['intensity_true']>threshold for x in pool)
                    false_ineligible=sum(scores[mode][x['id']]>threshold and x['intensity_true']<=threshold for x in pool)
                    regret=max(0.,true_npv-valid_npv)
                    assert regret> -1e-7
                    decisions.append({'portfolio':pid,'threshold_kg_mwh':threshold,
                        'budget_fraction':budget_frac,'budget_musd':budget,
                        'mode':mode,'baseline_selected':';'.join(true_sel),
                        'selected':';'.join(actual_sel),
                        'selection_changed':int(true_sel!=actual_sel),
                        'baseline_npv_musd':true_npv,
                        'selected_nominal_npv_musd':actual_npv,
                        'eligible_npv_musd':valid_npv,
                        'valid_npv_regret_musd':regret,
                        'ineligible_capex_musd':violation_capex,
                        'false_eligible_projects':false_eligible,
                        'false_ineligible_projects':false_ineligible,
                        'baseline_project_count':len(true_sel),
                        'selected_project_count':len(actual_sel)})
    fields=list(mutation[0]);write_csv(data/'code_audit.csv',mutation,fields)
    write_csv(data/'synthetic_projects.csv',projects,list(projects[0]))
    write_csv(data/'scenario_decisions.csv',decisions,list(decisions[0]))
    source_summary=[]
    for mode in MODES:
        a=[r for r in decisions if r['mode']==mode]
        source_summary.append({'mode':mode,'n_conditions':len(a),
            'selection_changes':sum(r['selection_changed'] for r in a),
            'selection_change_pct':round(100*sum(r['selection_changed'] for r in a)/len(a),2),
            'any_invalid_allocation':sum(r['ineligible_capex_musd']>1e-8 for r in a),
            'sum_invalid_capex_musd':round(sum(r['ineligible_capex_musd'] for r in a),3),
            'mean_invalid_capex_per_condition_musd':round(sum(r['ineligible_capex_musd'] for r in a)/len(a),3),
            'mean_valid_npv_regret_musd':round(sum(r['valid_npv_regret_musd'] for r in a)/len(a),3),
            'max_valid_npv_regret_musd':round(max(r['valid_npv_regret_musd'] for r in a),3),
            'n_eligibility_false_positives':sum(r['false_eligible_projects'] for r in a),
            'n_eligibility_false_negatives':sum(r['false_ineligible_projects'] for r in a)})
    write_csv(results/'mode_summary.csv',source_summary,list(source_summary[0]))
    by_threshold=[]
    for t in THRESHOLDS:
        for m in MODES[1:]:
            a=[r for r in decisions if r['mode']==m and r['threshold_kg_mwh']==t]
            by_threshold.append({'threshold_kg_mwh':t,'mode':m,'n_conditions':len(a),
                'n_selection_changed':sum(r['selection_changed'] for r in a),
                'mean_npv_regret_musd':round(sum(r['valid_npv_regret_musd'] for r in a)/len(a),3),
                'total_invalid_capex_musd':round(sum(r['ineligible_capex_musd'] for r in a),3)})
    write_csv(results/'threshold_summary.csv',by_threshold,list(by_threshold[0]))
    by_budget=[]
    for b in BUDGET_FRACTIONS:
        for m in MODES[1:]:
            a=[r for r in decisions if r['mode']==m and r['budget_fraction']==b]
            by_budget.append({'budget_fraction':b,'mode':m,'n_conditions':len(a),
                'n_selection_changed':sum(r['selection_changed'] for r in a),
                'mean_npv_regret_musd':round(sum(r['valid_npv_regret_musd'] for r in a)/len(a),3),
                'total_invalid_capex_musd':round(sum(r['ineligible_capex_musd'] for r in a),3)})
    write_csv(results/'budget_summary.csv',by_budget,list(by_budget[0]))
    manifest={'reference_date':'2026-11-22','study':'synthetic controlled calculation discrepancy and capital-allocation sensitivity',
         'leap_source':'user supplied AI-Powered_KPI_Extractor_Interactive_Bluebook_Generator.zip',
         'leap_module':'bluebook_generator.kpi_extractor.find_kpis_in_directory',
         'study_units':{'synthetic_portfolios':N_PORTFOLIOS,'synthetic_projects':len(projects),
             'source_fixtures':len(fixture_paths),'decision_conditions':len(decisions),
             'paired_fault_conditions':sum(r['mode']!='correct' for r in decisions)},
         'design':{'thresholds':THRESHOLDS,'budget_fractions':BUDGET_FRACTIONS,
             'modes':MODES,'years':DISCOUNT_YEARS, 'source_formula':FORMULA},
         'scan_stats':stats,'leap_extracted_count':len(extracted),
         'source_anchor_count':sum(r['source_anchored'] for r in mutation),
         'syntactic_disagreements':sum(r['ast_syntax_disagreement'] for r in mutation),
         'numeric_reference_disagreements':sum(r['test_reference_disagreement'] for r in mutation),
         'results_by_mode':source_summary,'results_by_threshold':by_threshold,'results_by_budget':by_budget}
    (results/'study_results.json').write_text(json.dumps(manifest,indent=2,default=str),encoding='utf-8')
    print(json.dumps({'units':manifest['study_units'],'extracted':len(extracted),'summary':source_summary},indent=2))
    return manifest

if __name__=='__main__': main()
