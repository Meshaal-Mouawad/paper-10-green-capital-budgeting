"""Draw the article's exact number-of-portfolios response surfaces from policy_cells.csv."""
import argparse
import csv
from fractions import Fraction
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import colors
from matplotlib.patches import Rectangle
import numpy as np


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("cells",type=Path)
    p.add_argument("figure",type=Path)
    args=p.parse_args()
    palettes=["#f7faf8","#e6f2ed","#cee6dd","#acd7ca","#81c4b6",
              "#50aa9c","#278c83","#116a67","#064847"]
    cmap=colors.ListedColormap(palettes)
    norm=colors.BoundaryNorm(np.arange(-.5,9.5,1),cmap.N)
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":8.6,"pdf.fonttype":42,
                         "axes.edgecolor":"#657472","axes.labelcolor":"#23332f",
                         "text.color":"#23332f","xtick.color":"#23332f","ytick.color":"#23332f"})
    with args.cells.open(newline="") as stream:
        rows=list(csv.DictReader(stream))
    fig,axes=plt.subplots(1,3,figsize=(7.65,2.95),sharey=True,sharex=True)
    fig.subplots_adjust(left=.085,right=.985,bottom=.34,top=.855,wspace=.16)
    names=(("gross_denominator","a   Gross output"),("scope2_omission","b   Scope 2 omitted"),
           ("net_output_undercount","c   Net output understated"))
    for ax,(mode,title) in zip(axes,names):
        cells=[]
        for row in rows:
            if row["mode"]!=mode: continue
            total=int(row["total_capex_musd"])
            cells.append((Fraction(row["tau_left"]),Fraction(row["tau_right"]),
                          Fraction(row["budget_left_musd"])/total,Fraction(row["budget_right_musd"])/total,
                          int(row["changed"])))
        xs=sorted({x for l,h,bl,bh,changed in cells for x in (l,h)})
        ys=sorted({y for l,h,bl,bh,changed in cells for y in (bl,bh)})
        ix={v:i for i,v in enumerate(xs)}
        iy={v:i for i,v in enumerate(ys)}
        counts=np.zeros((len(ys)-1,len(xs)-1),dtype=np.uint8)
        coverage=counts.copy()
        for l,h,bl,bh,changed in cells:
            counts[iy[bl]:iy[bh],ix[l]:ix[h]]+=changed
            coverage[iy[bl]:iy[bh],ix[l]:ix[h]]+=1
        assert np.all(coverage==8)
        # Rasterize just the colored cells to avoid hairline tiling in PDF viewers.
        im=ax.pcolormesh([float(x) for x in xs],[100*float(y) for y in ys],counts,
                         cmap=cmap,norm=norm,shading="flat",rasterized=True)
        ax.add_patch(Rectangle((380,45),40,30,fill=False,edgecolor="white",linewidth=2.6))
        ax.add_patch(Rectangle((380,45),40,30,fill=False,edgecolor="#493a34",linewidth=1.05,linestyle="--"))
        ax.set_title(title,loc="left",fontsize=9.6,fontweight="bold",pad=7)
        ax.set_xticks([300,400,500]); ax.set_yticks([0,25,50,75,100])
        ax.tick_params(length=3)
    axes[0].set_ylabel("Budget (% of pool capital)")
    fig.text(.535,.175,"Emissions ceiling (kg CO₂e/MWh)",ha="center",fontsize=9)
    cax=fig.add_axes([.40,.082,.42,.034])
    cbar=fig.colorbar(im,cax=cax,orientation="horizontal",ticks=[0,1,2,3,4,5,6,7,8])
    cbar.ax.tick_params(length=2,pad=1,labelsize=7)
    cbar.outline.set_visible(False)
    fig.text(.378,.091,"Portfolios changing selection",ha="right",va="center",fontsize=8.2)
    args.figure.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(args.figure,bbox_inches="tight",pad_inches=.04,dpi=340,metadata={"CreationDate":None})
    plt.close(fig)


if __name__=="__main__":
    main()
