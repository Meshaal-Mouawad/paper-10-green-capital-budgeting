"""Regenerate the two article figures: python render_figures.py /path/to/Supplement_S1.zip.
Requires matplotlib and numpy. Outputs PDFs alongside this file."""
import argparse
import csv
from fractions import Fraction
from io import TextIOWrapper
from pathlib import Path
from zipfile import ZipFile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Rectangle
import numpy as np

OUT = Path(__file__).resolve().parent
INK, BLUE, GOLD = "#1d2934", "#245a77", "#a45515"
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9,"pdf.fonttype":42,
    "text.color":INK,"axes.labelcolor":INK,"xtick.color":INK,"ytick.color":INK,
    "axes.spines.top":False,"axes.spines.right":False,"axes.edgecolor":"#9aa5ab",
    "axes.linewidth":0.6,"xtick.major.size":3,"ytick.major.size":3})

def records(archive, member):
    with archive.open("Supplement_S1/" + member) as stream:
        return list(csv.DictReader(TextIOWrapper(stream, encoding="utf-8")))

def save(fig, name):
    fig.savefig(OUT / name, dpi=450, metadata={"CreationDate":None})
    plt.close(fig)

def example(archive):
    projects = {p["id"]:p for p in records(archive,"baseline/data/synthetic_projects.csv") if p["portfolio"]=="1"}
    decisions = sorted((r for r in records(archive,"baseline/data/scenario_decisions.csv")
        if r["portfolio"]=="1" and r["mode"]=="gross_denominator" and float(r["threshold_kg_mwh"])==380
        and float(r["budget_fraction"]) in (0.45,0.6)), key=lambda r:float(r["budget_fraction"]))
    assert len(projects)==6 and len(decisions)==2
    ids = sorted(projects)
    cost = float(projects[ids[4]]["capex_musd"])
    fig = plt.figure(figsize=(7.16,2.9))
    a=fig.add_axes([.075,.215,.364,.56])
    b=fig.add_axes([.55,.215,.412,.56])
    fig.text(.013,.935,"A   Which projects meet the ceiling?",weight="bold",fontsize=10)
    fig.text(.50,.935,"B   Is there room for project 5?",weight="bold",fontsize=10)
    fig.text(.50,.845,"Capital left after reserving $75m for projects 1–3",fontsize=8.1)
    for i,key in enumerate(ids,1):
        p=projects[key]
        net=float(p["intensity_true"])
        gross=(float(p["scope1_kg"])+float(p["scope2_kg"]))/float(p["gross_mwh"])
        a.plot([gross,net],[i,i],color=GOLD if i==5 else "#a7afb5",lw=2.2 if i==5 else 1.2,zorder=2)
        a.plot(net,i,'o',ms=5,mfc="white",mec=INK,zorder=3,label="Net exports" if i==1 else None)
        a.plot(gross,i,'s',ms=4.5,color=BLUE,zorder=3,label="Gross generation" if i==1 else None)
    a.axvline(380,ls=(0,(3,2)),color=INK,lw=.9)
    a.text(380,.55,"380",ha="center",va="bottom",fontsize=8,backgroundcolor="white")
    a.set(xlim=(282,468),ylim=(6.5,.5),xticks=[300,350,400,450],yticks=range(1,7),
        yticklabels=[f"P{i}" for i in range(1,7)],xlabel="Emissions intensity (kg CO₂e/MWh)")
    a.tick_params(axis='y',length=0);a.spines['left'].set_visible(False)
    a.get_yticklabels()[4].set_color(GOLD);a.get_yticklabels()[4].set_fontweight('bold')
    a.legend(loc="center left",bbox_to_anchor=(-.035,1.16),ncol=2,fontsize=8,frameon=False,
        handlelength=1,columnspacing=1.0,handletextpad=.3)
    for y,r in zip([1.0,0.15],decisions):
        cap=float(r["budget_musd"])
        reserved=sum(float(projects[k]["capex_musd"]) for k in r["baseline_selected"].split(";"))
        left=cap-reserved
        loss=float(r["valid_npv_regret_musd"])
        b.barh(y,left,height=.105,color=BLUE,zorder=2)
        b.plot(left,y,'o',color=BLUE,ms=4)
        b.text(0,y+.14,f"${cap:g}m budget",va='bottom',weight="bold",fontsize=8.6)
        b.text(left+.95,y,f"{left:g}",va="center",weight="bold",fontsize=8.2)
        displaced=sorted(set(r["baseline_selected"].split(";"))-set(r["selected"].split(";")))
        outcome=("P"+" and P".join(str(int(key[-2:])) for key in displaced)+" displaced" if displaced else "All three retained")
        b.text(0,y-.17,f"{outcome}  ·  NPV lost: ${loss:.2f}m",va="top",fontsize=8)
    b.axvline(cost,color=GOLD,ls=(0,(3,2)),lw=1.3,zorder=0)
    b.text(cost,1.51,f"${cost:g}m cost",va="bottom",ha="center",color=GOLD,fontsize=8)
    b.set(xlim=(0,50),ylim=(-.42,1.61),xticks=[0,10,20,30,40,50],yticks=[],xlabel="Available capital (USD millions)")
    b.spines['left'].set_visible(False)
    save(fig,"project_example.pdf")

