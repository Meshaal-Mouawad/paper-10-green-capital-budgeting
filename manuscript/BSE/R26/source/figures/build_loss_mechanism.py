"""Conceptual diagram of equations (2)-(4), no data or numerical scaling."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':8,'pdf.fonttype':42,'svg.fonttype':'none','text.color':'#202b35'})
fig,ax=plt.subplots(figsize=(7.15,3.10)); fig.subplots_adjust(left=.015,right=.985,bottom=.025,top=.98); ax.set(xlim=(0,100),ylim=(0,100));ax.axis('off')
ink='#202b35'; blue='#285d79'; teal='#2d746f'; amber='#9a501e'; gray='#e8edf0'
def box(x,y,w,h,head,sub,edge=blue,fill='#f5f8fa'):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.38,rounding_size=1.2',linewidth=.85,edgecolor=edge,facecolor=fill))
    ax.text(x+w/2,y+h*.68,head,ha='center',va='center',fontsize=8.5,weight='bold',color=ink)
    ax.text(x+w/2,y+h*.28,sub,ha='center',va='center',fontsize=7.6,color=ink,linespacing=1.2)
def arr(x1,y1,x2,y2,color=ink):
    ax.add_patch(FancyArrowPatch((x1,y1),(x2,y2),arrowstyle='-|>',mutation_scale=9,lw=1.1,color=color,shrinkA=1,shrinkB=1))
ax.text(1,97,'A',weight='bold',fontsize=11,va='top'); ax.text(6,97,'From the emissions rule to the funding decision',weight='bold',fontsize=9.5,va='top')
box(1,61,21,23,'Same project inputs','Emissions, costs\nand cash flows',ink,'#f5f6f7')
box(31,75,28,13,'Approved formula','Eligible projects: $T$',teal,'#eef6f4')
box(31,57,28,13,'Reported formula','Eligible projects: $R$',blue,'#eef3f8')
box(69,75,30,13,'Reference optimum','Best qualifying value',teal,'#eef6f4')
box(69,57,30,13,'Reported optimum','Funded projects: $\\widehat S$',blue,'#eef3f8')
ax.plot([22.5,26,26],[72.5,72.5,81.5],color=ink,lw=1);arr(26,81.5,30.5,81.5);ax.plot([26,26],[72.5,63.5],color=ink,lw=1);arr(26,63.5,30.5,63.5)
arr(59.5,81.5,68.5,81.5);arr(59.5,63.5,68.5,63.5)
ax.plot([1,99],[51,51],color='#a6b2ba',lw=.65)
ax.text(1,47,'B',weight='bold',fontsize=11,va='top');ax.text(6,47,'Two components of qualified value lost',weight='bold',fontsize=9.5,va='top')
box(1,14,27,21,'Approved eligibility','$V(T,b)$\nFull budget',teal,'#eef6f4')
box(36.5,14,27,21,'Common eligibility','$V(C,b)$\nFull budget',blue,'#eef3f8')
box(72,14,27,21,'Common eligibility','$V(C,b-K(I))$\nRemaining budget',blue,'#eef3f8')
arr(28.5,24.5,36,24.5,amber);arr(64,24.5,71.5,24.5,amber)
ax.text(32.25,39,'Exclusion',ha='center',fontsize=7.7,weight='bold',color=amber);ax.text(67.75,39,'Displacement',ha='center',fontsize=7.7,weight='bold',color=amber)
ax.text(50,6,'Displacement begins when ineligible spending exceeds the capital left after reserving a least-cost common-eligible optimum.',ha='center',fontsize=7.5)
out=Path(__file__).resolve().parent
for ext in ('pdf','svg','png'):
    fig.savefig(out/f'loss_mechanism.{ext}',dpi=400,facecolor='white')
