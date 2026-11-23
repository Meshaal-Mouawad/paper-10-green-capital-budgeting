#!/usr/bin/env python3
"""Exact reassignment of the six existing financial bundles within each archived portfolio.

Run with Python 3.11+: python3 assignment_sensitivity.py Supplement_S1.zip --output results
No study code is imported. All rankings, classifications, signs and extrema use integers
or fractions. Each six-character permutation lists financial source slots (1..6) in
environmental slot order (1..6). Outputs in USD millions are rounded only when written.
"""
from argparse import ArgumentParser
from collections import defaultdict
from contextlib import contextmanager
import csv
from fractions import Fraction as F
import gzip
import hashlib
import io
from itertools import permutations, product
import json
from math import lcm
from pathlib import Path
from zipfile import ZipFile

FACTORS = ("gross_to_net", "total_to_scope1", "fixed_output")
CEILINGS = (380, 400, 420)
BUDGETS = (F("0.45"), F("0.60"), F("0.75"))
PERMS = tuple(permutations(range(6)))
ZERO = F(0)
IDENTITY = "123456"


def fmt(v):
    if isinstance(v, F):
        return str(v.numerator) if v.denominator == 1 else f"{float(v):.12g}"
    return v


@contextmanager
def write_table(path, fields):
    # Gzip clock and filename are suppressed to keep compressed outputs byte reproducible.
    if path.suffix == ".gz":
        with path.open("wb") as raw, gzip.GzipFile(filename="",mode="wb",fileobj=raw,mtime=0) as gz:
            with io.TextIOWrapper(gz,encoding="utf8",newline="") as out:
                w=csv.DictWriter(out,fieldnames=fields,lineterminator="\n")
                w.writeheader()
                yield w
    else:
        with path.open("w",encoding="utf8",newline="") as out:
            w=csv.DictWriter(out,fieldnames=fields,lineterminator="\n")
            w.writeheader()
            yield w


def emit(w, row):
    w.writerow({k:fmt(v) for k,v in row.items()})


def save(path, rows):
    with write_table(path, list(rows[0])) as w:
        for row in rows:
            emit(w,row)


def quantize(x, units):
    # Source design uses integral capital, centi-million cash, percentage-point rates
    # and per-mille gross/Scope 2 fractions. Reject departures beyond binary roundoff.
    ans=F(round(x*units), units)
    if abs(ans-x)>F("0.00000001"):
        raise ValueError(f"Input {x} exceeds documented precision tolerance")
    return ans


def load_inputs(archive):
    if archive.is_dir():
        with (archive/"baseline"/"data"/"synthetic_projects.csv").open() as f:
            inp=list(csv.DictReader(f))
        with (archive/"outputs"/"extensions"/"matched_directions.csv").open() as f:
            match=list(csv.DictReader(f))
    else:
        with ZipFile(archive) as z:
            def table(suffix):
                names=[n for n in z.namelist() if n.endswith(suffix)]
                assert len(names)==1,(suffix,names)
                with z.open(names[0]) as f:
                    return list(csv.DictReader(io.TextIOWrapper(f)))
            inp=table("baseline/data/synthetic_projects.csv")
            match=table("outputs/extensions/matched_directions.csv")
    assert len(inp)==48 and len(match)==432
    return inp,match


