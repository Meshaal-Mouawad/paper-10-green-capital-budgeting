#!/usr/bin/env python3
"""Independent exact-rational and truth-table checks of the three post hoc finance analyses.

Usage: python3 independent_extensions.py --lead-directory ../verification --output .
Requires independent_finance.py in this directory. Does not import the lead implementations.
"""
import argparse
import csv
import itertools
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

from independent_finance import (BUDGETS, MODES, TAUS, ZERO, F, classify, compare, intensities,
                                 records, solve, subset_library, write_csv)


def read(path):
    with path.open() as f:
        return list(csv.DictReader(f))


def solve_query_problem(worlds, winners, reference_world, xs):
    # Partial observations are indexed by coordinates known false and coordinates known true.
    # The independent solver scans the admissible worlds for each partial observation.
    @lru_cache(None)
    def policy(no, yes):
        possible = [w for w in worlds if w & no == 0 and w & yes == yes]
        if len({winners[w] for w in possible}) == 1:
            return 0, None
        choices = []
        for j in range(len(xs)):
            bit = 1 << j
            answers = {(w & bit)!=0 for w in possible}
            if len(answers)==2:
                depth = 1 + max(policy(no|bit, yes)[0], policy(no,yes|bit)[0])
                choices.append((depth, j))
        return min(choices)  # smallest project index among minimum worst-depth choices

    worst = policy(0,0)[0]
    no = yes = 0
    queries = []
    while True:
        _, j = policy(no,yes)
        if j is None:
            break
        bit = 1 << j
        queries.append(xs[j]["id"])
        if bit & reference_world:
            yes |= bit
        else:
            no |= bit
    # Directly enumerate every possible fixed questionnaire, unsorted input names normalized by ID.
    def identifies(mask):
        seen = {}
        for w in worlds:
            if w & mask in seen and seen[w & mask] != winners[w]:
                return False
            seen[w & mask] = winners[w]
        return True
    qr = min((m.bit_count(),m) for m in range(64) if identifies(m))[0]
    return worst, queries, qr


def decision_check(archive_rows):
    expected = {(int(x["portfolio"]),int(x["threshold"]),F(x["budget_fraction"]),x["model"]):x
                for x in archive_rows}
    assert len(expected)==len(archive_rows)==144
    comparisons = []
    for p in range(8):
        xs = records("main",p)
        all_subsets = subset_library(xs)
        for tau, frac in itertools.product(TAUS,BUDGETS):
            budget = sum(x["capex_musd"] for x in xs)*frac
            masks = {m:classify(xs,tau,m) for m in MODES}
            chain = [masks[m] for m in ("net_output_undercount","correct","gross_denominator","scope2_omission")]
            assert all(a & ~b == 0 for a,b in zip(chain,chain[1:]))
            lower,upper = chain[0],chain[-1]
            cube = [w for w in range(64) if lower & w==lower and (w|upper)==upper]
            for model, worlds in [("common",sorted(set(chain))),("project_specific",cube)]:
                winners = {w:solve(all_subsets,w,budget)["mask"] for w in worlds}
                winner_count = len(set(winners.values()))
                worst, qs, fixed = solve_query_problem(worlds,winners,masks["correct"], xs)
                lb = (winner_count-1).bit_length()
                assert worst >= lb
                # Check endpoint certificate on all reachable intervals, before or after any answers.
                # For common-mode models endpoints are attainable since every candidate is on a chain.
                n_intervals = 0
                for a,b in itertools.product(worlds, repeat=2):
                    if a & ~b:
                        continue
                    between = [w for w in worlds if a & ~w==0 and w & ~b==0]
                    assert (winners[a]==winners[b]) == (len({winners[w] for w in between})==1)
                    n_intervals += 1
                if model=="common":
                    assert worst==lb and fixed==winner_count-1
                else:
                    relevant = sum(any(w^bit in winners and winners[w^bit]!=winners[w] for w in worlds)
                                   for bit in (1<<j for j in range(6)))
                    assert relevant==fixed
                out = dict(portfolio=p+1,threshold=tau,budget_fraction=frac,model=model,
                           ambiguous_projects=(upper^lower).bit_count(), eligibility_patterns=len(worlds),
                           distinct_winners=winner_count, worst_case_checks=worst,
                           reference_path_checks=len(qs), reference_path=";".join(qs))
                archive = expected[p+1,tau,frac,model]
                delta, bad = compare(archive,out, ("reference_path","model"), tolerance=ZERO)
                comparisons.append(dict(**out, differing_fields="|".join(bad),
                    delta_worst_case_checks=delta["worst_case_checks"],
                    delta_reference_path_checks=delta["reference_path_checks"],
                    delta_reference_path_ids=delta["reference_path"],
                    best_prespecified_checks=fixed, adaptive_saving_vs_best_prespecified=fixed-worst,
                    fewer_prespecified_than_ambiguous=(upper^lower).bit_count()-fixed,
                    information_lower_bound=lb, verified_endpoint_intervals=n_intervals))
    return comparisons


