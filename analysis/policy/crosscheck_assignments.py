"""Check every emitted reassignment using archived NPVs and a capacity dynamic program.

Usage: python crosscheck_assignments.py BASELINE_DIRECTORY ASSIGNMENT_OUTPUT_DIRECTORY
Reads records; does not import either scientific implementation.
"""
import argparse
import csv
from fractions import Fraction as F
from functools import lru_cache
import gzip
import itertools
import json
from pathlib import Path


def load(path):
    with path.open(newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("baseline",type=Path)
    p.add_argument("assignment",type=Path)
    p.add_argument("--receipt",type=Path)
    a=p.parse_args()
    projects=load(a.baseline/"data/synthetic_projects.csv")
    checked=0
    max_residual=0.
    minmax={}
    by_budget={}
    seen=set()
    gross_factor=lambda item: F(str(float(item["gross_mwh"])/float(item["net_mwh"]))).limit_denominator(1000)
    scope_factor=lambda item: 1/(1-F(item["scope2_fraction"]).limit_denominator(1000))

    @lru_cache(None)
    def pool(pid):
        items=sorted((i for i in projects if int(i["portfolio"])==pid),key=lambda i:i["id"])
        ints=[int(round(float(i["intensity_true"]))) for i in items]
        cost=[int(float(i["capex_musd"])) for i in items]
        value=[float(i["npv_musd"]) for i in items]
        gains=[sum(v for j,v in enumerate(value) if mask & (1<<j)) for mask in range(64)]
        costs=[sum(c for j,c in enumerate(cost) if mask & (1<<j)) for mask in range(64)]
        factors={"gross_to_net":[gross_factor(i) for i in items],
                 "total_to_scope1":[scope_factor(i) for i in items],"fixed_output":[F(20,17)]*6}
        env={}
        for name,factors_by_slot in factors.items():
            for ceiling in (380,400,420):
                for direction in ("down","up","ref"):
                    adjusted=[v*f if direction=="up" else F(v)/f if direction=="down" else F(v)
                              for v,f in zip(ints,factors_by_slot)]
                    env[name,ceiling,direction]=[j for j,v in enumerate(adjusted) if v<=ceiling]
        opt={}
        for mask in range(64):
            dp=[0]*(sum(cost)+1)
            for j,c in enumerate(cost):
                if mask & (1<<j):
                    for b in range(len(dp)-1,c-1,-1):
                        other=dp[b-c] | (1<<j)
                        if gains[other] > gains[dp[b]]+1e-10:
                            dp[b]=other
            for f in (F('.45'),F('.60'),F('.75')):
                opt[mask,float(f)]=dp[int(f*sum(cost))]
        return gains,costs,opt,env

    def check_number(answer,field):
        nonlocal max_residual
        error=abs(answer-float(field))
        max_residual=max(error,max_residual)
        assert error<1e-7,(error,answer,field)

    with gzip.open(a.assignment/"condition_results.csv.gz","rt",newline="") as f:
        for row in csv.DictReader(f):
            pid=int(row["portfolio"])
            ceiling=int(row["ceiling"])
            budget=float(row["budget_share"])
            factor=row["factor"]
            perm=tuple(int(j)-1 for j in row["permutation"])
            key=(pid,perm,ceiling,budget,factor)
            assert key not in seen
            seen.add(key)
            gains,costs,opt,env=pool(pid)
            selections=[]
            eligibilities=[]
            for direction in ("ref","down","up"):
                mask=sum(1<<perm[i] for i in env[factor,ceiling,direction])
                eligibilities.append(mask)
                chosen=opt[mask,budget]
                selections.append(chosen)
                env_slots="".join(str(i+1) for i in range(6) if chosen & (1<<perm[i]))
                assert env_slots==(row[direction+"_environment_slots"] or "").replace("-",""), (row,env_slots)
            ref,down,up=selections
            truth=eligibilities[0]
            dg=gains[ref]-gains[down & truth]
            ug=gains[ref]-gains[up & truth]
            for expected,field in ((gains[ref],"ref_npv"),(dg,"down_gap"),(ug,"up_gap"),
                                   (ug-dg,"up_minus_down"),(costs[down & ~truth],"down_invalid_capital")):
                check_number(expected,row[field])
            assert (down!=ref)==int(row["down_changed"]) and (up!=ref)==int(row["up_changed"])
            k=(pid,factor,perm)
            minmax[k]=minmax.get(k,0.)+(ug-dg)/9
            j=(pid,factor,perm,budget)
            by_budget[j]=by_budget.get(j,0.)+(ug-dg)/3
            checked+=1
    assert checked==8*720*3*3*3
    bounds=load(a.assignment/"joint_assignment_sharp_bounds.csv")
    for row in bounds:
        extremes=[]
        for pid in range(1,9):
            local=[minmax[pid,row["factor"],perm] for perm in itertools.permutations(range(6))]
            extremes.append((min if row["extreme"]=="min" else max)(local))
        check_number(sum(extremes)/8,row["mean_up_minus_down"])
    budget_rows = [r for r in load(a.assignment/"policy_settings_sharp_bounds.csv") if r["ceiling"]=="all" and r["budget_share"]!="all"]
    for row in budget_rows:
        for extreme, select in (("min",min),("max",max)):
            portfolio_extremes=[]
            for pid in range(1,9):
                portfolio_extremes.append(select(by_budget[pid,row["factor"],perm,float(row["budget_share"])] for perm in itertools.permutations(range(6))))
            check_number(sum(portfolio_extremes)/8,row[extreme+"_mean_up_minus_down"])
    receipt=dict(verified_budget_specific_endpoints=2*len(budget_rows),verified_local_contrasts=checked,verified_joint_endpoints=len(bounds),
                 max_abs_difference_in_rounded_USD_millions=max_residual,
                 method="Dynamic programming with frozen NPVs; portfolio financier slots restored from each environmental permutation.")
    if a.receipt:
        a.receipt.write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt))


if __name__=="__main__":
    main()
