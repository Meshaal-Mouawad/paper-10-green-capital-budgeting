#!/usr/bin/env python3
"""Check area using the upper envelope of winning subsets in integer capital strips.

No policy-geometry source is imported. Also verify all 1,848 mixed archived states and
the least-capital slack equivalence for every possible pair of masks at the three budgets.
"""
from argparse import ArgumentParser
from collections import defaultdict
from fractions import Fraction as F
from itertools import product
from pathlib import Path
import csv
import json

from assignment_sensitivity import construct, load_inputs, quantize, save

MODES=("gross_denominator","scope2_omission","net_output_undercount")
FRACS=(F(".45"),F(".60"),F(".75"))


def read(path):
    with path.open() as fp:
        return list(csv.DictReader(fp))


def true_and_reports(xs):
    result=[]
    for x in xs:
        true=quantize(F(x["intensity_true"]),1)
        ratio=quantize(F(x["gross_mwh"])/F(x["net_mwh"]),1000)
        share=quantize(F(x["scope2_fraction"]),1000)
        result.append([true,true/ratio,true*(1-share),true*F(20,17)])
    return list(zip(*result))


def winning_intervals(ranked,max_score,lo,hi):
    uncovered=hi
    segs=[]
    for m in ranked:
        lower=max(lo,max_score[m]) if m else lo
        if lower < uncovered:
            segs.append((lower,uncovered,m))
            uncovered=lower
            if uncovered==lo:
                break
    assert uncovered==lo
    return segs


def measure(xs,groups,lo,hi,sl,sh):
    _,value,cap,_,_=construct(xs)
    total=cap[63]
    b0,b1=sl*total,sh*total
    # Each bundle costs an integer number of USD millions. On each open strip (c,c+1)
    # exactly the same candidate subsets are affordable as at c.
    surface=[[F(0),F(0)] for _ in MODES]
    ranked=sorted(range(64),key=lambda m:(-value[m],cap[m],m))
    thresholds=[[max((v for i,v in enumerate(scores) if m>>i&1),default=lo)
                 for m in range(64)] for scores in groups]
    for c in range(int(b0),min(total,int(b1)+1)):
        bw=min(c+1,b1)-max(c,b0)
        if bw<=0:
            continue
        affordable=[m for m in ranked if cap[m]<=c]
        winners=[winning_intervals(affordable,qs,lo,hi) for qs in thresholds]
        for mi,intervals in enumerate(winners[1:]):
            for al,ah,ref in winners[0]:
                for bl,bh,sel in intervals:
                    a,b=max(al,bl),min(ah,bh)
                    if a>=b:
                        continue
                    if ref!=sel:
                        surface[mi][0]+=(b-a)*bw
                    # Qualified portion of a fixed reported choice can change as individual
                    # reference-eligibility cutoffs are crossed. Integrate these directly.
                    cut=sorted({a,b,*[v for j,v in enumerate(groups[0]) if sel>>j&1 and a<v<b]})
                    for l,h in zip(cut,cut[1:]):
                        midpoint=(l+h)/2
                        ok=sum(1<<j for j,v in enumerate(groups[0]) if v<=midpoint)
                        gap=value[ref]-value[sel & ok]
                        assert gap>=0
                        if gap>0:
                            surface[mi][1]+=(h-l)*bw
    return [[v/((hi-lo)*(b1-b0)) for v in row] for row in surface]