def construct(pool):
    costs=[]; values=[]; scores=[]
    for x in pool:
        cap=quantize(F(x["capex_musd"]),1)
        cash=quantize(F(x["annual_cash_flow_musd"]),100)
        rate=quantize(F(x["discount_rate"]),100)
        npv=sum((cash/(1+rate)**year for year in range(1,6)),ZERO)-cap
        assert abs(npv-F(x["npv_musd"])) < F("0.00000001")
        e=quantize(F(x["intensity_true"]),1)
        gross_ratio=quantize(F(x["gross_mwh"])/F(x["net_mwh"]),1000)
        s=quantize(F(x["scope2_fraction"]),1000)
        scales=(gross_ratio,1/(1-s),F(20,17))
        scores.append((e,tuple((e/q,e*q) for q in scales)))
        values.append(npv)
        costs.append(int(cap))
    scale=lcm(*(v.denominator for v in values))
    units=[int(v*scale) for v in values]
    mask_cost=[sum(c for j,c in enumerate(costs) if m>>j&1) for m in range(64)]
    mask_value=[sum(v for j,v in enumerate(units) if m>>j&1) for m in range(64)]
    # Feasible subsets of donor identities are independent of the environmental mapping.
    winners={}
    for bi,b in enumerate(BUDGETS):
        affordable=[m for m in range(64) if mask_cost[m]<=b*sum(costs)]
        for elig in range(64):
            feasible=[m for m in affordable if m&~elig==0]
            vmax=max(mask_value[m] for m in feasible)
            best=[m for m in feasible if mask_value[m]==vmax]
            assert len(best)==1, "Order-dependent tie would require environmental-ID tie handling"
            winners[bi,elig]=best[0]
    profiles={}
    for t in CEILINGS:
        tru=sum(1<<j for j,x in enumerate(scores) if x[0]<=t)
        profiles[t]=[(tru,*(sum(1<<j for j,x in enumerate(scores) if x[1][k][d]<=t)
                              for d in (0,1))) for k in range(3)]
    return scale,mask_value,mask_cost,winners,profiles


def accum():
    return dict(n=0,up_gt=0,equal=0,up_lt=0,down_change=0,up_change=0,
                down_change_zero=0,up_change_zero=0,down_gap=0,up_gap=0,down_cap=0)


def collect(target,down_gap,up_gap,down_changed,up_changed,cap):
    target["n"]+=1
    target["up_gt"]+=up_gap>down_gap
    target["equal"]+=up_gap==down_gap
    target["up_lt"]+=up_gap<down_gap
    target["down_change"]+=down_changed
    target["up_change"]+=up_changed
    target["down_change_zero"]+=down_changed and down_gap==0
    target["up_change_zero"]+=up_changed and up_gap==0
    target["down_gap"]+=down_gap
    target["up_gap"]+=up_gap
    target["down_cap"]+=cap


def summary(a,scale):
    n=a["n"]
    return dict(n=n,up_greater=a["up_gt"],tie=a["equal"],down_greater=a["up_lt"],
                down_changed=a["down_change"],up_changed=a["up_change"],
                down_changed_zero_shortfall=a["down_change_zero"],up_changed_zero_shortfall=a["up_change_zero"],
                mean_down_invalid_capital=F(a["down_cap"],n),mean_down_shortfall=F(a["down_gap"],scale*n),
                mean_up_shortfall=F(a["up_gap"],scale*n),
                mean_up_minus_down=F(a["up_gap"]-a["down_gap"],scale*n))