def policy_map(archive):
    rows=records(archive,"outputs/policy/policy_cells.csv")
    summary=records(archive,"outputs/policy/policy_summary.csv")
    modes=[("gross_denominator","Gross generation"),("scope2_omission","Scope 2 omitted"),
           ("net_output_undercount","Net exports understated")]
    palette=ListedColormap(["#fbfcfd","#e2eaf0","#c6d9e3","#aac6d6","#89afc4",
                            "#6496ae","#42778e","#26586e","#123a4d"])
    norm=BoundaryNorm(np.arange(-.5,9.5),palette.N)
    fig,axes=plt.subplots(2,3,figsize=(7.16,4.25),sharex=True,sharey=True)
    fig.subplots_adjust(left=.125,right=.986,bottom=.235,top=.85,wspace=.115,hspace=.49)
    for j,(mode,title) in enumerate(modes):
        cells=[]
        for r in rows:
            if r["mode"]==mode:
                cap=int(r["total_capex_musd"])
                cells.append((Fraction(r["tau_left"]),Fraction(r["tau_right"]),
                    Fraction(r["budget_left_musd"])/cap,Fraction(r["budget_right_musd"])/cap,
                    int(r["changed"]),int(r["qualified_shortfall_positive"])))
        xs=sorted({x for c in cells for x in c[:2]});ys=sorted({y for c in cells for y in c[2:4]})
        ix={x:k for k,x in enumerate(xs)};iy={y:k for k,y in enumerate(ys)}
        coverage=np.zeros((len(ys)-1,len(xs)-1),dtype=np.uint8)
        changed=np.zeros_like(coverage);loss=np.zeros_like(coverage)
        for x1,x2,y1,y2,ch,lo in cells:
            box=np.s_[iy[y1]:iy[y2],ix[x1]:ix[x2]]
            coverage[box]+=1;changed[box]+=ch;loss[box]+=lo
        assert np.all(coverage==8) and np.all(loss<=changed)
        x=np.array([float(t) for t in xs]); y=np.array([float(t) for t in ys])
        for window,lx,hx,ly,hy in [("full_support",x[0],x[-1],0,1),("grid_window",380,420,.45,.75)]:
            area=np.outer(np.diff(np.clip(y,ly,hy)),np.diff(np.clip(x,lx,hx)))
            archived=next(r for r in summary if r["mode"]==mode and r["window"]==window)
            for counts,key in [(changed,"mean_changed_area_pct"),(loss,"mean_positive_area_pct")]:
                percent=(counts*area).sum()/area.sum()*100/8
                assert abs(percent-float(archived[key]))<1e-8,(mode,window,key,percent)
        for i,values in enumerate([changed,loss]):
            ax=axes[i,j]
            ax.pcolormesh([float(x) for x in xs],[100*float(y) for y in ys],values,
                cmap=palette,norm=norm,rasterized=True,shading="flat")
            for color,width,style in [("white",2.5,"-"),(INK,.9,"--")]:
                ax.add_patch(Rectangle((380,45),40,30,fill=False,ec=color,lw=width,ls=style))
            ax.set(xticks=[300,400,500],yticks=[0,50,100])
            ax.tick_params(labelsize=8)
            if i==0:ax.set_title(title,fontsize=8.8,pad=4)
    fig.text(.125,.955,"A   Funded projects changed",weight="bold",fontsize=10.2)
    fig.text(.125,.504,"B   Qualified net present value fell",weight="bold",fontsize=10.2)
    fig.text(.026,.535,"Budget (% of total project cost)",rotation=90,va="center",fontsize=8.5)
    fig.text(.55,.133,"Emissions ceiling (kg CO₂e/MWh)",ha="center",fontsize=8.6)
    fig.text(.125,.045,"Number of portfolios",va="center",fontsize=8.3)
    for k in range(9):
        x=.385+.053*k
        fig.add_artist(Rectangle((x,.023),.046,.045,transform=fig.transFigure,
            facecolor=palette(k),edgecolor="#aab2b6",linewidth=.35))
        fig.text(x+.023,.045,str(k),ha="center",va="center",fontsize=8,color="white" if k>=6 else INK)
    save(fig,"policy_geometry.pdf")

if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("supplement",type=Path)
    with ZipFile(parser.parse_args().supplement) as archive:
        example(archive)
        policy_map(archive)
