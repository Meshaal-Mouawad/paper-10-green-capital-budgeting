#!/usr/bin/env python3
"""Descriptive checks for the finite design and reference outcomes. Uses the exact finance model."""
import argparse
from fractions import Fraction as F
from pathlib import Path
from statistics import correlation

from independent_finance import BUDGETS, MODES, TAUS, ZERO, classify, intensities, records, solve, subset_library, write_csv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("."))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    design = []
    relative = []
    for case in ("main","control"):
        projects = [x for p in range(8) for x in records(case,p)]
        for feature in ("net_mwh","gross_mwh","scope2_fraction","capex_musd","annual_cash_flow_musd",
                        "discount_rate","npv_musd","intensity_true"):
            vals = [x[feature] for x in projects]
            design.append(dict(design=case,metric=feature,n=len(vals),distinct=len(set(vals)),
                minimum=min(vals),maximum=max(vals),mean=sum(vals,F(0))/len(vals),negative=sum(x<0 for x in vals)))
        strictly_ordered = 0
        paired = {m:[] for m in MODES}
        slack = {m:[] for m in MODES}
        for p in range(8):
            xs = records(case,p)
            if all(a["capex_musd"] < b["capex_musd"] and a["intensity_true"] < b["intensity_true"]
                   for a,b in zip(xs,xs[1:])):
                strictly_ordered += 1
            opts = subset_library(xs)
            by_mask = {a["mask"]:a for a in opts}
            for tau in TAUS:
                truth = classify(xs,tau,"correct")
                for x in xs:
                    scores = intensities(x)
                    for m in MODES:
                        slack[m].append(abs(scores["correct"]-tau)-abs(scores[m]-scores["correct"]))
                for f in BUDGETS:
                    b=f*sum(x["capex_musd"] for x in xs)
                    reference=solve(opts,truth,b)
                    for m in MODES:
                        sel=solve(opts,classify(xs,tau,m),b)
                        loss=reference["v"]-by_mask[sel["mask"] & truth]["v"]
                        paired[m].append((reference["v"],loss))
        for m in MODES:
            rs=paired[m]
            nz=[(v,g) for v,g in rs if v>0]
            relative.append(dict(design=case,mode=m,paired_decisions=len(rs),positive_reference_values=len(nz),
                zero_reference_values=len(rs)-len(nz),mean_reference_npv_musd=sum(v for v,g in rs)/len(rs),
                ratio_of_aggregate_gap_to_aggregate_reference=sum(g for v,g in rs)/sum(v for v,g in rs),
                mean_gap_fraction_among_positive_reference=sum(g/v for v,g in nz)/len(nz),
                min_strict_margin_slack_kg_mwh=min(slack[m]),
                capex_and_intensity_strictly_increasing_portfolios=strictly_ordered,
                pooled_capex_intensity_pearson=correlation([float(x["capex_musd"]) for x in projects],
                                                         [float(x["intensity_true"]) for x in projects])))
    write_csv(args.output/"project_design_summary.csv",design)
    write_csv(args.output/"relative_and_design_checks.csv",relative)


if __name__ == "__main__":
    main()