def direction_check(detail,summary):
    keys = ("portfolio","threshold","budget_fraction","factor","direction")
    expected = {(int(x["portfolio"]),int(x["threshold"]),F(x["budget_fraction"]),x["factor"],x["direction"]):x
                for x in detail}
    assert len(expected)==len(detail)==432
    rows = []
    for p in range(8):
        xs = records("main",p)
        options = subset_library(xs)
        look = {x["mask"]:x for x in options}
        for tau, frac in itertools.product(TAUS,BUDGETS):
            budget = sum(x["capex_musd"] for x in xs)*frac
            truth = classify(xs,tau,"correct")
            ref = solve(options,truth,budget)
            for factor in ("gross_to_net","total_to_scope1","fixed_output"):
                for direction in ("down","up"):
                    eligible = 0
                    for j,x in enumerate(xs):
                        f = {"gross_to_net":F(x["gross_mwh"],x["net_mwh"]),
                             "total_to_scope1":1/(1-x["scope2_fraction"]),
                             "fixed_output": 1/F(".85")}[factor]
                        e = x["intensity_true"] * (f if direction=="up" else 1/f)
                        if e <= tau:
                            eligible |= 1<<j
                    sel = solve(options,eligible,budget)
                    shortfall = ref["v"]-look[sel["mask"] & truth]["v"]
                    out=dict(portfolio=p+1, threshold=tau,budget_fraction=frac,factor=factor,
                        direction=direction, changed=int(sel["mask"]!=ref["mask"]),
                        false_admitted_capex=look[sel["mask"] & ~truth]["k"],shortfall=shortfall)
                    original=expected[tuple(out[k] for k in keys)]
                    d,bad = compare(original,out, ("factor","direction"))
                    rows.append(dict(**out,differing_fields="|".join(bad),delta_shortfall=d["shortfall"],
                                     delta_false_admitted_capex=d["false_admitted_capex"]))
    comparisons=[]
    assert len({(x["factor"],x["direction"]) for x in summary})==len(summary)==6
    for orig in summary:
        sample = [x for x in rows if all(x[k]==orig[k] for k in ("factor","direction"))]
        n=len(sample)
        out = dict(factor=orig["factor"],direction=orig["direction"],n=n,changed=sum(x["changed"] for x in sample),
                   mean_ineligible_capex=F(sum(x["false_admitted_capex"] for x in sample),n),
                   mean_shortfall=sum(x["shortfall"] for x in sample)/n)
        delta,bad=compare(orig,out,("factor","direction"))
        comparisons.append(dict(**out,differing_fields="|".join(bad),
            delta_mean_shortfall=delta["mean_shortfall"],delta_mean_ineligible_capex=delta["mean_ineligible_capex"]))
    return rows,comparisons


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lead-directory",type=Path,default=Path("../verification"))
    parser.add_argument("--output",type=Path,default=Path("."))
    args=parser.parse_args()
    args.output.mkdir(exist_ok=True,parents=True)
    queries=decision_check(read(args.lead_directory/"decision_checks.csv"))
    rows,comparisons=direction_check(read(args.lead_directory/"matched_directions.csv"),
                                     read(args.lead_directory/"matched_directions_summary.csv"))
    result = dict(query_comparisons=len(queries),query_diff_count=sum(bool(x["differing_fields"]) for x in queries),
                  matched_direction_comparisons=len(rows),matched_direction_diff_count=sum(bool(x["differing_fields"]) for x in rows),
                  matched_summary_comparisons=len(comparisons),matched_summary_diff_count=sum(bool(x["differing_fields"]) for x in comparisons))
    for model in ("common","project_specific"):
        qs=[r for r in queries if r["model"]==model]
        result[model] = {k:{"sum":sum(x[k] for x in qs),"distribution":dict(sorted(Counter(x[k] for x in qs).items()))}
                         for k in ("ambiguous_projects","distinct_winners","worst_case_checks","reference_path_checks",
                                   "best_prespecified_checks","adaptive_saving_vs_best_prespecified","fewer_prespecified_than_ambiguous")}
        result[model]["verified_endpoint_intervals"]=sum(r["verified_endpoint_intervals"] for r in qs)
    write_csv(args.output/"adaptive_query_diff.csv",queries)
    write_csv(args.output/"matched_direction_diff.csv",rows)
    write_csv(args.output/"matched_direction_aggregate_diff.csv",comparisons)
    (args.output/"posthoc_audit.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
    if any(result[k] for k in ("query_diff_count","matched_direction_diff_count","matched_summary_diff_count")):
        raise SystemExit("Lead comparison failed")


if __name__=="__main__":
    main()
