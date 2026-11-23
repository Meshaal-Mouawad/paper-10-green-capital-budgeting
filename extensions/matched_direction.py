"""Reciprocal-factor sensitivity on the frozen project register. Standard library only."""
import argparse
import csv
import itertools
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from statistics import mean


def save(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.baseline / "data/synthetic_projects.csv").open() as stream:
        projects = list(csv.DictReader(stream))
    rows = []
    for pid, group in itertools.groupby(projects,key=lambda p:p["portfolio"]):
        pool=list(group)
        universe=range(len(pool))
        costs=[float(p["capex_musd"]) for p in pool]
        npvs=[float(p["npv_musd"]) for p in pool]
        # Reconstruct the design's integer intensities and exact nominal multipliers.
        # A regrouped floating product for P01_03 is 420.00000000000006.
        # At the 420 ceiling this project qualifies under the declared <= rule.
        truth=[round(float(p["intensity_true"])) for p in pool]
        levels=[(int(pid)-1+j)%5 for j in universe]
        gross=[Fraction(107,100)+Fraction(k,40) for k in levels]
        scope2=[Fraction(9,100)+Fraction(k,40) for k in levels]
        for j,p in enumerate(pool):
            assert abs(truth[j]-float(p["intensity_true"])) < 1e-9
            assert abs(float(gross[j])-float(p["gross_mwh"])/float(p["net_mwh"])) < 1e-12
            assert abs(float(scope2[j])-float(p["scope2_fraction"])) < 1e-12
        factors={
            "gross_to_net":gross,
            "total_to_scope1":[1/(1-s) for s in scope2],
            "fixed_output":[Fraction(20,17)]*len(pool),
        }
        for fraction, tau in itertools.product((.45,.60,.75),(380,400,420)):
            budget=fraction*sum(costs)
            feasible=[a for n in range(len(pool)+1) for a in itertools.combinations(universe,n)
                      if sum(costs[i] for i in a) <= budget]
            feasible.sort(key=lambda a:(-sum(npvs[i] for i in a),sum(costs[i] for i in a),a))
            def winner(scores):
                return next(a for a in feasible if all(scores[i]<=tau for i in a))
            reference=winner(truth)
            for name, scales in factors.items():
                for direction in ("down","up"):
                    scores=[v/s if direction=="down" else v*s for v,s in zip(truth,scales)]
                    chosen=winner(scores)
                    loss=sum(npvs[i] for i in reference)-sum(npvs[i] for i in chosen if truth[i]<=tau)
                    rows.append(dict(portfolio=pid,threshold=tau,budget_fraction=fraction,
                                     factor=name,direction=direction,changed=int(chosen!=reference),
                                     false_admitted_capex=sum(costs[i] for i in chosen if truth[i]>tau),
                                     shortfall=loss))
    groups=defaultdict(list)
    for r in rows:
        groups[r["factor"],r["direction"]].append(r)
    summary=[dict(factor=label,direction=direction,n=len(part),
                  changed=sum(r["changed"] for r in part),
                  mean_ineligible_capex=mean(r["false_admitted_capex"] for r in part),
                  mean_shortfall=mean(r["shortfall"] for r in part))
             for (label,direction),part in groups.items()]
    save(args.output/"matched_directions.csv",rows)
    save(args.output/"matched_directions_summary.csv",summary)


if __name__=="__main__":
    main()
