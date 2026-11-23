#!/usr/bin/env python3
"""Rebuild the IJFS scenario model directly from published equations, using exact fractions.

Usage: python3 independent_finance.py BASELINE_DIRECTORY --output DIRECTORY
Only the Python standard library is required. The archive is opened read-only. No archived
Python module is loaded, executed, or used to generate the independent answer.
"""
import argparse
import csv
import hashlib
import io
import itertools
import json
from fractions import Fraction as F
from pathlib import Path
from public_inputs import ScientificInputs, SCIENCE_MANIFEST_SHA256

MODES = ("correct", "gross_denominator", "scope2_omission", "net_output_undercount")
TAUS = (380, 400, 420)
BUDGETS = tuple(map(F, ("0.45", "0.60", "0.75")))
ZERO = F(0)
TOL = F("0.0000001")  # Absolute bound for archived unrounded binary-float exports.


def read_csv(z, name):
    with z.open(name) as fp:
        return list(csv.DictReader(io.TextIOWrapper(fp)))


def formatted(v):
    if isinstance(v, F):
        return str(v.numerator) if v.denominator == 1 else f"{float(v):.12g}"
    return v


def write_csv(path, rows):
    with path.open("w", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows({k: formatted(v) for k, v in row.items()} for row in rows)


def records(setname, p):
    main = setname == "main"
    project_list = []
    for j in range(6):
        net = 80000 + 4500*j + 2750*p + 700*((p*j) % 3)
        gross = net * (F("1.07") + F(".025")*((p+j) % 5))
        s = F(".09") + F(".025")*((p+j) % 5)
        k = 18 + 5*j + 2*(p % 3) + 2*((j+2*p) % 3)
        cash = k*(F(".25") + F(".02")*((3*p+2*j) % 6))
        r = F(".07") + F(".01")*((p+j) % 4)
        value = sum(cash / (1+r)**t for t in range(1, 6)) - k
        if main:
            base = (330, 378, 392, 407, 429, 465)[j]
            e = base + 4*(p-F("3.5")) + 2*((p+1)*(j+2) % 4 - F("1.5"))
        else:
            e = (180, 220, 260, 560, 620, 700)[j] + 2*(p-F("3.5"))
        row = dict(id=f"{'P' if main else 'NC'}{p+1:02}_{j+1:02}", portfolio=p+1,
                   net_mwh=net, gross_mwh=gross, scope1_kg=e*net*(1-s),
                   scope2_kg=e*net*s, intensity_true=e, capex_musd=k,
                   annual_cash_flow_musd=cash, discount_rate=r, npv_musd=value,
                   scope2_fraction=s)
        project_list.append(row)
    return project_list


def intensities(x):
    mass = x["scope1_kg"] + x["scope2_kg"]
    net = x["net_mwh"]
    return dict(zip(MODES, (mass/net, mass/x["gross_mwh"], x["scope1_kg"]/net,
                            mass/(F(".85")*net))))


def subset_library(projects):
    # The admissible subsets share this independent, globally fixed preference order.
    sets = []
    for mask in range(1 << len(projects)):
        items = [x for j, x in enumerate(projects) if mask & (1 << j)]
        ids = ";".join(x["id"] for x in items)
        sets.append(dict(mask=mask, k=sum(x["capex_musd"] for x in items),
                         v=sum((x["npv_musd"] for x in items), ZERO), ids=ids))
    return sorted(sets, key=lambda x: (-x["v"], x["k"], x["ids"]))


def solve(pool, eligible, budget):
    return next(x for x in pool if x["mask"] & ~eligible == 0 and x["k"] <= budget)


def classify(projects, tau, mode):
    return sum(1 << j for j, x in enumerate(projects) if intensities(x)[mode] <= tau)


def compare(baseline, new, exact_strings=(), tolerance=TOL):
    """Archived float roundoff is bounded. IDs and integer counts must match exactly."""
    deltas = {}
    for k, raw in baseline.items():
        if k in exact_strings:
            deltas[k] = int(str(raw) != str(new[k]))
        else:
            deltas[k] = F(str(new[k])) - F(str(raw))
    errors = [k for k, d in deltas.items()
              if abs(d) > (0 if k in exact_strings else tolerance)]
    return deltas, errors


def evaluate_grid(z):
    all_rows, project_checks, decision_checks, classifications, derived = [], [], [], [], []
    for case, project_file, decision_file in [
        ("main", "synthetic_projects", "scenario_decisions"),
        ("control", "negative_control_projects", "negative_control_decisions"),
    ]:
        src = read_csv(z, f"data/{project_file}.csv")
        expected_projects = {x["id"]: x for x in src}
        assert len(expected_projects) == len(src) == 48
        src = read_csv(z, f"data/{decision_file}.csv")
        decision_map = {(int(x["portfolio"]), F(x.get("threshold", x.get("threshold_kg_mwh"))),
                         F(x["budget_fraction"]), x["mode"]): x for x in src}
        assert len(decision_map) == len(src) == 288
        for p in range(8):
            xs = records(case, p)
            pool = subset_library(xs)
            by_mask = {x["mask"]: x for x in pool}
            for x in xs:
                delta, bad = compare(expected_projects[x["id"]], x, ("id",))
                project_checks.append(dict(design=case, id=x["id"],
                                           differences_outside_tolerance=len(bad),
                                           differing_fields="|".join(bad),
                                           **{f"delta_{k}": v for k, v in delta.items()}))
                scores = intensities(x)
                for tau, mode in itertools.product(TAUS, MODES):
                    true, report = scores["correct"], scores[mode]
                    classifications.append(dict(design=case, id=x["id"], portfolio=p+1,
                        threshold=tau, mode=mode, true_kg_mwh=true, reported_kg_mwh=report,
                        error_kg_mwh=report-true, distance_to_threshold=abs(true-tau),
                        strict_absolute_margin_certified=int(abs(report-true)<abs(true-tau)),
                        true_eligible=int(true<=tau), reported_eligible=int(report<=tau),
                        false_admit=int(report<=tau<true), false_exclude=int(true<=tau<report)))
            for tau, frac in itertools.product(TAUS, BUDGETS):
                budget = sum(x["capex_musd"] for x in xs)*frac
                truth = classify(xs, tau, "correct")
                reference = solve(pool, truth, budget)
                for mode in MODES:
                    report = classify(xs, tau, mode)
                    sel = solve(pool, report, budget)
                    keep = by_mask[sel["mask"] & truth]
                    invalid = by_mask[sel["mask"] & ~truth]
                    common = truth & report
                    common_value = solve(pool, common, budget)["v"]
                    residual_value = solve(pool, common, budget-invalid["k"])["v"]
                    exclusion = reference["v"] - common_value
                    displacement = common_value - residual_value
                    gap = reference["v"] - keep["v"]
                    changed = int(sel["mask"] != reference["mask"])
                    new_admissions = report & ~truth
                    lost = truth & ~report
                    forced = next((x for x in pool if x["mask"] & ~report == 0 and
                                   x["k"]<=budget and x["mask"] & new_admissions), None)
                    reference_still_feasible = reference["mask"] & ~report == 0
                    # Once the incumbent remains feasible, only a subset containing a
                    # previously inadmissible project can outrank it.
                    outranks = (forced is not None and
                                (-forced["v"], forced["k"], forced["ids"]) <
                                (-reference["v"], reference["k"], reference["ids"]))
                    certificate = (not reference_still_feasible) or outranks
                    tied_objectives = sum(x["mask"] & ~report == 0 and x["k"] <= budget
                                         and x["v"] == sel["v"] for x in pool)
                    assert (keep["v"] == residual_value and exclusion >= 0 and
                            displacement >= 0 and gap == exclusion + displacement and
                            bool(changed) == certificate)
                    key = (p+1, tau, frac, mode)
                    row = dict(portfolio=p+1, threshold_kg_mwh=tau, budget_fraction=frac,
                               budget_musd=budget, mode=mode, baseline_selected=reference["ids"],
                               selected=sel["ids"], selection_changed=changed,
                               baseline_npv_musd=reference["v"], selected_nominal_npv_musd=sel["v"],
                               eligible_npv_musd=keep["v"], valid_npv_regret_musd=gap,
                               ineligible_capex_musd=invalid["k"],
                               false_eligible_projects=new_admissions.bit_count(),
                               false_ineligible_projects=lost.bit_count(),
                               baseline_project_count=reference["mask"].bit_count(),
                               selected_project_count=sel["mask"].bit_count())
                    if case == "main":
                        comparator = row
                    else:
                        comparator = dict(portfolio=p+1, threshold=tau, budget_fraction=frac,
                                          mode=mode, changed=changed)
                    old = decision_map[key]
                    delta, bad = compare(old, comparator, ("mode", "selected", "baseline_selected"))
                    diffrow = dict(design=case, portfolio=p+1, threshold=tau, budget_fraction=frac,
                                   mode=mode, archived_changed=old.get("selection_changed", old.get("changed")),
                                   independent_changed=changed, archived_reference=old.get("baseline_selected", ""),
                                   independent_reference=reference["ids"], archived_selection=old.get("selected",""),
                                   independent_selection=sel["ids"], differing_fields="|".join(bad))
                    for fld in ("budget_musd", "baseline_npv_musd", "selected_nominal_npv_musd",
                                "eligible_npv_musd", "valid_npv_regret_musd", "ineligible_capex_musd",
                                "false_eligible_projects", "false_ineligible_projects",
                                "baseline_project_count", "selected_project_count"):
                        diffrow[f"delta_{fld}"] = delta.get(fld, "")
                    decision_checks.append(diffrow)
                    derived.append(dict(design=case, portfolio=p+1, threshold=tau, budget_fraction=frac,
                        mode=mode, project_labels_changed=int(truth != report),
                        reference_still_feasible=int(reference_still_feasible), newly_admitted=by_mask[new_admissions]["ids"],
                        newly_excluded=by_mask[lost]["ids"], financed_false_admissions=invalid["ids"],
                        best_feasible_with_any_new_admission=forced["ids"] if forced else "",
                        best_with_new_admission_minus_reference_npv_musd=forced["v"]-reference["v"] if forced else "",
                        best_new_entrant_outranks_reference=int(outranks), certificate_predicts_change=int(certificate),
                        selection_changed=changed, number_of_optima_at_max_npv=tied_objectives,
                        financed_false_admission_capex_musd=invalid["k"], common_set_value_musd=common_value,
                        remaining_budget_musd=budget-invalid["k"], common_set_at_remaining_budget_npv_musd=residual_value,
                        exclusion_component_musd=exclusion, displacement_component_musd=displacement,
                        qualified_shortfall_musd=gap, decomposition_residual_musd=gap-exclusion-displacement,
                        change_but_zero_shortfall=int(changed and gap==0)))
                    all_rows.append(dict(design=case, **row))
    return all_rows, project_checks, decision_checks, classifications, derived


def group_metrics(rows, dimension=None):
    axis = None if dimension is None else rows[0][dimension]
    n = len(rows)
    gaps = [x["valid_npv_regret_musd"] for x in rows]
    capital = [x["ineligible_capex_musd"] for x in rows]
    changes = sum(x["selection_changed"] for x in rows)
    if dimension:
        return {dimension: axis, "mode": rows[0]["mode"], "n_conditions": n,
                "n_selection_changed": changes, "mean_npv_regret_musd":sum(gaps)/n,
                "total_invalid_capex_musd":sum(capital)}
    return dict(mode=rows[0]["mode"], n_conditions=n, selection_changes=changes,
                selection_change_pct=F(100*changes,n), any_invalid_allocation=sum(k>0 for k in capital),
                sum_invalid_capex_musd=sum(capital), mean_invalid_capex_per_condition_musd=F(sum(capital),n),
                mean_valid_npv_regret_musd=sum(gaps)/n, max_valid_npv_regret_musd=max(gaps),
                n_eligibility_false_positives=sum(x["false_eligible_projects"] for x in rows),
                n_eligibility_false_negatives=sum(x["false_ineligible_projects"] for x in rows))


def compare_summaries(z, all_rows):
    study = json.loads(z.read("results/study_results.json"))
    diffs = []
    for slug, dimension in [("mode",None), ("threshold","threshold_kg_mwh"), ("budget","budget_fraction")]:
        for origin, src in [(f"results/{slug}_summary.csv", read_csv(z, f"results/{slug}_summary.csv")),
                            (f"results/study_results.json#results_by_{slug}", study[f"results_by_{slug}"])]:
            assert len(src) == (4 if slug == "mode" else 9)
            observed_keys = set()
            for row in src:
                mode = row["mode"]
                axis = F(str(row[dimension])) if dimension else None
                assert (mode, axis) not in observed_keys
                observed_keys.add((mode, axis))
                sample = [x for x in all_rows if x["design"] == "main" and x["mode"] == mode
                          and (dimension is None or x[dimension] == axis)]
                indep = group_metrics(sample, dimension)
                for k in row:
                    if k in ("mode", dimension):
                        continue
                    delta = F(indep[k])-F(str(row[k]))
                    fine = (F("0.005") if k=="selection_change_pct" else
                            F("0.0005") if k.startswith(("mean_", "max_")) else ZERO)
                    diffs.append(dict(source=origin, mode=mode, dimension=dimension or "overall",
                        axis="" if axis is None else axis, metric=k, archived=row[k], independent=indep[k],
                        delta=delta, permitted_rounding=fine, matches=int(abs(delta)<=fine)))
    return diffs


def summarize(rows, project_checks, checks, labels, derived, summaries, z, path):
    headline = []
    for case, mode in itertools.product(("main","control"), MODES):
        ls = [x for x in labels if x["design"]==case and x["mode"]==mode]
        ds = [x for x in derived if x["design"]==case and x["mode"]==mode]
        cohort = [x for x in rows if x["design"]==case and x["mode"]==mode]
        headline.append(dict(design=case, mode=mode, project_threshold_labels=len(ls),
            true_eligible_labels=sum(x["true_eligible"] for x in ls),
            true_ineligible_labels=sum(1-x["true_eligible"] for x in ls),
            false_admit=sum(x["false_admit"] for x in ls),false_exclude=sum(x["false_exclude"] for x in ls),
            margin_certified=sum(x["strict_absolute_margin_certified"] for x in ls),
            max_error=max(x["error_kg_mwh"] for x in ls), min_error=min(x["error_kg_mwh"] for x in ls),
            portfolio_threshold_cells_with_crossing=sum(x["project_labels_changed"] for x in ds)//3,
            decisions_with_crossing=sum(x["project_labels_changed"] for x in ds),
            selection_changes=sum(x["selection_changed"] for x in ds),
            crossing_without_selection_change=sum(x["project_labels_changed"] > x["selection_changed"] for x in ds),
            decisions_with_multiple_maximizers=sum(x["number_of_optima_at_max_npv"]>1 for x in ds),
            decisions_receiving_false_admission=sum(bool(x["financed_false_admissions"]) for x in ds),
            changed_and_zero_shortfall=sum(x["change_but_zero_shortfall"] for x in ds),
            positive_shortfalls=sum(x["qualified_shortfall_musd"]>0 for x in ds),
            mean_exclusion_component_musd=sum(x["exclusion_component_musd"] for x in ds)/len(ds),
            mean_displacement_component_musd=sum(x["displacement_component_musd"] for x in ds)/len(ds),
            mean_ineligible_capex_musd=F(sum(x["ineligible_capex_musd"] for x in cohort),len(ds)),
            mean_nominal_npv_difference_musd=sum(x["selected_nominal_npv_musd"]-x["baseline_npv_musd"] for x in cohort)/len(ds),
            mean_baseline_npv_musd=sum(x["baseline_npv_musd"] for x in cohort)/len(ds)))
    source_ledger = read_csv(z, "data/code_audit.csv")
    numeric = []
    inputs = {(x["id"],m): (x["intensity_true"],intensities(x)[m]) for p in range(8)
              for x in records("main",p) for m in MODES}
    for r in source_ledger:
        true, report = inputs[(r["project_id"], r["mode"])]
        candidate = dict(intensity_true=true, intensity_reported=report, error_kg_mwh=report-true,
                         test_reference_disagreement=int(abs(report-true)>TOL))
        delta, bad = compare({k:r[k] for k in candidate},candidate)
        numeric.append(dict(project_id=r["project_id"], mode=r["mode"], differing_fields="|".join(bad),
                            **{f"delta_{k}":v for k,v in delta.items()}))
    assert len({(x["project_id"],x["mode"]) for x in numeric}) == len(numeric) == 192
    controls = json.loads(z.read("results/negative_control_results.json"))
    assert controls["negative_control_projects"] == 48 and controls["decision_conditions"] == 288
    assert controls["changes"] == sum(x["selection_changed"] for x in rows if x["design"]=="control")
    assert controls["thresholds"]==list(TAUS) and controls["budget_fractions"]==list(map(float,BUDGETS))
    audit = dict(baseline_manifest_sha256=SCIENCE_MANIFEST_SHA256, script_runtime="stdlib Python 3.11 or later",
        comparison_convention="independent minus archived; USD million for monetary fields",
        raw_absolute_tolerance=str(float(TOL)), independent_arithmetic="exact rational",
        project_rows=len(project_checks), project_rows_with_differences=sum(bool(x["differing_fields"]) for x in project_checks),
        finance_decisions_main=288, finance_decisions_control=288,
        decisions_with_differences=sum(bool(x["differing_fields"]) for x in checks),
        primary_numeric_kpi_fixtures=len(numeric), primary_numeric_kpi_differences=sum(bool(x["differing_fields"]) for x in numeric),
        summary_metric_fields_compared=len(summaries), summary_metric_differences=sum(1-x["matches"] for x in summaries),
        maximum_absolute_raw_decision_monetary_difference_musd=float(max(abs(x[k]) for x in checks if x["design"]=="main" for k in x if k.startswith("delta_") and k.endswith("musd"))),
        exact_certificate_mismatches=sum(x["selection_changed"] != x["certificate_predicts_change"] for x in derived),
        nonzero_shortfall_decomposition_residuals=sum(x["decomposition_residual_musd"]!=0 for x in derived),
        margin_violations=sum(x["strict_absolute_margin_certified"] and x["true_eligible"]!=x["reported_eligible"] for x in labels),
        paired_fault_decisions=216, correct_comparisons_per_design=72,
        nominal_financial_values="synthetic USD millions, not cash realizations")
    return headline, numeric, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("--output", type=Path, default=Path("."))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with ScientificInputs(args.baseline) as z:
        rows, projects, checks, labels, derived = evaluate_grid(z)
        summaries = compare_summaries(z, rows)
        headline, numbers, audit = summarize(rows, projects, checks, labels, derived, summaries, z, args.baseline)
    for name, data in [("independent_decisions", rows), ("decision_diff",checks), ("project_diff",projects),
                       ("numeric_kpi_diff",numbers), ("summary_diff", summaries), ("project_thresholds",labels),
                       ("decision_mechanism",derived), ("mechanism_summary",headline)]:
        write_csv(args.output/f"{name}.csv", data)
    (args.output/"audit.json").write_text(json.dumps(audit, indent=2)+"\n")
    print(json.dumps(audit, indent=2))
    if any(audit[k] for k in ("project_rows_with_differences","decisions_with_differences",
        "primary_numeric_kpi_differences","summary_metric_differences","exact_certificate_mismatches",
        "nonzero_shortfall_decomposition_residuals","margin_violations")):
        raise SystemExit("Comparison failed; inspect CSV differences.")


if __name__ == "__main__":
    main()