def main():
    ap=ArgumentParser(description=__doc__)
    ap.add_argument("supplement",type=Path)
    ap.add_argument("lead_directory",type=Path)
    ap.add_argument("--output",type=Path,default=Path("."))
    args=ap.parse_args()
    args.output.mkdir(exist_ok=True,parents=True)
    inp,_=load_inputs(args.supplement)
    pools=defaultdict(list)
    for x in inp:
        pools[int(x["portfolio"])].append(x)
    pool_scores={p:true_and_reports(xs) for p,xs in pools.items()}
    all_scores=[x for g in pool_scores.values() for scores in g for x in scores]
    windows={"full_support":(min(all_scores),max(all_scores),F(0),F(1)),"grid_window":(F(380),F(420),F(".45"),F(".75"))}
    originals=read(args.lead_directory/"policy_areas.csv")
    lead={(r["window"],int(r["portfolio"]),r["mode"]):r for r in originals}
    assert len(lead)==len(originals)==48
    rowwise=[]; mixed_rows=[]; tests=0
    mixed=read(args.lead_directory/"mixed_decomposition.csv")
    mixed_by_key={(int(r["portfolio"]),int(r["ceiling"]),F(r["budget_fraction"]),int(r["tested_eligible_mask"])):r
                  for r in mixed}
    assert len(mixed)==len(mixed_by_key)==1848
    for pid,xs in sorted(pools.items()):
        groups=pool_scores[pid]
        scale,value,capital,_,_=construct(xs)
        rank=sorted(range(64),key=lambda m:(-value[m],capital[m],m))
        for label,clip in windows.items():
            answers=measure(xs,groups,*clip)
            for mode,(change,positive) in zip(MODES,answers):
                archive=lead[label,pid,mode]
                dc=change-F(archive["changed_exact"])
                dp=positive-F(archive["positive_exact"])
                assert dc==dp==0
                rowwise.append(dict(window=label,portfolio=pid,mode=mode,changed_exact=str(change),
                    positive_exact=str(positive),delta_changed=dc,delta_positive=dp))
        for frac in FRACS:
            b=frac*capital[-1]
            affordable=[m for m in rank if capital[m]<=b]
            refbest=[next(m for m in affordable if m&~elig==0) for elig in range(64)]
            pairs={}
            for T,R in product(range(64),repeat=2):
                chosen=refbest[R]; common=T&R; optimum=refbest[common]
                false_financed=capital[chosen & ~T]
                retained_value=value[chosen&T]
                # Compute min capital over all value-maximizing alternatives independently
                # of their tie order. Also separately reoptimize at the reduced budget.
                cstar=min(capital[m] for m in affordable if m&~common==0 and value[m]==value[optimum])
                residual=next(m for m in affordable if m&~common==0 and capital[m]<=b-false_financed)
                assert value[residual]==retained_value
                displacement=value[optimum]-retained_value
                exclusion=value[refbest[T]]-value[optimum]
                assert displacement>=0 and exclusion>=0 and (displacement==0)==(false_financed<=b-cstar)
                pairs[T,R]=(refbest[T],chosen,F(exclusion,scale),F(displacement,scale))
                tests+=1
            for t in (380,400,420):
                masks=[sum(1<<i for i,e in enumerate(g) if e<=t) for g in groups]
                Tmin,Tmax=masks[3],masks[2]
                for R in range(64):
                    if R&Tmin!=Tmin or R|Tmax!=Tmax: continue
                    leadrow=mixed_by_key[pid,t,frac,R]
                    T=masks[0]
                    ref,sel,exc,disp=pairs[T,R]
                    err=max(abs(exc-F(leadrow["exclusion"])),abs(disp-F(leadrow["displacement"])),
                            abs(exc+disp-F(leadrow["shortfall"])))
                    both=int(bool(T&~R) and bool(R&~T))
                    assert (int(leadrow["reference_eligible_mask"]), int(leadrow["reference_winner"]),
                            int(leadrow["reported_winner"]), int(leadrow["both_label_directions"]),
                            int(leadrow["both_terms_positive"])) == (T,ref,sel,both,int(exc>0 and disp>0))
                    assert err<F("1e-7")
                    mixed_rows.append(dict(portfolio=pid,ceiling=t,budget_share=frac,reported_mask=R,
                        both_label_directions=both,both_terms_positive=int(exc>0 and disp>0),max_value_delta=err))
    save(args.output/"policy_area_crosscheck.csv",rowwise)
    save(args.output/"mixed_state_crosscheck.csv.gz",mixed_rows)
    summ=[]
    for w,mode in product(windows,MODES):
        records=[r for r in rowwise if r["window"]==w and r["mode"]==mode]
        changed=100*sum(F(r["changed_exact"]) for r in records)/len(records)
        positive=100*sum(F(r["positive_exact"]) for r in records)/len(records)
        summ.append(dict(window=w,mode=mode,percent_changed=changed,percent_positive=positive))
    save(args.output/"policy_area_verified_summary.csv",summ)
    status=dict(portfolio_mode_window_area_comparisons=len(rowwise),exact_area_disagreements=0,
                exact_slack_tests=tests,slack_equivalence_disagreements=0,
                matched_mixed_financial_rows=len(mixed_rows),
                in_both_label_directions=sum(r["both_label_directions"] for r in mixed_rows),
                both_loss_terms_positive=sum(r["both_terms_positive"] for r in mixed_rows),
                max_mixed_loss_residual=float(max(r["max_value_delta"] for r in mixed_rows)))
    print(json.dumps(status,indent=2))
    (args.output/"policy_crosscheck.json").write_text(json.dumps(status,indent=2)+"\n")


if __name__=="__main__":
    main()
