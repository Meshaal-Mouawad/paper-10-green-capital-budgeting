"""Map continuous screening ceilings and budget fractions on the frozen project register.

Usage: python policy_surface.py PATH/TO/Supplement_S1/baseline OUTPUT
The optimizer and policy-cell enumeration use exact fractions. Area is a measure
of the specified policy rectangle, without a probability model for financiers.
"""
import argparse
import csv
from collections import defaultdict
from fractions import Fraction as F
from functools import lru_cache
from itertools import pairwise
from pathlib import Path


MODES = ("gross_denominator", "scope2_omission", "net_output_undercount")


def write(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def read(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def decimal_design_value(value, decimals):
    # All relevant generator rates/inputs lie on stated decimal grids.
    result = F(round(float(value) * 10**decimals), 10**decimals)
    assert abs(float(result) - float(value)) < 1e-8
    return result


def prepare(rows):
    costs, values, intensities = [], [], []
    for row in rows:
        cost = int(decimal_design_value(row["capex_musd"], 0))
        cash = decimal_design_value(row["annual_cash_flow_musd"], 2)
        rate = decimal_design_value(row["discount_rate"], 2)
        intensity = decimal_design_value(row["intensity_true"], 0)
        share = decimal_design_value(row["scope2_fraction"], 3)
        gross_net = decimal_design_value(float(row["gross_mwh"]) / float(row["net_mwh"]), 3)
        value = sum(cash / (1 + rate)**year for year in range(1, 6)) - cost
        assert abs(float(value) - float(row["npv_musd"])) < 1e-8
        costs.append(cost)
        values.append(value)
        intensities.append(dict(correct=intensity, gross_denominator=intensity/gross_net,
                                scope2_omission=intensity*(1-share),
                                net_output_undercount=intensity/F(85,100)))
    return costs, values, intensities


def solver(costs, values):
    masks = range(1 << len(costs))
    capital = [sum(c for i,c in enumerate(costs) if m & (1 << i)) for m in masks]
    npv = [sum((v for i,v in enumerate(values) if m & (1 << i)), F(0)) for m in masks]
    ranked = sorted(masks,key=lambda m:(-npv[m],capital[m],m))

    @lru_cache(None)
    def winner(eligible, budget):
        return next(m for m in ranked if (m & eligible) == m and capital[m] <= budget)

    # Independent 0/1 dynamic program validates the optimum at every subset-cost
    # breakpoint for every candidate eligibility set, including all boundaries.
    for eligible in masks:
        dp = [0] * (sum(costs)+1)
        for i,(c,v) in enumerate(zip(costs,values)):
            if eligible & (1 << i):
                for b in range(sum(costs),c-1,-1):
                    alternative = dp[b-c] | (1 << i)
                    old = dp[b]
                    if (npv[alternative],-capital[alternative],-alternative) > (npv[old],-capital[old],-old):
                        dp[b] = alternative
        for b in set(capital):
            assert winner(eligible,b) == dp[b]
    return capital,npv,winner


def eligible(intensities, mode, tau):
    return sum(1 << i for i,s in enumerate(intensities) if s[mode] <= tau)


def case(capital, npv, winner, truth, reported, budget):
    reference = winner(truth,budget)
    funded = winner(reported,budget)
    common = reported & truth
    invalid = funded & ~truth
    valid = funded & truth
    best_common = winner(common,budget)
    residual = winner(common,budget-capital[invalid])
    excluded = npv[reference]-npv[best_common]
    displaced = npv[best_common]-npv[residual]
    unspent = budget-capital[best_common]
    assert npv[valid] == npv[residual]
    assert excluded + displaced == npv[reference]-npv[valid]
    assert (displaced == 0) == (capital[invalid] <= unspent)
    return reference, funded, excluded, displaced


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    grouped=defaultdict(list)
    for r in read(args.baseline/"data/synthetic_projects.csv"):
        grouped[int(r["portfolio"])].append(r)
    registers={p:prepare(sorted(rows,key=lambda r:r["id"])) for p,rows in grouped.items()}
    scores=[x for _,_,ints in registers.values() for item in ints for x in item.values()]
    tmin,tmax=min(scores),max(scores)
    windows={"full_support":(tmin,tmax,F(0),F(1)), "grid_window":(F(380),F(420),F(45,100),F(75,100))}
    summary,cells,mixed=[],[],[]
    ref_data=read(args.baseline/"data/scenario_decisions.csv")
    for pid,(costs,values,ints) in registers.items():
        capital,npv,winner=solver(costs,values)
        total=sum(costs)
        names=[r["id"] for r in sorted(grouped[pid],key=lambda r:r["id"])]
        traces=[r for r in ref_data if int(r["portfolio"])==pid]
        for r in traces:
            tau = F(r["threshold_kg_mwh"])
            budget = total*F(r["budget_fraction"])
            T,R=eligible(ints,"correct",tau),eligible(ints,r["mode"],tau)
            ref,chosen,x,d=case(capital,npv,winner,T,R,budget)
            assert ";".join(n for i,n in enumerate(names) if chosen & (1<<i)) == r["selected"]
            assert abs(float(x+d)-float(r["valid_npv_regret_musd"])) < 1e-8
        for tau in (380,400,420):
            masks=[eligible(ints,m,tau) for m in ("correct",*MODES)]
            definite = possible = masks[0]
            for m in masks: definite &= m; possible |= m
            for frac in (F(".45"),F(".60"),F(".75")):
                for reported in range(1<<len(costs)):
                    if (reported & definite) != definite or (reported & possible) != reported:
                        continue
                    ref,funded,x,d=case(capital,npv,winner,masks[0],reported,frac*total)
                    mixed.append(dict(portfolio=pid,ceiling=tau,budget_fraction=str(frac),
                                      reference_eligible_mask=masks[0],tested_eligible_mask=reported,
                                      both_label_directions=int(bool(reported & ~masks[0]) and bool(masks[0] & ~reported)),
                                      reference_winner=ref,reported_winner=funded,
                                      exclusion=float(x),displacement=float(d),shortfall=float(x+d),
                                      both_terms_positive=int(x>0 and d>0)))
        for label,(lo,hi,bl,bh) in windows.items():
            bs=sorted({bl*total,bh*total,*[F(c) for c in capital if bl*total<c<bh*total]})
            for mode in MODES:
                ts=sorted({lo,hi,*[item[m] for item in ints for m in ("correct",mode) if lo<item[m]<hi]})
                covered=changed=positive=exposure=F(0)
                for tl,th in pairwise(ts):
                    T,R=eligible(ints,"correct",tl),eligible(ints,mode,tl)
                    for b0,b1 in pairwise(bs):
                        ref,chosen,x,d=case(capital,npv,winner,T,R,b0)
                        area=(th-tl)*(b1-b0)/((hi-lo)*(bh-bl)*total)
                        covered+=area
                        changed+=area*(ref!=chosen)
                        positive+=area*(x+d>0)
                        exposure+=area*(capital[chosen & ~T]>0)
                        if label=="full_support":
                            cells.append(dict(portfolio=pid,mode=mode,tau_left=str(tl),tau_right=str(th),
                                              budget_left_musd=str(b0),budget_right_musd=str(b1),total_capex_musd=total,
                                              reference_mask=ref,selected_mask=chosen,changed=int(chosen!=ref),
                                              qualified_shortfall_positive=int(x+d>0),ineligible_capex=capital[chosen & ~T]))
                assert covered==1
                summary.append(dict(window=label,portfolio=pid,mode=mode,threshold_min=str(lo),threshold_max=str(hi),
                                    budget_fraction_low=str(bl),budget_fraction_high=str(bh),
                                    changed_area=float(changed),positive_shortfall_area=float(positive),
                                    ineligible_capex_area=float(exposure),changed_exact=str(changed),positive_exact=str(positive)))
    write(args.output/"policy_cells.csv",cells)
    write(args.output/"policy_areas.csv",summary)
    write(args.output/"mixed_decomposition.csv",mixed)
    combined=[]
    for window in windows:
        for mode in MODES:
            part=[r for r in summary if r["window"]==window and r["mode"]==mode]
            combined.append(dict(window=window,mode=mode,portfolios=len(part),threshold_min=float(F(part[0]["threshold_min"])),
                                 threshold_max=float(F(part[0]["threshold_max"])),
                                 mean_changed_area_pct=float(100*sum(F(r["changed_exact"]) for r in part)/len(part)),
                                 mean_positive_area_pct=float(100*sum(F(r["positive_exact"]) for r in part)/len(part))))
    write(args.output/"policy_summary.csv",combined)
    print("Mixed patterns (including one-sided)",len(mixed),"two-way",sum(r["both_label_directions"] for r in mixed),
          "both terms positive",sum(r["both_terms_positive"] for r in mixed))
    print("Full-support policy cells",len(cells))


if __name__=="__main__":
    main()