def run(archive,out):
    inp,match=load_inputs(archive)
    reference={(int(x["portfolio"]),int(x["threshold"]),F(x["budget_fraction"]),x["factor"],x["direction"]):x
               for x in match}
    assert len(reference)==432
    pools=defaultdict(list)
    for x in inp:
        pools[int(x["portfolio"])].append(x)
    assert sorted(pools)==list(range(1,9))
    by_portfolio=[]; by_factor=[]; by_factor_perm=defaultdict(list)
    witness={}; identity_diff=[]; permutation_rows=[]; context=[]
    policy_bounds={}
    weight_lines=defaultdict(list)
    indices=("portfolio","permutation","ceiling","budget_share","factor")
    fields=indices+("ref_environment_slots","down_environment_slots","up_environment_slots",
          "ref_npv","down_gap","up_gap","up_minus_down","down_invalid_capital","down_changed","up_changed")
    with write_table(out/"condition_results.csv.gz",fields) as detailed:
        for pid,raw in sorted(pools.items()):
            raw.sort(key=lambda x:x["id"])
            assert [x["id"] for x in raw]==[f"P{pid:02}_{j:02}" for j in range(1,7)]
            scale,value,cost,winner,profiles=construct(raw)
            groups={f:accum() for f in FACTORS}
            local_context=defaultdict(accum)
            for perm in PERMS:
                code="".join(str(i+1) for i in perm)
                donor_masks=[sum(1<<d for i,d in enumerate(perm) if m & 1<<i) for m in range(64)]
                env_slots={donor_masks[m]:"".join(str(i+1) for i in range(6) if m>>i&1) or "-" for m in range(64)}
                pg={f:accum() for f in FACTORS}
                policy_sums=defaultdict(int)
                for t,bi in product(CEILINGS,range(3)):
                    for k,f in enumerate(FACTORS):
                        truth,down,up=map(donor_masks.__getitem__,profiles[t][k])
                        ref=winner[bi,truth]; lower=winner[bi,down]; higher=winner[bi,up]
                        d=value[ref]-value[lower&truth]; u=value[ref]-value[higher&truth]
                        cap=cost[lower&~truth]
                        assert d>=0 and u>=0 and higher&~truth==0 and up&~truth==0 and truth&~down==0
                        dc=int(lower!=ref); uc=int(higher!=ref)
                        for settings in ((str(t),str(BUDGETS[bi])),(str(t),"all"),("all",str(BUDGETS[bi]))):
                            policy_sums[(f,*settings)]+=u-d
                        for bucket in (pg[f],groups[f],local_context[t,bi,f]):
                            collect(bucket,d,u,dc,uc,cap)
                        row=dict(portfolio=pid,permutation=code,ceiling=t,budget_share=BUDGETS[bi],factor=f,
                            ref_environment_slots=env_slots[ref],down_environment_slots=env_slots[lower],
                            up_environment_slots=env_slots[higher],ref_npv=F(value[ref],scale),down_gap=F(d,scale),
                            up_gap=F(u,scale),up_minus_down=F(u-d,scale),down_invalid_capital=cap,
                            down_changed=dc,up_changed=uc)
                        emit(detailed,row)
                        for side in ("min","max"):
                            old=witness.get((f,side))
                            if old is None or ((row["up_minus_down"]<old["up_minus_down"]) if side=="min"
                                    else (row["up_minus_down"]>old["up_minus_down"])):
                                witness[f,side]=row
                        if code==IDENTITY:
                            for direction,chosen,loss,invalid in (("down",dc,d,cap),("up",uc,u,0)):
                                base=reference[pid,t,BUDGETS[bi],f,direction]
                                err=F(loss,scale)-F(base["shortfall"])
                                assert int(base["changed"])==chosen and F(base["false_admitted_capex"])==invalid
                                assert abs(err)<F("0.0000001")
                                identity_diff.append(dict(portfolio=pid,ceiling=t,budget_share=BUDGETS[bi],
                                    factor=f,direction=direction,delta_shortfall=err,delta_changed=0,delta_invalid_capital=0))
                for (f,st,sb),val in policy_sums.items():
                    n=3 if "all" in (st,sb) else 1
                    exact=F(val,scale*n)
                    for side in ("min","max"):
                        key=(f,st,sb,side,pid)
                        previous=policy_bounds.get(key)
                        if previous is None or (exact<previous[0] if side=="min" else exact>previous[0]):
                            policy_bounds[key]=(exact,code)
                for f in FACTORS:
                    tight=F(policy_sums[f,"all",str(BUDGETS[0])],3*scale)
                    loose=F(sum(policy_sums[f,"all",str(b)] for b in BUDGETS[1:]),6*scale)
                    weight_lines[f,pid].append((loose,tight,code))
                    summ=summary(pg[f],scale)
                    r=dict(portfolio=pid,permutation=code,factor=f,**summ)
                    permutation_rows.append(r)
                    by_factor_perm[f,code].append(r)
            for f in FACTORS:
                by_portfolio.append(dict(portfolio=pid,factor=f,**summary(groups[f],scale)))
            for (t,bi,f),a in sorted(local_context.items()):
                context.append(dict(portfolio=pid,ceiling=t,budget_share=BUDGETS[bi],factor=f,**summary(a,scale)))
    settings_bounds=[]
    for f,st,sb in sorted({(k[0],k[1],k[2]) for k in policy_bounds}):
        result=dict(factor=f,ceiling=st,budget_share=(fmt(F(sb)) if sb!="all" else sb))
        for side in ("min","max"):
            vals=[policy_bounds[f,st,sb,side,p] for p in range(1,9)]
            result[side+"_mean_up_minus_down"]=sum(v for v,code in vals)/8
            result[side+"_permutation_witness"]="|".join(code for v,code in vals)
        settings_bounds.append(result)
    save(out/"policy_settings_sharp_bounds.csv",settings_bounds)
    # For a given weight on the tight budget the remaining mass is divided equally
    # between the two other budgets. A minimizing choice is independent for each pool.
    # Start at w=1. The zero of the current attaining line is an upper bound on the
    # first crossing. If the lower envelope is still negative, its next attaining
    # line has a strictly earlier zero. The finitely many lines make this terminate.
    weights=[]
    for f in FACTORS:
        at_zero=sum(min(x[0] for x in weight_lines[f,pid]) for pid in range(1,9))/8
        at_one=sum(min(x[1] for x in weight_lines[f,pid]) for pid in range(1,9))/8
        assert at_zero>0 and at_one<0
        w=F(1); n_iter=0
        while True:
            n_iter+=1
            def weighted(row):
                loose,tight,_=row
                return (1-w)*loose+w*tight
            winners=[min(weight_lines[f,pid],key=weighted) for pid in range(1,9)]
            loose=sum(x[0] for x in winners)/8
            tight=sum(x[1] for x in winners)/8
            lower=loose*(1-w)+tight*w
            if lower==0:
                break
            assert lower<0 and loose>0
            new_w=loose/(loose-tight)
            assert 0<new_w<w
            w=new_w
        weights.append(dict(factor=f,critical_weight_on_45pct=w,
            exact_numerator=w.numerator,exact_denominator=w.denominator,
            minimum_at_zero_weight=at_zero,minimum_at_full_weight=at_one,
            witness_difference_with_only_45pct=tight,witness_difference_with_60_and_75pct=loose,
            witness_permutations_by_portfolio="|".join(x[2] for x in winners),
            exact_lower_envelope_at_crossing=0,iterations=n_iter))
    save(out/"budget_weight_tipping.csv",weights)
    shared_witnesses=[]
    for target in FACTORS:
        attaining=[min(weight_lines[target,p],key=lambda x:x[1])[2] for p in range(1,9)]
        for tested in FACTORS:
            vals=[next(x[1] for x in weight_lines[tested,p] if x[2]==code)
                  for p,code in enumerate(attaining,1)]
            shared_witnesses.append(dict(target_minimum=target,tested_factor=tested,
                    witness_permutations_by_portfolio="|".join(attaining),
                    mean_up_minus_down_at_45pct=sum(vals)/8))
    save(out/"common_tight_budget_witnesses.csv",shared_witnesses)
    save(out/"portfolio_assignment_results.csv.gz",permutation_rows)
    save(out/"by_portfolio.csv",by_portfolio)
    save(out/"within_condition_counts.csv",context)
    save(out/"identity_comparison.csv",identity_diff)
    save(out/"cell_extreme_witnesses.csv",[dict(extreme=k[1],**r) for k,r in witness.items()])
    for f in FACTORS:
        subset=[x for x in by_portfolio if x["factor"]==f]
        r=dict(factor=f)
        for k in subset[0]:
            if k in ("factor","portfolio"):
                continue
            v=sum(s[k] for s in subset)
            r[k]=v/8 if k.startswith("mean_") else v
        by_factor.append(r)
    save(out/"cell_summary.csv",by_factor)
    assignment_contrasts=[]; sharp=[]; common=[]
    for f in FACTORS:
        local=[x for x in permutation_rows if x["factor"]==f]
        extrema={s:[] for s in ("min","max")}
        for pid in range(1,9):
            specific=[x for x in local if x["portfolio"]==pid]
            vals=[x["mean_up_minus_down"] for x in specific]
            for side,fn in (("min",min),("max",max)):
                boundary=fn(vals)
                r=next(x for x in specific if x["mean_up_minus_down"]==boundary)
                extrema[side].append(r)
            assignment_contrasts.append(dict(factor=f,portfolio=pid,n=len(vals),up_greater=sum(x>0 for x in vals),
                tie=vals.count(0),down_greater=sum(x<0 for x in vals),minimum=min(vals),maximum=max(vals)))
        for side,rs in extrema.items():
            sharp.append(dict(factor=f,extreme=side,mean_down_shortfall=sum(r["mean_down_shortfall"] for r in rs)/8,
                mean_up_shortfall=sum(r["mean_up_shortfall"] for r in rs)/8,
                mean_up_minus_down=sum(r["mean_up_minus_down"] for r in rs)/8,
                witness_permutations_by_portfolio="|".join(r["permutation"] for r in rs),
                up_greater_local_cells=sum(r["up_greater"] for r in rs),
                tie_local_cells=sum(r["tie"] for r in rs),down_greater_local_cells=sum(r["down_greater"] for r in rs)))
        for perm in PERMS:
            code="".join(str(i+1) for i in perm)
            records=by_factor_perm[f,code]
            common.append(dict(factor=f,permutation=code,n=72,
                mean_down_shortfall=sum(x["mean_down_shortfall"] for x in records)/8,
                mean_up_shortfall=sum(x["mean_up_shortfall"] for x in records)/8,
                mean_up_minus_down=sum(x["mean_up_minus_down"] for x in records)/8,
                down_changed=sum(x["down_changed"] for x in records),
                down_changed_zero_shortfall=sum(x["down_changed_zero_shortfall"] for x in records)))
    save(out/"portfolio_mean_ordering.csv",assignment_contrasts)
    save(out/"joint_assignment_sharp_bounds.csv",sharp)
    save(out/"synchronized_assignment_means.csv.gz",common)
    count_summary=[]
    for f in FACTORS:
        for kind,seq in (("portfolio_mean",[x for x in permutation_rows if x["factor"]==f]),
                         ("synchronized_mean",[x for x in common if x["factor"]==f])):
            ds=[x["mean_up_minus_down"] for x in seq]
            count_summary.append(dict(factor=f,comparison=kind,n=len(ds),up_greater=sum(d>0 for d in ds),
                tie=ds.count(0),down_greater=sum(d<0 for d in ds),minimum=min(ds),maximum=max(ds)))
    save(out/"averaged_ordering.csv",count_summary)
    digest_source=(archive/"baseline"/"data"/"synthetic_projects.csv") if archive.is_dir() else archive
    with digest_source.open("rb") as fin:
        input_hash=hashlib.file_digest(fin,"sha256").hexdigest()
    validation=dict(input_sha256=input_hash,hashed_input="project register" if archive.is_dir() else "supplement ZIP",projects=48,financial_bundles=48,portfolios=8,
        mappings_per_portfolio=len(PERMS),portfolio_mappings=8*len(PERMS),
        portfolio_assignment_ceiling_budget_cells=8*len(PERMS)*9,
        matched_direction_contrasts=8*len(PERMS)*9*len(FACTORS),directional_allocations=8*len(PERMS)*9*len(FACTORS)*2,
        joint_independent_assignments=str(len(PERMS)**8),identity_directional_rows=len(identity_diff),
        identity_max_abs_npv_residual=max(float(abs(x["delta_shortfall"])) for x in identity_diff),
        npv_maximizers_per_pool_budget_mask="unique in each of 8*3*64 cases",
        exact_arithmetic="rational intensities and five-year NPVs scaled to integers within each portfolio")
    (out/"validation.json").write_text(json.dumps(validation,indent=2)+"\n")
    print(json.dumps(validation,indent=2))


if __name__=="__main__":
    parser=ArgumentParser(description=__doc__)
    parser.add_argument("inputs",type=Path,help="Path to R3 Supplement_S1.zip")
    parser.add_argument("--output",type=Path,default=Path("."))
    args=parser.parse_args()
    args.output.mkdir(exist_ok=True,parents=True)
    run(args.inputs,args.output)
