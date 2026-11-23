"""Rebuild the two article figures from frozen output tables."""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

TEAL, RUST, BLUE, INK, GRID = "#00766d", "#b34e25", "#3c6094", "#27343b", "#dce2e3"
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9,"axes.spines.top":False,
                     "axes.spines.right":False,"axes.labelcolor":INK,"text.color":INK,
                     "axes.edgecolor":"#8c9a9c","xtick.color":INK,"ytick.color":INK,
                     "pdf.fonttype":42,"axes.axisbelow":True})


def load_csv(p):
    with p.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def project_example(root, out):
    audit=load_csv(root/"data/code_audit.csv")
    decisions=load_csv(root/"data/scenario_decisions.csv")
    ids=sorted({r["project_id"] for r in audit if r["project_id"].startswith("P01_")})
    values={(r["project_id"],r["mode"]):float(r["intensity_reported"]) for r in audit}
    fig, (a,b)=plt.subplots(1,2,figsize=(7.4,3.22),gridspec_kw={"width_ratios":[1.05,1.1]})
    fig.subplots_adjust(left=.09,right=.97,top=.83,bottom=.24,wspace=.54)
    for i,p in enumerate(ids):
        y=5-i
        ref=values[p,"correct"]
        altered=values[p,"gross_denominator"]
        a.plot([altered,ref],[y,y],color="#839297",lw=1.65)
        a.scatter(altered,y,s=29,color=TEAL,marker="s",zorder=3)
        a.scatter(ref,y,s=36,facecolor="white",edgecolor=INK,linewidth=1.1,zorder=4)
    a.axvline(380,color=RUST,ls="--",lw=1.15)
    a.set(yticks=range(6),yticklabels=list("654321"),xticks=[280,320,360,400,440],
          xlabel="Emissions intensity (kg CO₂e/MWh)",ylabel="Project",ylim=(-.55,5.55))
    a.set_title("a   Which projects qualify?",loc="left",fontsize=10,fontweight="bold",pad=8)
    a.legend(handles=[Line2D([],[],marker="o",mfc="white",mec=INK,ls="",label="Net"),
                      Line2D([],[],marker="s",color=TEAL,ls="",label="Gross"),
                      Line2D([],[],ls="--",color=RUST,label="Ceiling")],ncol=3,loc="upper center",
             bbox_to_anchor=(.50,-.32),frameon=False,fontsize=7.4,handlelength=1.1,columnspacing=.75)
    conditions=[(.45,"correct"),(.45,"gross_denominator"),(.6,"correct"),(.6,"gross_denominator")]
    for y,(budget,mode) in enumerate(conditions):
        sel=next(r["selected"].split(";") for r in decisions if r["portfolio"]=="1" and float(r["threshold_kg_mwh"])==380 and float(r["budget_fraction"])==budget and r["mode"]==mode)
        for i,p in enumerate(ids):
            b.scatter(i,3-y,s=52,facecolor=(TEAL if p in sel else "white"),
                      edgecolor=(TEAL if p in sel else "#c4ced0"),marker="s",lw=1)
    b.axhline(1.5,color=GRID,lw=1)
    b.set(yticks=[3,2,1,0],yticklabels=["45% · Net","45% · Gross","60% · Net","60% · Gross"],
          xticks=range(6),xticklabels=list("123456"),xlabel="Project",ylim=(-.5,3.5),xlim=(-.5,5.5))
    b.spines["left"].set_visible(False)
    b.tick_params(axis="y",length=0)
    b.set_title("b   Which projects receive capital?",loc="left",fontsize=10,fontweight="bold",pad=8)
    b.legend(handles=[Line2D([],[],ls="",marker="s",color=TEAL,label="Funded"),
                      Line2D([],[],ls="",marker="s",mfc="white",mec="#a0adb0",label="Unfunded")],
             loc="upper center",bbox_to_anchor=(.5,-.32),frameon=False,ncol=2,fontsize=7.4)
    fig.savefig(out/"project_example.pdf",bbox_inches="tight",pad_inches=.045)
    plt.close(fig)


def shortfalls(root,out):
    fig,axes=plt.subplots(1,2,figsize=(7.4,2.9),sharey=True)
    fig.subplots_adjust(left=.1,bottom=.28,right=.98,top=.84,wspace=.17)
    modes=[("gross_denominator","Gross output",TEAL,"o"),("scope2_omission","Scope 2 omitted",BLUE,"s"),
           ("net_output_undercount","Net output understated",RUST,"^")]
    for ax,(file,xkey,title,xlab) in zip(axes,[("budget_summary","budget_fraction","a   Capital budget","Budget (% of candidate capital)"),
                                               ("threshold_summary","threshold_kg_mwh","b   Emissions ceiling","Ceiling (kg CO₂e/MWh)")]):
        rows=load_csv(root/f"results/{file}.csv")
        for m,label,col,mark in modes:
            data=sorted((float(r[xkey]),float(r["mean_npv_regret_musd"])) for r in rows if r["mode"]==m)
            xx,yy=zip(*data)
            xx=[int(round(x*100)) if xkey=="budget_fraction" else int(x) for x in xx]
            ax.plot(xx,yy,color=col,marker=mark,lw=1.7,ms=4.8,label=label)
            ax.set_xticks(xx)
        ax.set_xlabel(xlab)
        ax.set_title(title,loc="left",fontsize=10,fontweight="bold",pad=7)
        ax.set_ylim(-.5,20.5)
        ax.set_yticks([0,5,10,15,20])
        ax.grid(axis="y",color=GRID,lw=.65)
    axes[0].set_ylabel("Qualified NPV shortfall\n(USD million)")
    fig.legend(*axes[0].get_legend_handles_labels(),loc="lower center",bbox_to_anchor=(.54,-.04),ncol=3,frameon=False,fontsize=8.2)
    fig.savefig(out/"shortfall_sensitivity.pdf",bbox_inches="tight",pad_inches=.045)
    plt.close(fig)


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("baseline",type=Path)
    p.add_argument("figures",type=Path)
    args=p.parse_args()
    args.figures.mkdir(parents=True,exist_ok=True)
    project_example(args.baseline,args.figures)
    shortfalls(args.baseline,args.figures)
